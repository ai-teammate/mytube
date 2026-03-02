"""
MYTUBE-147: Increment video view count — count is updated atomically on page load.

Verifies that accessing GET /api/videos/:id increments the view_count in the
database by 1 on each request, and that the API response reflects the
post-increment value.

Preconditions
-------------
- A video exists with a known initial view_count (seeded as 10).

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a test user and a video with view_count = 10 via direct DB access.
3. Send the first GET /api/videos/<id> request.
4. Query the database directly to verify view_count is now 11.
5. Assert the API response body contains view_count = 11.
6. Send a second GET /api/videos/<id> request.
7. Query the database directly to verify view_count is now 12.
8. Assert the API response body contains view_count = 12.

Environment variables
---------------------
- API_BINARY : Path to the pre-built Go binary
               (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
               Database connection settings (all have sensible defaults
               matching the test DB configuration).

Architecture notes
------------------
- No authentication required; GET /api/videos/:id is a public endpoint.
- ApiProcessService handles Go binary lifecycle and HTTP requests.
- UserService is used for idempotent test-user setup.
- Direct psycopg2 is used to seed the video with a known view_count and to
  query the view_count after each API call.
- Both API requests and DB snapshots are captured in a single module-scoped
  fixture (view_count_sequence) so every test method receives a deterministic,
  pre-computed result set without triggering additional increments.
- No hardcoded waits; wait_for_ready() polls /health.
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18147
_STARTUP_TIMEOUT = 20.0

_TEST_FIREBASE_UID = "test-uid-mytube-147"
_TEST_USERNAME = "testuser_mytube147"
_INITIAL_VIEW_COUNT = 10


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


def _get_view_count(conn, video_id: str) -> int:
    """Query the database for the current view_count of the given video."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT view_count FROM videos WHERE id = %s",
            (video_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"No video found with id={video_id!r}")
    return int(row[0])


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
        # A placeholder is sufficient; the public endpoint never invokes
        # Firebase token verification.
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID", "dummy-project"),
        # RAW_UPLOADS_BUCKET is required by the API binary at startup.
        # A placeholder is fine because this test only calls the public
        # GET /api/videos/:id endpoint, which does not touch GCS.
        "RAW_UPLOADS_BUCKET": os.getenv("RAW_UPLOADS_BUCKET", "dummy-bucket"),
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
def seeded_video(api_server, db_conn):
    """Insert a test user and a video with view_count = _INITIAL_VIEW_COUNT.

    Uses ON CONFLICT DO NOTHING for the user row (idempotent). A fresh video
    row is always inserted so the initial view_count is exactly
    _INITIAL_VIEW_COUNT regardless of previous test runs.

    Returns the video's UUID string.
    """
    user_svc = UserService(db_conn)

    # Upsert the user row.
    existing_user = user_svc.find_by_firebase_uid(_TEST_FIREBASE_UID)
    if existing_user is not None:
        user_id = existing_user["id"]
    else:
        user_id = user_svc.create_user(_TEST_FIREBASE_UID, _TEST_USERNAME)

    # Insert a fresh video with the known initial view_count.
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status, view_count)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (user_id, "Test Video MYTUBE-147", "ready", _INITIAL_VIEW_COUNT),
        )
        video_id = str(cur.fetchone()[0])

    return video_id


@pytest.fixture(scope="module")
def view_count_sequence(api_server, db_conn, seeded_video):
    """Execute the full test sequence once and capture all results.

    Steps performed (in order):
      1. Record the initial DB view_count (must be _INITIAL_VIEW_COUNT).
      2. Issue the first GET /api/videos/<id> — increments count to 11.
      3. Record the DB view_count after the first request.
      4. Issue the second GET /api/videos/<id> — increments count to 12.
      5. Record the DB view_count after the second request.

    Returns a dict with all captured values so individual test methods can
    assert against pre-computed, deterministic data without triggering
    additional increments.
    """
    db_before = _get_view_count(db_conn, seeded_video)

    first_status, first_body = api_server.get(f"/api/videos/{seeded_video}")
    db_after_first = _get_view_count(db_conn, seeded_video)

    second_status, second_body = api_server.get(f"/api/videos/{seeded_video}")
    db_after_second = _get_view_count(db_conn, seeded_video)

    return {
        "video_id": seeded_video,
        "db_before": db_before,
        "first_status": first_status,
        "first_body": first_body,
        "db_after_first": db_after_first,
        "second_status": second_status,
        "second_body": second_body,
        "db_after_second": db_after_second,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestViewCountIncrement:
    """GET /api/videos/:id must increment view_count by 1 on each request."""

    # --- Precondition ---

    def test_initial_db_view_count_is_10(self, view_count_sequence):
        """Sanity check: the seeded video must start with view_count = 10."""
        assert view_count_sequence["db_before"] == _INITIAL_VIEW_COUNT, (
            f"Expected initial view_count={_INITIAL_VIEW_COUNT}, "
            f"got {view_count_sequence['db_before']}."
        )

    # --- First request ---

    def test_first_request_returns_200(self, view_count_sequence):
        """The first GET /api/videos/:id must return HTTP 200 OK."""
        assert view_count_sequence["first_status"] == 200, (
            f"Expected HTTP 200, got {view_count_sequence['first_status']}. "
            f"Response body: {view_count_sequence['first_body']}"
        )

    def test_first_request_response_is_valid_json(self, view_count_sequence):
        """The response body from the first request must be parseable JSON."""
        try:
            json.loads(view_count_sequence["first_body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\n"
                f"Body: {view_count_sequence['first_body']}"
            )

    def test_first_request_response_view_count_is_11(self, view_count_sequence):
        """The JSON response from the first GET must contain view_count = 11."""
        data = json.loads(view_count_sequence["first_body"])
        view_count = data.get("view_count")
        assert view_count == _INITIAL_VIEW_COUNT + 1, (
            f"Expected view_count={_INITIAL_VIEW_COUNT + 1} in first response, "
            f"got {view_count!r}. Response: {view_count_sequence['first_body']}"
        )

    def test_first_request_db_view_count_is_11(self, view_count_sequence):
        """After the first GET, the database view_count must be 11."""
        assert view_count_sequence["db_after_first"] == _INITIAL_VIEW_COUNT + 1, (
            f"Expected DB view_count={_INITIAL_VIEW_COUNT + 1} after first GET, "
            f"got {view_count_sequence['db_after_first']}."
        )

    # --- Second request ---

    def test_second_request_returns_200(self, view_count_sequence):
        """The second GET /api/videos/:id must return HTTP 200 OK."""
        assert view_count_sequence["second_status"] == 200, (
            f"Expected HTTP 200, got {view_count_sequence['second_status']}. "
            f"Response body: {view_count_sequence['second_body']}"
        )

    def test_second_request_response_is_valid_json(self, view_count_sequence):
        """The response body from the second request must be parseable JSON."""
        try:
            json.loads(view_count_sequence["second_body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\n"
                f"Body: {view_count_sequence['second_body']}"
            )

    def test_second_request_response_view_count_is_12(self, view_count_sequence):
        """The JSON response from the second GET must contain view_count = 12."""
        data = json.loads(view_count_sequence["second_body"])
        view_count = data.get("view_count")
        assert view_count == _INITIAL_VIEW_COUNT + 2, (
            f"Expected view_count={_INITIAL_VIEW_COUNT + 2} in second response, "
            f"got {view_count!r}. Response: {view_count_sequence['second_body']}"
        )

    def test_second_request_db_view_count_is_12(self, view_count_sequence):
        """After the second GET, the database view_count must be 12."""
        assert view_count_sequence["db_after_second"] == _INITIAL_VIEW_COUNT + 2, (
            f"Expected DB view_count={_INITIAL_VIEW_COUNT + 2} after second GET, "
            f"got {view_count_sequence['db_after_second']}."
        )

    # --- Field validation ---

    def test_view_count_field_is_present_in_response(self, view_count_sequence):
        """The GET /api/videos/:id response must include a 'view_count' field."""
        data = json.loads(view_count_sequence["first_body"])
        assert "view_count" in data, (
            f"Expected 'view_count' key in response, got keys: {list(data.keys())}"
        )

    def test_view_count_field_is_integer(self, view_count_sequence):
        """The 'view_count' field in the response must be an integer."""
        data = json.loads(view_count_sequence["first_body"])
        view_count = data.get("view_count")
        assert isinstance(view_count, int), (
            f"Expected 'view_count' to be an int, "
            f"got {type(view_count).__name__}: {view_count!r}"
        )
