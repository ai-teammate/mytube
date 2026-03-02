"""
MYTUBE-119: Profile video list limit — API returns a maximum of 50 videos.

Verifies that GET /api/users/[username] enforces the MVP limit of 50 videos
per request, even when the user has more than 50 ready videos in the database.

Preconditions
-------------
- A user exists with more than 50 videos, all marked with status "ready".

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a test user row via UserService.
3. Insert 60 "ready" videos for that user via VideoService.
4. Send GET /api/users/<username> (no authentication required).
5. Assert HTTP 200 OK.
6. Parse the JSON response body.
7. Assert the "videos" array contains exactly 50 items.

Environment variables
---------------------
- API_BINARY : Path to the pre-built Go binary
               (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
               Database connection settings (all have sensible defaults
               matching the test DB configuration).

Architecture notes
------------------
- No authentication required; the endpoint is public.
- ApiProcessService handles Go binary lifecycle and HTTP requests.
- UserService and VideoService are used for idempotent test-data setup.
- No hardcoded waits; wait_for_ready() polls /health.
- 60 videos are inserted to exceed the limit and confirm the cap is 50.
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

_PORT = 18119
_STARTUP_TIMEOUT = 20.0

_TEST_USERNAME = "testuser_mytube119"
_TEST_FIREBASE_UID = "test-uid-mytube-119"
_VIDEO_INSERT_COUNT = 60   # more than the expected cap of 50
_EXPECTED_VIDEO_LIMIT = 50


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
        # A placeholder is required to satisfy the startup check; the public
        # endpoint never invokes token verification so no real project is needed.
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID", "dummy-project"),
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
    """Insert a test user with 60 ready videos via UserService and VideoService.

    Uses find_by_firebase_uid to check existence before creating, making the
    fixture idempotent across re-runs. Returns the user's internal UUID string.
    """
    user_svc = UserService(db_conn)
    video_svc = VideoService(db_conn)

    # Upsert the user row via UserService.
    existing_user = user_svc.find_by_firebase_uid(_TEST_FIREBASE_UID)
    if existing_user is not None:
        user_id = existing_user["id"]
    else:
        user_id = user_svc.create_user(_TEST_FIREBASE_UID, _TEST_USERNAME)

    # Count existing ready videos to keep the fixture idempotent.
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM videos WHERE uploader_id = %s AND status = 'ready'",
            (user_id,),
        )
        existing_count = cur.fetchone()[0]

    videos_to_add = _VIDEO_INSERT_COUNT - existing_count
    for i in range(videos_to_add):
        video_svc.insert_video(
            user_id,
            f"Video {existing_count + i + 1} for MYTUBE-119",
            "ready",
        )

    return user_id


@pytest.fixture(scope="module")
def profile_response(api_server, seeded_user):
    """Issue GET /api/users/<username> and capture the response."""
    status_code, body = api_server.get(f"/api/users/{_TEST_USERNAME}")
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProfileVideoListLimit:
    """GET /api/users/:username must cap the videos array at 50 items."""

    def test_status_code_is_200(self, profile_response):
        """The response status must be HTTP 200 OK."""
        assert profile_response["status_code"] == 200, (
            f"Expected HTTP 200, got {profile_response['status_code']}. "
            f"Response body: {profile_response['body']}"
        )

    def test_response_body_is_valid_json(self, profile_response):
        """The response body must be parseable JSON."""
        try:
            json.loads(profile_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(f"Response body is not valid JSON: {exc}\nBody: {profile_response['body']}")

    def test_response_contains_videos_array(self, profile_response):
        """The JSON response must contain a 'videos' key."""
        body = json.loads(profile_response["body"])
        assert "videos" in body, (
            f"Expected 'videos' key in response, got keys: {list(body.keys())}"
        )

    def test_videos_array_is_a_list(self, profile_response):
        """The 'videos' value must be a JSON array."""
        body = json.loads(profile_response["body"])
        assert isinstance(body["videos"], list), (
            f"Expected 'videos' to be a list, got {type(body['videos']).__name__}"
        )

    def test_videos_count_is_exactly_50(self, profile_response):
        """The 'videos' array must contain exactly 50 items (the MVP cap)."""
        body = json.loads(profile_response["body"])
        count = len(body["videos"])
        assert count == _EXPECTED_VIDEO_LIMIT, (
            f"Expected exactly {_EXPECTED_VIDEO_LIMIT} videos, got {count}. "
            f"The API must enforce the 50-video limit even when the user has "
            f"{_VIDEO_INSERT_COUNT} ready videos in the database."
        )
