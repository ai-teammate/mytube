"""
MYTUBE-288: Retrieve video metadata — category_id is included in response.

Objective
---------
Verify that the GET /api/videos/:id endpoint includes the ``category_id`` field
in the response body when the video has a category assigned.

Preconditions
-------------
A video exists in the database with a specific ``category_id`` assigned.

Steps
-----
1. Send a GET request to /api/videos/:id for the video ID.
2. Inspect the JSON response body.

Expected Result
---------------
The API returns a 200 OK status.  The response body contains the
``category_id`` field, and its value matches the one stored in the database.

Layer A — Go unit tests (always runs; no DB or Firebase required)
-----------------------------------------------------------------
Runs TestNewVideoHandler_GET_CategoryID_IncludedInResponse and
TestNewVideoHandler_GET_CategoryID_NilWhenNotSet from the Go handler test
suite to verify the handler serialises ``category_id`` correctly.

Layer B — HTTP integration test (runs when DB is reachable)
-----------------------------------------------------------
Starts the full Go API server, seeds a user and video row with a specific
``category_id``, issues a GET /api/videos/:id request, and asserts:
- HTTP 200 status
- ``category_id`` field is present in the response body
- ``category_id`` value matches the seeded value

Environment Variables
---------------------
API_BINARY              Path to the pre-built Go binary
                        (default: <repo_root>/api/mytube-api).
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE
                        Database connection settings (Layer B).
FIREBASE_PROJECT_ID     Firebase project (Layer B; default: "ai-native-478811").
GOOGLE_APPLICATION_CREDENTIALS
                        Path to GCS service-account JSON
                        (Layer B; falls back to testing/fixtures/mock_service_account.json).
RAW_UPLOADS_BUCKET      GCS bucket name (Layer B; default: "mytube-raw-uploads").

Architecture
------------
- VideoApiService (API service component) for GET /api/videos/:id.
- ApiProcessService for spinning up the Go binary under test.
- DBConfig and APIConfig from testing/core/config/ for environment config.
- No hardcoded URLs, credentials, or category IDs.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

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
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18288
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "ai-native-478811")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-288")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

_TEST_USERNAME = "testuser288"
_TEST_VIDEO_TITLE = "Test Video MYTUBE-288"
_TEST_CATEGORY_ID = 3  # Use a common category ID present in all environments


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
    """Return True if PostgreSQL is reachable at the configured host/port."""
    try:
        import psycopg2

        conn = psycopg2.connect(db_config.dsn())
        conn.close()
        return True
    except Exception:
        return False


# ===========================================================================
# Layer A — Go unit tests (always run; no external services required)
# ===========================================================================


class TestVideoHandler_CategoryID_GoUnit:
    """Go unit tests verifying that category_id serialisation is correct."""

    def test_category_id_included_in_response(self) -> None:
        """TestNewVideoHandler_GET_CategoryID_IncludedInResponse must pass.

        Verifies that when a video has a non-nil category_id, the GET
        /api/videos/:id handler includes that field in the JSON response
        with the correct value.
        """
        result = _run_go_test("TestNewVideoHandler_GET_CategoryID_IncludedInResponse")
        assert result.returncode == 0, (
            f"Go unit test TestNewVideoHandler_GET_CategoryID_IncludedInResponse "
            f"failed — the handler does not include category_id in the response.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_category_id_nil_when_not_set(self) -> None:
        """TestNewVideoHandler_GET_CategoryID_NilWhenNotSet must pass.

        Verifies that when a video has no category assigned (category_id is
        NULL), the handler returns null for the category_id field — it must
        never be omitted entirely from the response.
        """
        result = _run_go_test("TestNewVideoHandler_GET_CategoryID_NilWhenNotSet")
        assert result.returncode == 0, (
            f"Go unit test TestNewVideoHandler_GET_CategoryID_NilWhenNotSet "
            f"failed — the handler does not handle null category_id correctly.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ===========================================================================
# Layer B — HTTP integration test
# Requires a reachable PostgreSQL database; skipped gracefully when absent.
# ===========================================================================


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def require_db(db_config: DBConfig):
    """Skip Layer B tests when PostgreSQL is not reachable."""
    if not _postgres_available(db_config):
        pytest.skip(
            f"PostgreSQL is not reachable at {db_config.host}:{db_config.port} — "
            "skipping Layer B integration tests. "
            "Ensure DB_HOST/DB_PORT/DB_USER/DB_PASSWORD/DB_NAME are set and "
            "the database is running."
        )


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig, require_db):
    """Build (if needed) and start the Go API server; yield it; stop on teardown."""
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
def db_conn(db_config: DBConfig, require_db):
    """Open a direct psycopg2 connection to the test database."""
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed — skipping Layer B integration test.")

    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_video(api_server, db_conn):
    """Seed a user and a video with category_id; yield video_id; clean up on teardown."""
    import psycopg2

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
            INSERT INTO videos (uploader_id, title, status, category_id)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, _TEST_VIDEO_TITLE, "ready", _TEST_CATEGORY_ID),
        )
        video_id = str(cur.fetchone()[0])

    yield {"video_id": video_id, "category_id": _TEST_CATEGORY_ID}

    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))


@pytest.fixture(scope="module")
def video_response(api_server, seeded_video) -> dict:
    """GET /api/videos/:id for the seeded video; return parsed JSON body."""
    api_config = APIConfig.__new__(APIConfig)
    api_config.base_url = f"http://127.0.0.1:{_PORT}"
    api_config.health_token = ""

    svc = VideoApiService(api_config)
    video_id = seeded_video["video_id"]
    data = svc.get_video(video_id)
    if data is None:
        pytest.fail(
            f"GET /api/videos/{video_id} returned None — the endpoint may be "
            f"unreachable or returned a non-200 response."
        )
    return data


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------


class TestVideoMetadataCategoryID:
    """GET /api/videos/:id must include category_id matching the stored value."""

    def test_status_code_is_200(self, video_response: dict, seeded_video: dict) -> None:
        """GET /api/videos/:id must return HTTP 200 OK.

        This is a precondition check — if the fixture already yielded a dict
        (i.e. VideoApiService.get_video did not return None), the status was 200.
        """
        assert video_response is not None, (
            f"GET /api/videos/{seeded_video['video_id']} did not return a response. "
            "Expected HTTP 200 OK with a JSON body."
        )

    def test_category_id_field_present(self, video_response: dict, seeded_video: dict) -> None:
        """Response body must contain the category_id key."""
        assert "category_id" in video_response, (
            f"Expected 'category_id' field in GET /api/videos/{seeded_video['video_id']} "
            f"response body, but it was absent. "
            f"Response keys: {list(video_response.keys())}. "
            f"Full response: {json.dumps(video_response)}"
        )

    def test_category_id_is_not_none(self, video_response: dict, seeded_video: dict) -> None:
        """category_id in the response must not be null when the video has a category assigned."""
        category_id = video_response.get("category_id")
        assert category_id is not None, (
            f"Expected 'category_id' to be non-null in response for video "
            f"{seeded_video['video_id']} (seeded with category_id={_TEST_CATEGORY_ID}), "
            f"but got null. Full response: {json.dumps(video_response)}"
        )

    def test_category_id_matches_stored_value(
        self, video_response: dict, seeded_video: dict
    ) -> None:
        """category_id in the response must match the value stored in the database."""
        expected = seeded_video["category_id"]
        actual = video_response.get("category_id")
        assert actual == expected, (
            f"category_id mismatch for video {seeded_video['video_id']}: "
            f"expected {expected!r} (from DB seed), got {actual!r}. "
            f"Full response: {json.dumps(video_response)}"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
