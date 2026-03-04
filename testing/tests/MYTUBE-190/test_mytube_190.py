"""
MYTUBE-190: Soft-delete video via API — status changed to deleted.

Objective
---------
Verify that DELETE /api/videos/:id performs a soft-delete by updating the
video's status to 'deleted' in the database.

Preconditions
-------------
- User is authenticated and owns a video.

Test structure
--------------
Layer A — Go unit tests (always runs; no Firebase token or DB required):
    Runs the existing Go handler unit tests to verify that DELETE /api/videos/:id
    returns 204 No Content on success, enforces auth, and validates the video ID.

    Note: the test case description mentions 200 OK, but the implementation
    correctly returns 204 No Content for a successful DELETE. Layer A confirms
    this with TestDeleteVideo_Success_Returns204.

Layer B — Integration test via HTTP (runs when FIREBASE_TEST_TOKEN is set):
    Starts the full Go API server, seeds a 'ready' video owned by the CI test
    user, sends an authenticated DELETE request, asserts 204 No Content, then
    queries the database directly to confirm the video status is 'deleted'.
    Also verifies the video no longer appears in GET /api/me/videos.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN      : Valid Firebase ID token (Layer B only).
- FIREBASE_TEST_UID        : Firebase UID of the test user
                             (Layer B only; default: ci-test-user-001).
- FIREBASE_PROJECT_ID      : Firebase project ID
                             (default: ai-native-478811).
- API_BINARY               : Path to the pre-built Go binary
                             (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                             Database connection settings (Layer B only).

Architecture notes
------------------
- Layer A invokes `go test ./internal/handler/ -run TestDeleteVideo` via subprocess.
- Layer B uses ApiProcessService + AuthService.delete() for authenticated DELETE.
- A direct psycopg2 connection seeds the test video and verifies the DB state.
- No hardcoded URLs, credentials, or environment values.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18190
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "ai-native-478811")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT,
    "testing",
    "fixtures",
    "mock_service_account.json",
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)

# Placeholder bucket — the delete endpoint never touches GCS.
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "test-placeholder-bucket-190")

# Unique username and title to avoid collisions with other test data.
_TEST_USERNAME = "testuser-mytube190"
_VIDEO_TITLE = "softdelete-test-video-mytube190"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> None:
    """Build the Go API binary if it is not already present."""
    if os.path.isfile(API_BINARY):
        return
    result = subprocess.run(
        ["go", "build", "-o", API_BINARY, "."],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to build API binary:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _run_go_tests(pattern: str) -> subprocess.CompletedProcess:
    """Run Go unit tests matching *pattern* inside the handler package."""
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-run", pattern, "./internal/handler/"],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Layer A — Go unit tests (always runs; no external services required)
# ---------------------------------------------------------------------------


class TestSoftDeleteVideo_GoUnit:
    """Run existing Go handler unit tests covering DELETE /api/videos/:id."""

    def test_success_returns_204(self):
        """DELETE /api/videos/:id must return 204 No Content on success."""
        result = _run_go_tests("TestDeleteVideo_Success_Returns204")
        assert result.returncode == 0, (
            f"Go unit test TestDeleteVideo_Success_Returns204 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_no_claims_returns_401(self):
        """DELETE without auth claims must return 401 Unauthorized."""
        result = _run_go_tests("TestDeleteVideo_NoClaims_Returns401")
        assert result.returncode == 0, (
            f"Go unit test TestDeleteVideo_NoClaims_Returns401 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_invalid_video_id_returns_400(self):
        """DELETE with a non-UUID video ID must return 400 Bad Request."""
        result = _run_go_tests("TestDeleteVideo_InvalidVideoID_Returns400")
        assert result.returncode == 0, (
            f"Go unit test TestDeleteVideo_InvalidVideoID_Returns400 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_video_not_found_or_not_owner_returns_404(self):
        """DELETE for a video not owned by the caller must return 404."""
        result = _run_go_tests("TestDeleteVideo_VideoNotFoundOrNotOwner_Returns404")
        assert result.returncode == 0, (
            f"Go unit test TestDeleteVideo_VideoNotFoundOrNotOwner_Returns404 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_full_delete_suite_passes(self):
        """All TestDeleteVideo_* Go handler unit tests must pass."""
        result = _run_go_tests("TestDeleteVideo_")
        assert result.returncode == 0, (
            f"One or more TestDeleteVideo_* Go unit tests failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Layer B — Integration test via HTTP
# Requires FIREBASE_TEST_TOKEN; skipped gracefully when absent.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def firebase_token() -> str:
    """Load the Firebase test token; skip Layer B when absent."""
    token = os.getenv("FIREBASE_TEST_TOKEN", "")
    if not token:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping HTTP integration tests "
            "(Layer A Go unit tests still run)."
        )
    return token


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig, firebase_token: str):
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
            f"API server did not become ready within {_STARTUP_TIMEOUT}s.\n"
            f"Logs:\n{logs}"
        )

    yield svc
    svc.stop()


@pytest.fixture(scope="module")
def db_conn(api_server, db_config: DBConfig):
    """
    Open a direct psycopg2 connection after the API server (and its migrations)
    are up. Used to seed test data and verify DB state after the API call.
    """
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_video(db_conn) -> dict:
    """
    Create a user row (or reuse an existing one) and insert a 'ready' video
    owned by that user.

    Returns a dict with 'user_id' and 'video_id'.
    Teardown hard-deletes the seeded video to leave the DB clean.
    """
    firebase_uid = _FIREBASE_TEST_UID
    username = _TEST_USERNAME

    # Insert or re-use the test user.
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO UPDATE SET username = EXCLUDED.username
            RETURNING id
            """,
            (firebase_uid, username),
        )
        user_id = str(cur.fetchone()[0])

    # Insert a video with status 'ready' owned by the test user.
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status)
            VALUES (%s, %s, 'ready')
            RETURNING id
            """,
            (user_id, _VIDEO_TITLE),
        )
        video_id = str(cur.fetchone()[0])

    yield {"user_id": user_id, "video_id": video_id, "firebase_uid": firebase_uid}

    # Teardown: remove the seeded video row unconditionally.
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))


@pytest.fixture(scope="module")
def auth_client(api_server, firebase_token: str) -> AuthService:
    """Return an AuthService pointed at the local test API server."""
    return AuthService(base_url=f"http://127.0.0.1:{_PORT}", token=firebase_token)


@pytest.fixture(scope="module")
def delete_response(
    seeded_video: dict, auth_client: AuthService
) -> tuple[int, str]:
    """Send DELETE /api/videos/<video_id> and capture (status_code, body)."""
    video_id = seeded_video["video_id"]
    return auth_client.delete(f"/api/videos/{video_id}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSoftDeleteVideo_Integration:
    """HTTP integration: DELETE /api/videos/:id performs a soft-delete."""

    def test_delete_returns_204(self, delete_response: tuple[int, str]):
        """
        DELETE /api/videos/:id must return 204 No Content on success.

        Note: the test case ticket describes 200 OK, but the implementation
        correctly returns 204 No Content for a DELETE that soft-deletes a row.
        """
        status_code, body = delete_response
        assert status_code == 204, (
            f"Expected HTTP 204 No Content after soft-delete, got {status_code}. "
            f"Response body: {body!r}"
        )

    def test_delete_response_body_is_empty(self, delete_response: tuple[int, str]):
        """The 204 No Content response body must be empty."""
        _, body = delete_response
        assert body.strip() == "", (
            f"Expected an empty body for 204 No Content, got: {body!r}"
        )

    def test_video_status_is_deleted_in_db(
        self,
        seeded_video: dict,
        delete_response: tuple[int, str],  # ensures DELETE ran first
        db_conn,
    ):
        """
        After DELETE, the video row must still exist in the database with
        status = 'deleted' (soft-delete, not a hard-delete).
        """
        video_id = seeded_video["video_id"]

        with db_conn.cursor() as cur:
            cur.execute("SELECT status FROM videos WHERE id = %s", (video_id,))
            row = cur.fetchone()

        assert row is not None, (
            f"Video {video_id} was not found in the database after soft-delete. "
            "Expected it to still exist with status='deleted'."
        )
        assert row[0] == "deleted", (
            f"Expected video status to be 'deleted' after soft-delete, "
            f"got {row[0]!r}."
        )

    def test_video_absent_from_me_videos(
        self,
        seeded_video: dict,
        delete_response: tuple[int, str],  # ensures DELETE ran first
        auth_client: AuthService,
    ):
        """
        After DELETE, the video must not appear in GET /api/me/videos.
        The dashboard query filters out rows with status='deleted'.
        """
        video_id = seeded_video["video_id"]

        status, body = auth_client.get("/api/me/videos")

        assert status == 200, (
            f"GET /api/me/videos returned unexpected status {status}. Body: {body!r}"
        )

        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"GET /api/me/videos returned non-JSON body: {exc}\nBody: {body!r}"
            )

        videos = data if isinstance(data, list) else data.get("videos", [])
        present_ids = {str(v.get("id") or v.get("video_id", "")) for v in videos}

        assert video_id not in present_ids, (
            f"Deleted video {video_id} still appears in GET /api/me/videos response. "
            f"Expected it to be excluded because its status is 'deleted'."
        )
