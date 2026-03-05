"""
MYTUBE-257: Update video metadata with duplicate tags — tags are deduplicated successfully.

Verifies that the API correctly handles duplicate tag values in the request body
by deduplicating them before storage and in the response.

Objective
---------
Ensure that the API correctly handles duplicate tag values in the request body by
deduplicating them before storage and in the response.

Preconditions
-------------
- User is authenticated and owns a video.

Test steps
----------
1. Send a PUT request to /api/videos/[video_id] with a tag list containing duplicate
   strings (e.g., ["tutorial", "tutorial", "coding"]).
2. Inspect the tags array in the 200 OK response body.
3. Perform a GET request to verify the persisted tags for that video.

Expected Result
---------------
The API returns a 200 OK status. The tags are deduplicated in both the response body
and the database, resulting in a unique list (e.g., ["tutorial", "coding"]).

Environment variables
---------------------
- FIREBASE_TEST_TOKEN  : Firebase ID token for the test user.
                         Test is skipped when absent.
- FIREBASE_PROJECT_ID  : Firebase project ID required to initialise the Firebase
                         verifier. Test is skipped when absent.
- API_BINARY           : Path to the pre-built Go binary
                         (default: <repo_root>/api/mytube-api).
- FIREBASE_TEST_UID    : The firebase_uid stored in the users row that must
                         match the test token (default: test-uid-mytube-257).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                         Database connection settings (all have sensible
                         defaults matching the test DB configuration).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- UserService is used for idempotent test-user seeding (find_by_firebase_uid + create_user).
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

_PORT = 18257
_STARTUP_TIMEOUT = 20.0

# Firebase test credentials (required at runtime; test skips when absent).
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# The firebase_uid that the test token belongs to.
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-257")

# Initial video metadata (state before the PUT).
_INITIAL_TITLE = "Video for Tag Deduplication Test MYTUBE-257"
_INITIAL_DESCRIPTION = "Initial video for testing tag deduplication"
_INITIAL_TAGS = []

# Tags with duplicates submitted via PUT /api/videos/:id.
_DUPLICATE_TAGS = ["tutorial", "tutorial", "coding", "tutorial", "coding"]

# Expected tags after deduplication (sorted or in order, duplicates removed).
# We test for uniqueness and presence of all unique values.
_EXPECTED_UNIQUE_TAGS = ["tutorial", "coding"]


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
            "FIREBASE_TEST_TOKEN not set — skipping PUT /api/videos/:id tag deduplication test. "
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
    user_id = user_svc.create_user(_FIREBASE_TEST_UID, "testuser257")
    return {"id": user_id, "firebase_uid": _FIREBASE_TEST_UID, "username": "testuser257"}


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
        tags=_INITIAL_TAGS,
    )
    return {"id": video_id}


@pytest.fixture(scope="module")
def put_video_response(api_server, seeded_video):
    """Issue PUT /api/videos/:id with duplicate tags; capture the response."""
    payload = json.dumps(
        {
            "title": _INITIAL_TITLE,
            "description": _INITIAL_DESCRIPTION,
            "tags": _DUPLICATE_TAGS,
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
def get_video_response(api_server, put_video_response):
    """Issue GET /api/videos/:id after the PUT to verify persistence of changes."""
    video_id = put_video_response["video_id"]
    status_code, body = api_server.get(f"/api/videos/{video_id}")
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTagDeduplication:
    """PUT /api/videos/:id with duplicate tags must deduplicate them in response and DB."""

    # --- Step 1: PUT response: HTTP status ---

    def test_step_1_put_status_code_is_200(self, put_video_response):
        """Step 1: Send PUT request — response status must be HTTP 200 OK."""
        assert put_video_response["status_code"] == 200, (
            f"Expected HTTP 200, got {put_video_response['status_code']}. "
            f"Response body: {put_video_response['body']}"
        )

    def test_step_1_put_response_is_valid_json(self, put_video_response):
        """Step 1: Response body must be parseable JSON."""
        try:
            json.loads(put_video_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\nBody: {put_video_response['body']}"
            )

    # --- Step 2: PUT response: deduplication verification ---

    def test_step_2_put_response_tags_are_deduplicated(self, put_video_response):
        """Step 2: Inspect tags array — must be deduplicated in response body."""
        body = json.loads(put_video_response["body"])
        tags = body.get("tags", [])

        # Check that the set of tags matches expected (no extra tags, no duplicates, all unique values present)
        assert set(tags) == set(_EXPECTED_UNIQUE_TAGS), (
            f"Response tags do not match expected unique tags. "
            f"Expected: {set(_EXPECTED_UNIQUE_TAGS)}, Got: {set(tags)}"
        )

    # --- Step 3: GET response: persistence verification ---

    def test_step_3_get_status_code_is_200(self, get_video_response):
        """Step 3: Perform GET request — response status must be HTTP 200 OK."""
        assert get_video_response["status_code"] == 200, (
            f"Expected HTTP 200, got {get_video_response['status_code']}. "
            f"Response body: {get_video_response['body']}"
        )

    def test_step_3_get_response_is_valid_json(self, get_video_response):
        """Step 3: GET response body must be parseable JSON."""
        try:
            json.loads(get_video_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"GET response body is not valid JSON: {exc}\nBody: {get_video_response['body']}"
            )

    def test_step_3_persisted_tags_are_deduplicated(self, get_video_response):
        """Step 3: Verify persisted tags — must be deduplicated in database."""
        body = json.loads(get_video_response["body"])
        tags = body.get("tags", [])

        # Check that the set of tags matches expected (no extra tags, no duplicates, all unique values present)
        assert set(tags) == set(_EXPECTED_UNIQUE_TAGS), (
            f"Persisted tags do not match expected unique tags. "
            f"Expected: {set(_EXPECTED_UNIQUE_TAGS)}, Got: {set(tags)}"
        )
