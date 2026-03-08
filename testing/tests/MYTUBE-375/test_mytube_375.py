"""
MYTUBE-375: Delete video with DELETE_ON_VIDEO_DELETE=false — GCS files retained.

Objective
---------
Verify that the automatic GCS cleanup can be disabled via environment variables
for debugging purposes.

Preconditions
-------------
- Environment variable DELETE_ON_VIDEO_DELETE is set to false.
- A video exists with associated GCS files.

Steps
-----
1. Send a DELETE request to /api/videos/[video_id].
2. Verify the database record status is updated to 'deleted'.
3. Check the GCS buckets for the raw and HLS files.

Expected Result
---------------
The video status is updated in the database, but the files in GCS are NOT
deleted, as the auto-deletion flag is disabled.

Layer A — Go unit tests (always runs; no external services required)
--------------------------------------------------------------------
Runs TestDeleteVideo_GCSCleanupDisabled_DoesNotDelete from the Go handler
test suite to verify that when DELETE_ON_VIDEO_DELETE=false, the handler
does not invoke the GCS object deleter at all.

Layer B — HTTP integration test (runs when DB is reachable + Firebase token present)
-------------------------------------------------------------------------------------
Starts the full Go API server with DELETE_ON_VIDEO_DELETE=false, seeds a user
and video row with GCS path values, issues a DELETE /api/videos/:id request
with a real Firebase token, and asserts:
- HTTP 204 No Content
- DB record status transitions to 'deleted'
- GCS raw file still exists in the bucket (when GOOGLE_APPLICATION_CREDENTIALS is set)

Environment Variables
---------------------
API_BINARY                      Path to pre-built Go binary
                                (default: <repo_root>/api/mytube-api).
FIREBASE_TEST_TOKEN             Firebase ID token. Layer B is skipped when absent.
FIREBASE_PROJECT_ID             Firebase project ID (default: ai-native-478811).
FIREBASE_TEST_UID               UID embedded in the test token
                                (default: ci-test-user-001).
GOOGLE_APPLICATION_CREDENTIALS  Path to GCS service-account JSON (optional).
                                When set, a real file is uploaded to GCS before the
                                DELETE and its continued existence is verified after.
GCP_PROJECT_ID                  GCP project ID (default: ai-native-478811).
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE
                                Database connection settings.

Architecture
------------
- Layer A delegates entirely to Go unit tests via subprocess.
- Layer B uses ApiProcessService to manage the Go API binary lifecycle.
- VideoService (DB layer) seeds and queries video rows.
- GCSService verifies object presence in GCS when credentials are available.
- AuthService issues authenticated HTTP requests using the injected token.
- DBConfig and APIConfig from testing/core/config/ for environment config.
- No hardcoded URLs, credentials, or GCS paths.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.core.config.gcs_config import GCSConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.auth_service import AuthService
from testing.components.services.gcs_service import GCSService
from testing.components.services.video_service import VideoService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18375
_STARTUP_TIMEOUT = 30.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "ai-native-478811")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

_GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "ai-native-478811")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

_TEST_USERNAME = "testuser_mytube375"
_TEST_VIDEO_TITLE = "Test Video MYTUBE-375"

# GCS object name prefix for test objects — namespaced to this ticket.
_GCS_TEST_PREFIX = "test-data/MYTUBE-375/"


# ===========================================================================
# Helpers
# ===========================================================================


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


def _run_go_test(pattern: str) -> subprocess.CompletedProcess:
    """Run Go unit tests matching *pattern* in the handler package."""
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-run", pattern, "./internal/handler/"],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )


def _postgres_available(db_config: DBConfig) -> bool:
    """Return True if PostgreSQL is reachable."""
    try:
        import psycopg2
        conn = psycopg2.connect(db_config.dsn())
        conn.close()
        return True
    except Exception:
        return False


def _gcs_credentials_available() -> bool:
    """Return True if real (non-mock) GCS credentials appear to be configured."""
    creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not creds or not os.path.isfile(creds):
        return False
    # Mock credentials used in tests are identified by their project_id
    try:
        import json
        with open(creds) as f:
            data = json.load(f)
        return data.get("project_id") not in ("mock-project-id", "")
    except Exception:
        return False


# ===========================================================================
# Layer A — Go unit tests (always run; no external services required)
# ===========================================================================


class TestDeleteVideoGCSCleanupDisabledGoUnit:
    """Go unit test: DELETE_ON_VIDEO_DELETE=false must not invoke GCS deletion."""

    def test_gcs_cleanup_disabled_does_not_delete(self) -> None:
        """TestDeleteVideo_GCSCleanupDisabled_DoesNotDelete must pass.

        Verifies that when DELETE_ON_VIDEO_DELETE env var is 'false', the
        DELETE /api/videos/:id handler:
        1. Returns HTTP 204 No Content (soft-deletion succeeded).
        2. Does NOT call the GCS ObjectDeleter — neither DeleteObject nor
           DeletePrefix is invoked.

        This is the unit-level guarantee that the flag is respected.
        """
        result = _run_go_test("TestDeleteVideo_GCSCleanupDisabled_DoesNotDelete")
        assert result.returncode == 0, (
            "Go unit test TestDeleteVideo_GCSCleanupDisabled_DoesNotDelete failed.\n"
            "This means the handler calls GCS deletion even when "
            "DELETE_ON_VIDEO_DELETE=false, violating the debug-mode contract.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ===========================================================================
# Layer B — HTTP integration test
# Requires DB access and FIREBASE_TEST_TOKEN; skipped gracefully when absent.
# ===========================================================================


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def gcs_config() -> GCSConfig:
    return GCSConfig()


@pytest.fixture(scope="module")
def require_db_and_token(db_config: DBConfig):
    """Skip Layer B when DB is unreachable or Firebase token is missing."""
    if not _firebase_token_present():
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping Layer B integration tests. "
            "Generate a token via the Firebase REST API and export FIREBASE_TEST_TOKEN."
        )
    if not _postgres_available(db_config):
        pytest.skip(
            f"PostgreSQL is not reachable at {db_config.host}:{db_config.port} — "
            "skipping Layer B integration tests."
        )


def _firebase_token_present() -> bool:
    return bool(os.getenv("FIREBASE_TEST_TOKEN", "").strip())


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig, require_db_and_token):
    """Start the Go API server with DELETE_ON_VIDEO_DELETE=false.

    Using the NopObjectDeleter path (no real GCS client at binary level).
    The binary still initialises its GCS dependency from env vars, so we
    point GOOGLE_APPLICATION_CREDENTIALS at the mock JSON.
    """
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
        # The flag under test: GCS cleanup disabled.
        "DELETE_ON_VIDEO_DELETE": "false",
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
def db_conn(db_config: DBConfig, require_db_and_token):
    """Open a direct psycopg2 connection for seeding and DB assertions."""
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed.")

    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def gcs_test_object(gcs_config: GCSConfig):
    """Upload a minimal test file to GCS raw-uploads bucket and yield its object name.

    Only runs when real GCS credentials are available. Cleans up in teardown.
    If GCS is not available, yields None (GCS assertions are skipped).
    """
    if not _gcs_credentials_available():
        yield None
        return

    try:
        gcs_svc = GCSService(gcs_config)
        object_name = gcs_svc.upload_test_object(gcs_config.raw_uploads_bucket)
        yield object_name
    except Exception as exc:
        # GCS upload failed; skip GCS assertions but continue DB tests.
        pytest.skip(f"Could not upload test object to GCS: {exc}")
        return

    try:
        gcs_svc.delete_object(gcs_config.raw_uploads_bucket, object_name)
    except Exception:
        pass  # Best-effort cleanup; object may already be gone.


@pytest.fixture(scope="module")
def seeded_video(api_server, db_conn, gcs_test_object):
    """Seed a user and a video with GCS paths; yield metadata; clean up on teardown.

    If gcs_test_object is available (real GCS upload succeeded), the video row
    uses that object name as gcs_raw_path so Layer B can assert the file persists.
    Otherwise a synthetic (non-existent) path is used — sufficient for the
    DELETE_ON_VIDEO_DELETE=false test since the API won't try to delete it anyway.
    """
    import psycopg2

    raw_path = gcs_test_object if gcs_test_object else f"test-data/MYTUBE-375/fake_{uuid.uuid4().hex}.mp4"
    hls_path = f"gs://mytube-hls-output/videos/fake-video-id-375/index.m3u8"

    with db_conn.cursor() as cur:
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

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status, gcs_raw_path, hls_manifest_path)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, _TEST_VIDEO_TITLE, "ready", raw_path, hls_path),
        )
        video_id = str(cur.fetchone()[0])

    yield {
        "video_id": video_id,
        "user_id": user_id,
        "raw_path": raw_path,
        "hls_path": hls_path,
        "gcs_test_object": gcs_test_object,
    }

    # Teardown: remove residual DB rows (the API soft-deletes, so the row still
    # exists with status='deleted'; we hard-delete it here for test hygiene).
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))


@pytest.fixture(scope="module")
def delete_response(api_server, seeded_video) -> tuple[int, str]:
    """Issue DELETE /api/videos/:id (authenticated) and return (status_code, body).

    Uses the FIREBASE_TEST_TOKEN from environment.
    """
    base_url = f"http://127.0.0.1:{_PORT}"
    token = os.getenv("FIREBASE_TEST_TOKEN", "")
    auth_svc = AuthService(base_url=base_url, token=token)
    video_id = seeded_video["video_id"]
    return auth_svc.delete(f"/api/videos/{video_id}")


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------


class TestDeleteVideoGCSCleanupDisabledIntegration:
    """DELETE /api/videos/:id with DELETE_ON_VIDEO_DELETE=false.

    DB status must become 'deleted'; GCS files must NOT be deleted.
    """

    def test_delete_returns_204(
        self, delete_response: tuple[int, str], seeded_video: dict
    ) -> None:
        """DELETE /api/videos/:id must return HTTP 204 No Content.

        A 204 confirms the video was soft-deleted by the API.  Any other status
        indicates the delete operation failed, meaning the test precondition
        (a valid video owned by the test user) was not met or authentication failed.
        """
        status_code, body = delete_response
        assert status_code == 204, (
            f"Expected HTTP 204 No Content from DELETE /api/videos/{seeded_video['video_id']}, "
            f"got {status_code}. "
            f"Response body: {body!r}. "
            "Check that FIREBASE_TEST_TOKEN is valid and the video is owned by FIREBASE_TEST_UID."
        )

    def test_db_status_is_deleted(
        self, delete_response: tuple[int, str], seeded_video: dict, db_conn
    ) -> None:
        """Video record status in DB must be 'deleted' after the DELETE request.

        This is the primary assertion from the ticket: the database record must
        reflect the deletion even when GCS cleanup is disabled.
        """
        video_id = seeded_video["video_id"]
        video_svc = VideoService(db_conn)
        video_data = video_svc.get_video_by_id(video_id)
        assert video_data is not None, (
            f"Video row for id={video_id!r} not found in DB after DELETE. "
            "Expected a soft-deleted row with status='deleted'."
        )
        assert video_data["status"] == "deleted", (
            f"Expected video status='deleted' after DELETE /api/videos/{video_id}, "
            f"but got status={video_data['status']!r}. "
            "The API soft-delete should update the status column to 'deleted'."
        )

    def test_gcs_raw_file_still_exists(
        self,
        delete_response: tuple[int, str],
        seeded_video: dict,
        gcs_config: GCSConfig,
    ) -> None:
        """GCS raw file must NOT be deleted when DELETE_ON_VIDEO_DELETE=false.

        Only runs when real GCS credentials are available (GOOGLE_APPLICATION_CREDENTIALS
        points to a non-mock service account and GCS upload in seeded_video succeeded).
        Skipped gracefully when GCS is not configured — the Go unit test in Layer A
        already covers this behaviour at the unit level.
        """
        gcs_object = seeded_video.get("gcs_test_object")
        if not gcs_object:
            pytest.skip(
                "No real GCS test object available (either GOOGLE_APPLICATION_CREDENTIALS "
                "is not set or points to a mock SA). "
                "GCS retention is verified at unit level by "
                "TestDeleteVideo_GCSCleanupDisabled_DoesNotDelete."
            )

        try:
            gcs_svc = GCSService(gcs_config)
        except Exception as exc:
            pytest.skip(f"GCSService unavailable: {exc}")

        exists = gcs_svc.blob_exists(gcs_config.raw_uploads_bucket, gcs_object)

        assert exists, (
            f"GCS object gs://{gcs_config.raw_uploads_bucket}/{gcs_object} was deleted "
            f"after DELETE /api/videos/{seeded_video['video_id']} even though "
            "DELETE_ON_VIDEO_DELETE=false. "
            "The API must NOT delete GCS files when this flag is disabled."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
