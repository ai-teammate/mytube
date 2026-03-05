"""
MYTUBE-256: Update video metadata with non-existent category — 400 Bad Request returned.

Objective
---------
Verify that the API validates the category_id and returns an error if the category
does not exist in the database.

Preconditions
-------------
- User is authenticated and owns a video.

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a user row via direct DB access using a known firebase_uid.
3. Pre-insert a video row owned by that user with initial metadata.
4. Send PUT /api/videos/:id with Authorization: Bearer <FIREBASE_TEST_TOKEN>
   and a JSON body containing an invalid category_id (999999).
5. Assert HTTP 400 Bad Request is returned.
6. Send GET /api/videos/:id and verify the video metadata is unchanged.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN  : Firebase ID token for the test user.
                         Test is skipped when absent.
- FIREBASE_PROJECT_ID  : Firebase project ID required to initialise the
                         verifier.  Test is skipped when absent.
- API_BINARY           : Path to the pre-built Go binary
                         (default: <repo_root>/api/mytube-api).
- FIREBASE_TEST_UID    : The firebase_uid stored in the users row that must
                         match the test token (default: test-uid-mytube-256).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                         Database connection settings (all have sensible
                         defaults matching the test DB configuration).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- UserService is used for idempotent test-user seeding.
- VideoService is used to seed the initial video row.
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
"""
import json
import os
import subprocess
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.user_service import UserService
from testing.components.services.video_service import VideoService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18256
_STARTUP_TIMEOUT = 20.0

# Firebase test credentials (required at runtime; test skips when absent).
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# The firebase_uid that the test token belongs to.
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-256")

# Initial video metadata (state before the PUT).
_INITIAL_TITLE = "Test Video MYTUBE-256"
_INITIAL_DESCRIPTION = "Initial description for MYTUBE-256"

# Non-existent category ID (should trigger validation error).
_INVALID_CATEGORY_ID = 999999


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials():
    """Skip the entire module when Firebase credentials are not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping PUT /api/videos/:id validation test. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run this test."
        )
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — the API server cannot initialise "
            "the Firebase verifier without this variable."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """Build (if needed) and start the Go API server in a subprocess.

    Yields the ApiProcessService once /health is reachable, then stops the
    process on teardown.
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
        "RAW_UPLOADS_BUCKET": os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads"),
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
    """Open a direct psycopg2 connection to the test database."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_user(api_server, db_conn):
    """Insert a user row with a known firebase_uid; return a dict with the user data."""
    user_svc = UserService(db_conn)
    existing = user_svc.find_by_firebase_uid(_FIREBASE_TEST_UID)
    if existing is not None:
        return existing
    user_id = user_svc.create_user(_FIREBASE_TEST_UID, "testuser256")
    return {"id": user_id, "firebase_uid": _FIREBASE_TEST_UID, "username": "testuser256"}


@pytest.fixture(scope="module")
def seeded_video(seeded_user, db_conn):
    """Insert a video row owned by the test user with initial metadata.

    Returns a dict containing the video id.
    """
    video_svc = VideoService(db_conn)
    video_id = video_svc.insert_video_with_details(
        uploader_id=seeded_user["id"],
        title=_INITIAL_TITLE,
        description=_INITIAL_DESCRIPTION,
        status="ready",
        tags=[],
    )
    return {"id": video_id}


@pytest.fixture(scope="module")
def put_video_with_invalid_category(api_server, seeded_video):
    """Issue PUT /api/videos/:id with invalid category_id; capture the response."""
    payload = json.dumps(
        {
            "title": _INITIAL_TITLE,
            "description": _INITIAL_DESCRIPTION,
            "category_id": _INVALID_CATEGORY_ID,
        }
    ).encode()

    video_id = seeded_video["id"]
    status_code, body = api_server.put(
        f"/api/videos/{video_id}",
        body=payload,
        headers={
            "Authorization": f"Bearer {_FIREBASE_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    return {"status_code": status_code, "body": body, "video_id": video_id}


@pytest.fixture(scope="module")
def get_video_after_failed_update(api_server, put_video_with_invalid_category):
    """Issue GET /api/videos/:id after the failed PUT to verify metadata is unchanged."""
    video_id = put_video_with_invalid_category["video_id"]
    status_code, body = api_server.get(f"/api/videos/{video_id}")
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpdateVideoWithInvalidCategory:
    """PUT /api/videos/:id with non-existent category must return 400 Bad Request."""

    def test_put_returns_400_status_code(self, put_video_with_invalid_category):
        """The response status should be HTTP 400 Bad Request for invalid category_id.
        
        NOTE: Currently returns 500 due to unhandled database foreign key constraint.
        The API should validate category_id before attempting to update.
        """
        assert put_video_with_invalid_category["status_code"] == 400, (
            f"Expected HTTP 400 for invalid category_id, got {put_video_with_invalid_category['status_code']}. "
            f"Response body: {put_video_with_invalid_category['body']}"
        )

    def test_put_response_is_valid_json(self, put_video_with_invalid_category):
        """The 400 response body should be parseable JSON."""
        try:
            json.loads(put_video_with_invalid_category["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\n"
                f"Body: {put_video_with_invalid_category['body']}"
            )

    def test_video_metadata_unchanged_after_failed_update(
        self, get_video_after_failed_update, seeded_video
    ):
        """The video metadata must remain unchanged after the failed PUT."""
        assert get_video_after_failed_update["status_code"] == 200, (
            f"Expected HTTP 200 for GET, got {get_video_after_failed_update['status_code']}. "
            f"Body: {get_video_after_failed_update['body']}"
        )
        
        body = json.loads(get_video_after_failed_update["body"])
        assert body.get("title") == _INITIAL_TITLE, (
            f"Title was modified despite failed PUT. "
            f"Expected {_INITIAL_TITLE!r}, got {body.get('title')!r}"
        )
        assert body.get("description") == _INITIAL_DESCRIPTION, (
            f"Description was modified despite failed PUT. "
            f"Expected {_INITIAL_DESCRIPTION!r}, got {body.get('description')!r}"
        )
