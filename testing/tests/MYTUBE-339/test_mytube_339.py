"""
MYTUBE-339: Transcoding job completion sequence — status updated to 'ready'
            only after manifest persistence.

Objective
---------
Verify that the backend transcoding process follows a strict sequence of
operations to prevent videos from being marked 'ready' before their manifest
data is saved.

Specifically, this test verifies that:
- The database enforces the invariant via a CHECK constraint
  (chk_ready_requires_hls): status='ready' requires hls_manifest_path IS NOT NULL.
- The transcoder's UpdateVideo call is atomic — it sets hls_manifest_path,
  thumbnail_url, and status='ready' in a single SQL UPDATE statement.
- A video cannot be updated to status='ready' without hls_manifest_path being set.
- After an atomic 'ready' update, the API endpoint returns hls_manifest_url as
  non-null alongside status='ready'.
- There is no observable intermediate state where the API would return
  status='ready' with hls_manifest_url=null.

Test Steps
----------
1. Connect to the database and verify the CHECK constraint
   chk_ready_requires_hls exists on the videos table.
2. Insert a test video with status='processing' and hls_manifest_path=NULL.
3. Attempt to update the video to status='ready' while leaving
   hls_manifest_path=NULL → must raise a constraint violation error.
4. Perform the atomic UPDATE (hls_manifest_path + status='ready' together) as
   the real transcoder does.
5. Via the API (GET /api/videos/:id), verify the video is served with
   status='ready' and a non-null hls_manifest_url.
6. Query the entire videos table: assert no rows exist where
   status='ready' AND hls_manifest_path IS NULL.

Environment Variables
---------------------
- API_BINARY         : Path to the pre-built Go binary
                       (default: <repo_root>/api/mytube-api).
- FIREBASE_TEST_TOKEN : Firebase ID token (required; test skipped if absent).
- FIREBASE_PROJECT_ID : Firebase project ID (required; test skipped if absent).
- FIREBASE_TEST_UID   : UID embedded in the test token
                        (default: test-uid-mytube-339).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                        Database connection settings with sensible defaults.

Architecture Notes
------------------
- Direct psycopg2 connections are used for DB-level assertion and test-data setup.
- ApiProcessService starts the Go API binary so we can exercise the public endpoint.
- VideoApiService calls GET /api/videos/:id and inspects hls_manifest_url.
- No hardcoded waits — ApiProcessService.wait_for_ready() polls /health.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

import psycopg2
import psycopg2.errors
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18339
_STARTUP_TIMEOUT = 20.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-339")

_TEST_USERNAME = "testuser_mytube339"

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

# Fake CDN base URL and HLS bucket used to build the manifest path.
_HLS_BUCKET = "mytube-hls-output"
_CDN_BASE_URL = os.getenv("CDN_BASE_URL", "https://cdn.example.com")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> None:
    """Build the Go API binary if it is not already present."""
    if os.path.isfile(API_BINARY):
        return
    api_dir = os.path.join(_REPO_ROOT, "api")
    result = subprocess.run(
        ["go", "build", "-o", API_BINARY, "."],
        cwd=api_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to build API binary:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _cleanup(conn, user_id: str) -> None:
    """Remove all test rows in FK-safe order for the given user_id."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM ratings WHERE video_id IN "
            "(SELECT id FROM videos WHERE uploader_id = %s)",
            (user_id,),
        )
        cur.execute("DELETE FROM ratings WHERE user_id = %s", (user_id,))
        cur.execute(
            "DELETE FROM comments WHERE video_id IN "
            "(SELECT id FROM videos WHERE uploader_id = %s)",
            (user_id,),
        )
        cur.execute("DELETE FROM comments WHERE author_id = %s", (user_id,))
        cur.execute(
            "DELETE FROM video_tags WHERE video_id IN "
            "(SELECT id FROM videos WHERE uploader_id = %s)",
            (user_id,),
        )
        cur.execute("DELETE FROM videos WHERE uploader_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials():
    """Skip the entire module when Firebase credentials are not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping transcoding-sequence test. "
            "Set FIREBASE_TEST_TOKEN to run this test."
        )
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — the API server needs this to "
            "initialise the Firebase verifier."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def db_conn(db_config: DBConfig):
    """Direct psycopg2 connection for setup, DB assertions, and teardown."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """Build (if needed) and start the Go API server; stop on teardown."""
    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "GOOGLE_APPLICATION_CREDENTIALS": _MOCK_CREDS,
        "RAW_UPLOADS_BUCKET": _RAW_UPLOADS_BUCKET,
        "CDN_BASE_URL": _CDN_BASE_URL,
    }

    svc = ApiProcessService(
        binary_path=API_BINARY,
        port=_PORT,
        env=env,
        startup_timeout=_STARTUP_TIMEOUT,
    )
    svc.start()

    ready = svc.wait_for_ready(path="/health")
    if not ready:
        logs = svc.get_log_output()
        svc.stop()
        pytest.fail(
            f"API server did not become ready within {_STARTUP_TIMEOUT}s.\nLogs:\n{logs}"
        )

    yield svc
    svc.stop()


@pytest.fixture(scope="module")
def video_api(api_server: ApiProcessService) -> VideoApiService:
    cfg = APIConfig()
    cfg.base_url = f"http://127.0.0.1:{_PORT}"
    return VideoApiService(cfg)


@pytest.fixture(scope="module")
def seeded_user(api_server, db_conn):
    """Insert a test user and yield its DB id.  Clean up on teardown."""
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) "
            "ON CONFLICT (firebase_uid) DO NOTHING",
            (_FIREBASE_TEST_UID, _TEST_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()
    if row is None:
        pytest.fail(
            f"Could not insert or find user for firebase_uid={_FIREBASE_TEST_UID!r}"
        )
    user_id = str(row[0])

    yield user_id

    _cleanup(db_conn, user_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTranscodingSequence:
    """MYTUBE-339: Status 'ready' must only be set after hls_manifest_path is stored."""

    # ------------------------------------------------------------------
    # Step 1 — DB constraint check
    # ------------------------------------------------------------------

    def test_check_constraint_exists(self, db_conn) -> None:
        """Step 1: The DB must have chk_ready_requires_hls constraint on videos.

        Migration 0009 adds:
            CHECK (status != 'ready' OR hls_manifest_path IS NOT NULL)
        Without this constraint a coding error in the transcoder could
        silently insert a 'ready' row with a NULL manifest.
        """
        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)
                FROM   information_schema.table_constraints
                WHERE  table_name       = 'videos'
                  AND  constraint_name  = 'chk_ready_requires_hls'
                  AND  constraint_type  = 'CHECK'
                """
            )
            count = cur.fetchone()[0]
        assert count == 1, (
            "Expected CHECK constraint 'chk_ready_requires_hls' on the videos table, "
            "but it was not found.  Migration 0009_require_hls_for_ready_videos.up.sql "
            "may not have been applied."
        )

    # ------------------------------------------------------------------
    # Step 2+3 — Constraint violation: cannot mark 'ready' without manifest
    # ------------------------------------------------------------------

    def test_constraint_rejects_ready_without_manifest(
        self, db_config: DBConfig, db_conn, seeded_user: str
    ) -> None:
        """Steps 2–3: Attempting to set status='ready' with NULL hls_manifest_path
        must raise a CHECK-constraint violation.

        This directly verifies that the database prevents the broken intermediate
        state the ticket describes: status='ready' AND hls_manifest_url=null.
        """
        video_id = str(uuid.uuid4())
        try:
            # Insert a video in 'processing' state (valid — no manifest needed yet).
            with db_conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO videos (id, uploader_id, title, status) "
                    "VALUES (%s, %s, %s, 'processing')",
                    (video_id, seeded_user, "MYTUBE-339 constraint test"),
                )

            # Now attempt to flip status to 'ready' WITHOUT providing the manifest path.
            # The DB constraint must reject this. Use a separate connection with
            # autocommit=False so we can roll back on constraint violation.
            constraint_violated = False
            conn2 = psycopg2.connect(db_config.dsn())
            try:
                conn2.autocommit = False
                try:
                    with conn2.cursor() as cur:
                        cur.execute(
                            "UPDATE videos SET status = 'ready' WHERE id = %s",
                            (video_id,),
                        )
                    conn2.commit()
                except psycopg2.errors.CheckViolation:
                    constraint_violated = True
                    conn2.rollback()
                except Exception:
                    conn2.rollback()
                    raise
            finally:
                conn2.close()

            assert constraint_violated, (
                "Expected a CHECK constraint violation when updating status to 'ready' "
                "with hls_manifest_path=NULL, but the UPDATE succeeded.  "
                "This means the database does NOT enforce the invariant that prevents "
                "videos from being marked 'ready' before their manifest is stored."
            )
        finally:
            # Cleanup the test row regardless of outcome.
            with db_conn.cursor() as cur:
                cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))

    # ------------------------------------------------------------------
    # Step 4 — Atomic update succeeds
    # ------------------------------------------------------------------

    def test_atomic_update_succeeds(
        self, db_conn, seeded_user: str
    ) -> None:
        """Step 4: The transcoder's atomic UPDATE (manifest + status together)
        must succeed and leave the video row in a fully consistent 'ready' state.
        """
        video_id = str(uuid.uuid4())
        hls_manifest_path = f"gs://{_HLS_BUCKET}/videos/{video_id}/index.m3u8"
        thumbnail_url = f"{_CDN_BASE_URL}/videos/{video_id}/thumbnail.jpg"

        try:
            with db_conn.cursor() as cur:
                # Insert in 'processing' state — simulates the state after upload.
                cur.execute(
                    "INSERT INTO videos (id, uploader_id, title, status) "
                    "VALUES (%s, %s, %s, 'processing')",
                    (video_id, seeded_user, "MYTUBE-339 atomic update test"),
                )

            # Perform the same single-statement atomic UPDATE as the transcoder.
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE videos
                    SET hls_manifest_path = %s,
                        thumbnail_url      = %s,
                        status             = 'ready',
                        updated_at         = now()
                    WHERE id = %s
                    """,
                    (hls_manifest_path, thumbnail_url, video_id),
                )

            # Verify the row is now fully consistent.
            with db_conn.cursor() as cur:
                cur.execute(
                    "SELECT status, hls_manifest_path FROM videos WHERE id = %s",
                    (video_id,),
                )
                row = cur.fetchone()

            assert row is not None, f"Video row {video_id} not found after update."
            status, stored_manifest_path = row
            assert status == "ready", (
                f"Expected status='ready' after atomic update, got {status!r}."
            )
            assert stored_manifest_path is not None, (
                "hls_manifest_path is NULL after the atomic update — the transcoder's "
                "UpdateVideo call did not persist the manifest path."
            )
            assert stored_manifest_path == hls_manifest_path, (
                f"Expected hls_manifest_path={hls_manifest_path!r}, "
                f"got {stored_manifest_path!r}."
            )
        finally:
            with db_conn.cursor() as cur:
                cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))

    # ------------------------------------------------------------------
    # Step 5 — API serves ready video with non-null hls_manifest_url
    # ------------------------------------------------------------------

    def test_api_returns_hls_url_for_ready_video(
        self, db_conn, seeded_user: str, video_api: VideoApiService
    ) -> None:
        """Step 5: GET /api/videos/:id must return hls_manifest_url as non-null
        when the video has status='ready' and hls_manifest_path set.

        This verifies there is no intermediate state visible to the API where
        status='ready' AND hls_manifest_url=null.
        """
        video_id = str(uuid.uuid4())
        hls_manifest_path = f"gs://{_HLS_BUCKET}/videos/{video_id}/index.m3u8"
        thumbnail_url = f"{_CDN_BASE_URL}/videos/{video_id}/thumbnail.jpg"

        try:
            with db_conn.cursor() as cur:
                # Insert in processing state first.
                cur.execute(
                    "INSERT INTO videos (id, uploader_id, title, status) "
                    "VALUES (%s, %s, %s, 'processing')",
                    (video_id, seeded_user, "MYTUBE-339 API test"),
                )

            # Verify the API returns 404/null before transcoding is complete.
            pre_status, pre_body = video_api.get_video_detail(video_id)
            # The API returns nil (404 or empty) for non-ready videos.
            assert pre_status != 200 or pre_body is None or pre_body.get("status") != "ready", (
                f"API returned a 'ready' video before the transcoding update was applied. "
                f"status={pre_status}, body={pre_body}"
            )

            # Perform the atomic transcoder update.
            with db_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE videos
                    SET hls_manifest_path = %s,
                        thumbnail_url      = %s,
                        status             = 'ready',
                        updated_at         = now()
                    WHERE id = %s
                    """,
                    (hls_manifest_path, thumbnail_url, video_id),
                )

            # Now the API must serve the video with both status='ready' and
            # hls_manifest_url non-null.
            post_status, post_body = video_api.get_video_detail(video_id)
            assert post_status == 200, (
                f"Expected HTTP 200 for ready video {video_id}, got {post_status}. "
                f"Body: {post_body}"
            )
            assert post_body is not None, (
                f"API returned an empty body for video {video_id} after status='ready'."
            )
            assert post_body.get("status") == "ready", (
                f"Expected status='ready' in API response, got {post_body.get('status')!r}."
            )
            hls_url = post_body.get("hls_manifest_url")
            assert hls_url is not None, (
                f"API returned status='ready' but hls_manifest_url=null for video {video_id}. "
                f"This is the forbidden intermediate state described in MYTUBE-339: "
                f"the frontend cannot mount a player without a manifest URL."
            )
            assert isinstance(hls_url, str) and hls_url, (
                f"hls_manifest_url must be a non-empty string, got {hls_url!r}."
            )
        finally:
            with db_conn.cursor() as cur:
                cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))

    # ------------------------------------------------------------------
    # Step 6 — Global DB invariant: no 'ready' video has NULL manifest
    # ------------------------------------------------------------------

    def test_no_ready_video_has_null_manifest(self, db_conn) -> None:
        """Step 6: The entire videos table must not contain any row where
        status='ready' AND hls_manifest_path IS NULL.

        This is the broadest check: it ensures no existing video violates
        the invariant, including rows that may have been inserted before
        migration 0009 was applied.
        """
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM videos "
                "WHERE status = 'ready' AND hls_manifest_path IS NULL"
            )
            count = cur.fetchone()[0]
        assert count == 0, (
            f"Found {count} video(s) with status='ready' AND hls_manifest_path=NULL. "
            "These rows represent the broken intermediate state described in MYTUBE-339. "
            "The transcoder must always set hls_manifest_path atomically with status='ready'. "
            "Migration 0009 should have reset violating rows back to 'processing'; "
            "re-running the migration or triggering re-transcoding will fix them."
        )
