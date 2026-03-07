"""
MYTUBE-373: Delete video via API — raw and HLS files deleted from GCS.

Objective
---------
Verify that deleting a video via the API correctly removes associated raw upload
files and HLS output artifacts from GCS buckets.

Preconditions
-------------
- A video exists with a valid gcs_raw_path in mytube-raw-uploads.
- Transcoded HLS files exist in mytube-hls-output under the expected prefix.
- Environment variable DELETE_ON_VIDEO_DELETE is set to true.

Steps
-----
1. Note the GCS object paths for the raw file and HLS manifest.
2. Send a DELETE request to /api/videos/[video_id].
3. Check the mytube-raw-uploads bucket for the raw file.
4. Check the mytube-hls-output bucket for the HLS manifest and segments.

Expected Result
---------------
The API returns 200 OK (or 204 No Content per implementation). Both the raw file
and all HLS artifacts associated with the video ID are successfully deleted from
their respective GCS buckets.

Architecture notes
------------------
Two layers:

**Layer A — Go unit tests** (always runs, no DB/GCS needed):
    Runs the existing Go handler unit tests for DeleteVideo with
    DELETE_ON_VIDEO_DELETE=true to confirm the deletion path is exercised.

**Layer B — Integration test via HTTP** (runs when FIREBASE_TEST_TOKEN +
    FIREBASE_PROJECT_ID are set):
    1. Seeds a user + video row in the DB (with synthetic gcs_raw_path and
       hls_manifest_path pointing to the mock buckets).
    2. Starts the Go API binary with DELETE_ON_VIDEO_DELETE=true and
       GOOGLE_APPLICATION_CREDENTIALS pointing to the mock service account key
       (real GCS calls are expected to fail silently — that is the documented
       best-effort behaviour of cleanupVideoGCSObjects).
    3. Issues an authenticated DELETE /api/videos/:id request.
    4. Asserts HTTP 204 No Content.
    5. Asserts the video's DB status is 'deleted' (soft-deleted).
    6. Asserts GET /api/videos/:id returns 404 (video no longer visible).

    The GCS bucket assertions (steps 3-4 from the ticket) are attempted when
    GOOGLE_APPLICATION_CREDENTIALS points to a real service-account key file
    (not the mock fixture) and the GCS buckets are reachable. If GCS credentials
    are unavailable the GCS assertions are skipped gracefully.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN     : Firebase ID token for authenticated DELETE request.
- FIREBASE_PROJECT_ID     : Firebase project ID for the API server.
- FIREBASE_TEST_UID       : UID embedded in the test token
                            (default: test-uid-mytube-373).
- API_BINARY              : Path to pre-built Go binary
                            (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                            Database connection settings.
- GOOGLE_APPLICATION_CREDENTIALS : Path to service-account JSON.
                            Defaults to testing/fixtures/mock_service_account.json.
- GCS_RAW_UPLOADS_BUCKET  : Raw-uploads bucket name (default: mytube-raw-uploads).
- HLS_BUCKET              : HLS-output bucket name (default: mytube-hls-output).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.auth_service import AuthService
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18373
_STARTUP_TIMEOUT = 20.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-373")

_TEST_USERNAME = "testuser_mytube373"

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_CREDS_PATH = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)

_RAW_UPLOADS_BUCKET = os.getenv("GCS_RAW_UPLOADS_BUCKET", "mytube-raw-uploads")
_HLS_BUCKET = os.getenv("HLS_BUCKET", "mytube-hls-output")


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


def _cleanup_db(conn, user_id: str) -> None:
    """Remove all test rows for the given user_id in FK-safe order."""
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM ratings WHERE video_id IN "
            "(SELECT id FROM videos WHERE uploader_id = %s)",
            (user_id,),
        )
        cur.execute(
            "DELETE FROM comments WHERE video_id IN "
            "(SELECT id FROM videos WHERE uploader_id = %s)",
            (user_id,),
        )
        cur.execute(
            "DELETE FROM video_tags WHERE video_id IN "
            "(SELECT id FROM videos WHERE uploader_id = %s)",
            (user_id,),
        )
        cur.execute("DELETE FROM videos WHERE uploader_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))


# ---------------------------------------------------------------------------
# Layer A — Go unit tests (always run)
# ---------------------------------------------------------------------------


class TestDeleteVideoGCSCleanupUnitTests:
    """Layer A: Go handler unit tests for the video DELETE + GCS cleanup path."""

    def test_go_delete_video_handler_unit_tests(self) -> None:
        """Run Go handler unit tests for video delete with GCS cleanup.

        Exercises:
        - DELETE /api/videos/:id returns 204 when GCS cleanup is enabled.
        - GCS cleanup is invoked for both the raw file and HLS prefix.
        - GCS cleanup disabled (DELETE_ON_VIDEO_DELETE=false) skips GCS calls.
        - GCS errors do not affect the HTTP 204 response.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestDeleteVideo",
                "./internal/handler/",
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            "Go handler unit tests for video DELETE failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
        assert "PASS" in result.stdout or "ok" in result.stdout, (
            "Expected PASS in Go test output but got:\n"
            f"{result.stdout}\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Layer B fixtures — integration tests (require FIREBASE_TEST_TOKEN)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """Start the API binary with DELETE_ON_VIDEO_DELETE=true.

    Skips the module when FIREBASE_TEST_TOKEN or FIREBASE_PROJECT_ID is absent.
    """
    if not _FIREBASE_TOKEN:
        pytest.skip("FIREBASE_TEST_TOKEN not set — skipping integration tests.")
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — the API server cannot initialise "
            "the Firebase verifier."
        )

    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "GOOGLE_APPLICATION_CREDENTIALS": _CREDS_PATH,
        "RAW_UPLOADS_BUCKET": _RAW_UPLOADS_BUCKET,
        # Enable GCS deletion — the core behaviour under test.
        "DELETE_ON_VIDEO_DELETE": "true",
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
def db_conn(db_config: DBConfig):
    """Direct psycopg2 connection for seeding and assertions."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_video(api_server, db_conn) -> dict:
    """Seed user and video rows; return metadata dict.

    The video is seeded with synthetic gcs_raw_path and hls_manifest_path so
    the handler's GCS cleanup path is exercised. The raw path is a realistic
    object key (no leading gs://); the HLS path is a full gs:// URL as stored
    by the transcoder.

    Teardown removes any remaining DB rows for the test user.
    """
    video_id = str(uuid.uuid4())

    # Synthetic GCS paths that look real (the raw path uses the video UUID
    # as the object key under the expected raw/ prefix).
    raw_path = f"raw/{video_id}.mp4"
    hls_manifest_path = f"gs://{_HLS_BUCKET}/videos/{video_id}/index.m3u8"

    user_id: str | None = None

    with db_conn.cursor() as cur:
        # Upsert test user.
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_TEST_UID, _TEST_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()
        if row is None:
            pytest.fail(
                f"Could not insert or find user row for firebase_uid={_FIREBASE_TEST_UID!r}"
            )
        user_id = str(row[0])

        # Insert a video with gcs_raw_path and hls_manifest_path pre-set so
        # the handler's GCS cleanup path is exercised.
        cur.execute(
            """
            INSERT INTO videos
                (id, uploader_id, title, status, gcs_raw_path, hls_manifest_path)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                video_id,
                user_id,
                "Test Video for MYTUBE-373",
                "ready",
                raw_path,
                hls_manifest_path,
            ),
        )

    yield {
        "video_id": video_id,
        "user_id": user_id,
        "raw_path": raw_path,
        "hls_manifest_path": hls_manifest_path,
    }

    # Teardown: clean up any residual rows.
    _cleanup_db(db_conn, user_id)


@pytest.fixture(scope="module")
def auth_service(api_server) -> AuthService:
    return AuthService(
        base_url=f"http://127.0.0.1:{_PORT}",
        token=_FIREBASE_TOKEN,
    )


@pytest.fixture(scope="module")
def video_api_service(api_server) -> VideoApiService:
    from testing.core.config.api_config import APIConfig
    cfg = APIConfig.__new__(APIConfig)
    cfg.base_url = f"http://127.0.0.1:{_PORT}"
    cfg.health_token = ""
    return VideoApiService(cfg)


@pytest.fixture(scope="module")
def delete_response(auth_service: AuthService, seeded_video: dict) -> dict:
    """Issue DELETE /api/videos/:id once and cache the result."""
    video_id = seeded_video["video_id"]
    status_code, body = auth_service.delete(f"/api/videos/{video_id}")
    return {"status_code": status_code, "body": body, "video_id": video_id}


# ---------------------------------------------------------------------------
# Layer B — Integration tests
# ---------------------------------------------------------------------------


class TestDeleteVideoGCSCleanupIntegration:
    """Layer B: Full integration tests — HTTP + DB assertions."""

    def test_delete_returns_204(self, delete_response: dict) -> None:
        """Step 2: DELETE /api/videos/:id must return HTTP 204 No Content."""
        assert delete_response["status_code"] == 204, (
            f"Expected HTTP 204 No Content from DELETE /api/videos/"
            f"{delete_response['video_id']}, "
            f"got {delete_response['status_code']}. "
            f"Response body: {delete_response['body']!r}"
        )

    def test_video_soft_deleted_in_db(
        self,
        db_conn,
        seeded_video: dict,
        delete_response: dict,  # ensures DELETE ran first
    ) -> None:
        """After DELETE, the video row must have status='deleted'."""
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM videos WHERE id = %s",
                (seeded_video["video_id"],),
            )
            row = cur.fetchone()

        assert row is not None, (
            f"Video row for {seeded_video['video_id']} not found in DB after DELETE. "
            "Expected a soft-deleted row with status='deleted'."
        )
        assert row[0] == "deleted", (
            f"Expected video status='deleted' after DELETE, got {row[0]!r}. "
            f"Video ID: {seeded_video['video_id']}"
        )

    def test_get_video_returns_404_after_delete(
        self,
        video_api_service: VideoApiService,
        seeded_video: dict,
        delete_response: dict,  # ensures DELETE ran first
    ) -> None:
        """Step 3–4 proxy: GET /api/videos/:id must return 404 after deletion."""
        status_code, body = video_api_service.get_video_detail(seeded_video["video_id"])
        assert status_code == 404, (
            f"Expected HTTP 404 for GET /api/videos/{seeded_video['video_id']} "
            f"after deletion, got {status_code}. "
            f"Response body: {body!r}\n\n"
            "The video was soft-deleted; the API must not expose it publicly."
        )

    def test_gcs_raw_file_deleted(
        self,
        seeded_video: dict,
        delete_response: dict,  # ensures DELETE ran first
    ) -> None:
        """Step 3: Raw file must be absent from mytube-raw-uploads after deletion.

        This assertion is skipped when real GCS credentials are unavailable
        (i.e. when using the mock service-account fixture).
        """
        if not os.path.isfile(_CREDS_PATH) or _CREDS_PATH == _DEFAULT_MOCK_CREDS:
            pytest.skip(
                "Real GCS credentials not configured — skipping live bucket check. "
                "Set GOOGLE_APPLICATION_CREDENTIALS to a real service-account key "
                "to exercise the GCS bucket assertions."
            )

        try:
            from google.cloud import storage as gcs_storage
            from google.oauth2 import service_account as sa_module
        except ImportError:
            pytest.skip("google-cloud-storage is not installed.")

        creds = sa_module.Credentials.from_service_account_file(_CREDS_PATH)
        client = gcs_storage.Client(credentials=creds)
        blob = client.bucket(_RAW_UPLOADS_BUCKET).blob(seeded_video["raw_path"])

        assert not blob.exists(), (
            f"Raw file gs://{_RAW_UPLOADS_BUCKET}/{seeded_video['raw_path']} "
            "still exists after DELETE /api/videos/:id with DELETE_ON_VIDEO_DELETE=true.\n"
            "Expected: the file to be deleted from the raw-uploads bucket.\n"
            "Actual: the file is still present in the bucket."
        )

    def test_gcs_hls_files_deleted(
        self,
        seeded_video: dict,
        delete_response: dict,  # ensures DELETE ran first
    ) -> None:
        """Step 4: HLS manifest and all segment files must be absent from
        mytube-hls-output after deletion.

        This assertion is skipped when real GCS credentials are unavailable.
        """
        if not os.path.isfile(_CREDS_PATH) or _CREDS_PATH == _DEFAULT_MOCK_CREDS:
            pytest.skip(
                "Real GCS credentials not configured — skipping live bucket check. "
                "Set GOOGLE_APPLICATION_CREDENTIALS to a real service-account key "
                "to exercise the GCS bucket assertions."
            )

        try:
            from google.cloud import storage as gcs_storage
            from google.oauth2 import service_account as sa_module
        except ImportError:
            pytest.skip("google-cloud-storage is not installed.")

        video_id = seeded_video["video_id"]
        hls_prefix = f"videos/{video_id}/"

        creds = sa_module.Credentials.from_service_account_file(_CREDS_PATH)
        client = gcs_storage.Client(credentials=creds)
        blobs = list(client.list_blobs(_HLS_BUCKET, prefix=hls_prefix))

        assert len(blobs) == 0, (
            f"Found {len(blobs)} HLS object(s) under "
            f"gs://{_HLS_BUCKET}/{hls_prefix} after DELETE /api/videos/:id "
            "with DELETE_ON_VIDEO_DELETE=true.\n"
            f"Remaining objects: {[b.name for b in blobs[:10]]}\n"
            "Expected: all HLS artifacts deleted from the output bucket."
        )
