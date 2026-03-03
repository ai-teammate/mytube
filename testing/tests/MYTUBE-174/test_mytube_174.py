"""
MYTUBE-174: Search videos by keyword — matching ready videos returned.

Verifies that GET /api/search?q=<keyword> performs full-text search on video
titles and exact match on tags, returning only videos with status='ready'.

Preconditions
-------------
- Videos exist with various statuses ('ready', 'processing') and specific
  keywords in titles/tags.

Test steps
----------
1. Seed test data:
   - A 'ready'      video with title containing "dragon"       (title match)
   - A 'ready'      video with tag "sunset"                    (tag match)
   - A 'processing' video with title containing "dragon"       (must be excluded)
2. GET /api/search?q=dragon  → must include the ready title-match video.
3. GET /api/search?q=sunset  → must include the ready tag-match video.
4. GET /api/search?q=dragon  → must NOT include the processing video.

Environment variables
---------------------
- API_BINARY           : Path to pre-built Go binary
                         (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                         Database connection settings.

Architecture notes
------------------
- GET /api/search is a public endpoint; no Firebase token is required.
- ApiProcessService handles Go binary lifecycle and HTTP requests.
- UserService is used for idempotent test-user setup.
- VideoService.insert_video_with_details() seeds videos with tags.
- All HTTP calls and DB seeding are performed once in a module-scoped fixture
  (search_results) so individual test methods receive deterministic results.
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
from testing.components.services.video_service import VideoService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18174
_STARTUP_TIMEOUT = 20.0

_TEST_FIREBASE_UID = "test-uid-mytube-174"
_TEST_USERNAME = "testuser_mytube174"

# Titles used for seeding — unique enough to avoid collisions with real data.
_TITLE_READY_DRAGON = "Dragon Quest Adventure mytube174"
_TITLE_PROCESSING_DRAGON = "Dragon Rising Processing mytube174"
_TITLE_READY_SUNSET = "Sunset Over the Mountains mytube174"
_TAG_SUNSET = "sunset"


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
        # Search is a public endpoint; Firebase validation is not exercised.
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID", "dummy-project"),
        # Placeholder; search does not touch GCS.
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
def seeded_videos(api_server, db_conn):
    """Seed the three test videos needed by this test module.

    Returns a dict with the IDs of each seeded video:
    {
        "ready_dragon_id":      <uuid str>,
        "ready_sunset_id":      <uuid str>,
        "processing_dragon_id": <uuid str>,
    }

    Uses ON CONFLICT DO NOTHING-style idempotency for the test user row.
    Fresh video rows are always inserted so tests are deterministic across
    multiple runs.
    """
    user_svc = UserService(db_conn)

    existing_user = user_svc.find_by_firebase_uid(_TEST_FIREBASE_UID)
    if existing_user is not None:
        user_id = existing_user["id"]
    else:
        user_id = user_svc.create_user(_TEST_FIREBASE_UID, _TEST_USERNAME)

    video_svc = VideoService(db_conn)

    # Ready video matched by title full-text search for "dragon".
    ready_dragon_id = video_svc.insert_video_with_details(
        uploader_id=user_id,
        title=_TITLE_READY_DRAGON,
        description="A ready dragon video for MYTUBE-174",
        status="ready",
        tags=[],
    )

    # Ready video matched by exact tag "sunset".
    ready_sunset_id = video_svc.insert_video_with_details(
        uploader_id=user_id,
        title=_TITLE_READY_SUNSET,
        description="A ready sunset video for MYTUBE-174",
        status="ready",
        tags=[_TAG_SUNSET],
    )

    # Processing video with "dragon" in title — must be excluded from results.
    processing_dragon_id = video_svc.insert_video_with_details(
        uploader_id=user_id,
        title=_TITLE_PROCESSING_DRAGON,
        description="A processing dragon video for MYTUBE-174",
        status="processing",
        tags=[],
    )

    return {
        "ready_dragon_id": ready_dragon_id,
        "ready_sunset_id": ready_sunset_id,
        "processing_dragon_id": processing_dragon_id,
    }


@pytest.fixture(scope="module")
def search_results(api_server, seeded_videos):
    """Execute all three search requests once and return captured results.

    Steps:
      1. GET /api/search?q=dragon  — title full-text match.
      2. GET /api/search?q=sunset  — exact tag match.

    Returns a dict so individual test methods can assert against
    pre-computed, deterministic data without re-issuing HTTP requests.
    """
    status_dragon, body_dragon = api_server.get("/api/search?q=dragon")
    status_sunset, body_sunset = api_server.get("/api/search?q=sunset")

    return {
        "seeded": seeded_videos,
        "dragon_status": status_dragon,
        "dragon_body": body_dragon,
        "sunset_status": status_sunset,
        "sunset_body": body_sunset,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchByTitleMatch:
    """GET /api/search?q=dragon — full-text title match returns the ready video."""

    def test_returns_200(self, search_results):
        """Search by keyword must return HTTP 200."""
        assert search_results["dragon_status"] == 200, (
            f"Expected HTTP 200, got {search_results['dragon_status']}. "
            f"Body: {search_results['dragon_body']}"
        )

    def test_response_is_json_array(self, search_results):
        """Response body must be a valid JSON array."""
        try:
            data = json.loads(search_results["dragon_body"])
        except json.JSONDecodeError as exc:
            pytest.fail(f"Response is not valid JSON: {exc}\nBody: {search_results['dragon_body']}")
        assert isinstance(data, list), (
            f"Expected a JSON array, got {type(data).__name__}: {search_results['dragon_body']}"
        )

    def test_ready_dragon_video_is_present(self, search_results):
        """The ready 'dragon' video must appear in the results."""
        data = json.loads(search_results["dragon_body"])
        ids = [item.get("id") for item in data]
        assert search_results["seeded"]["ready_dragon_id"] in ids, (
            f"Expected ready dragon video {search_results['seeded']['ready_dragon_id']!r} "
            f"in results, got ids: {ids}"
        )

    def test_processing_dragon_video_is_absent(self, search_results):
        """The processing 'dragon' video must NOT appear in the results."""
        data = json.loads(search_results["dragon_body"])
        ids = [item.get("id") for item in data]
        assert search_results["seeded"]["processing_dragon_id"] not in ids, (
            f"Processing video {search_results['seeded']['processing_dragon_id']!r} "
            f"must be excluded from search results, but was found. ids: {ids}"
        )

    def test_every_result_has_required_fields(self, search_results):
        """Each video card in the response must contain the required fields."""
        data = json.loads(search_results["dragon_body"])
        required_fields = {"id", "title", "view_count", "uploader_username", "created_at"}
        for item in data:
            missing = required_fields - set(item.keys())
            assert not missing, (
                f"Video card is missing fields {missing}: {item}"
            )


class TestSearchByTagMatch:
    """GET /api/search?q=sunset — exact tag match returns the ready video."""

    def test_returns_200(self, search_results):
        """Search by tag must return HTTP 200."""
        assert search_results["sunset_status"] == 200, (
            f"Expected HTTP 200, got {search_results['sunset_status']}. "
            f"Body: {search_results['sunset_body']}"
        )

    def test_response_is_json_array(self, search_results):
        """Response body must be a valid JSON array."""
        try:
            data = json.loads(search_results["sunset_body"])
        except json.JSONDecodeError as exc:
            pytest.fail(f"Response is not valid JSON: {exc}\nBody: {search_results['sunset_body']}")
        assert isinstance(data, list), (
            f"Expected a JSON array, got {type(data).__name__}: {search_results['sunset_body']}"
        )

    def test_ready_sunset_video_is_present(self, search_results):
        """The ready video tagged 'sunset' must appear in the results."""
        data = json.loads(search_results["sunset_body"])
        ids = [item.get("id") for item in data]
        assert search_results["seeded"]["ready_sunset_id"] in ids, (
            f"Expected ready sunset video {search_results['seeded']['ready_sunset_id']!r} "
            f"in results, got ids: {ids}"
        )

    def test_every_result_has_required_fields(self, search_results):
        """Each video card in the response must contain the required fields."""
        data = json.loads(search_results["sunset_body"])
        required_fields = {"id", "title", "view_count", "uploader_username", "created_at"}
        for item in data:
            missing = required_fields - set(item.keys())
            assert not missing, (
                f"Video card is missing fields {missing}: {item}"
            )


class TestSearchStatusFiltering:
    """Only 'ready' videos must be returned regardless of keyword match."""

    def test_no_non_ready_videos_in_dragon_results(self, search_results, db_conn):
        """All videos returned for 'dragon' must have status='ready' in the DB."""
        data = json.loads(search_results["dragon_body"])
        if not data:
            return  # No results to check; prior tests already assert presence.
        ids = [item["id"] for item in data if "id" in item]
        if not ids:
            return
        # Query the DB to verify every returned video has status='ready'.
        placeholders = ",".join(["%s"] * len(ids))
        with db_conn.cursor() as cur:
            cur.execute(
                f"SELECT id, status FROM videos WHERE id IN ({placeholders})",
                ids,
            )
            rows = cur.fetchall()
        non_ready = [(str(row[0]), row[1]) for row in rows if row[1] != "ready"]
        assert not non_ready, (
            f"Non-ready videos found in search results: {non_ready}"
        )

    def test_no_non_ready_videos_in_sunset_results(self, search_results, db_conn):
        """All videos returned for 'sunset' must have status='ready' in the DB."""
        data = json.loads(search_results["sunset_body"])
        if not data:
            return
        ids = [item["id"] for item in data if "id" in item]
        if not ids:
            return
        placeholders = ",".join(["%s"] * len(ids))
        with db_conn.cursor() as cur:
            cur.execute(
                f"SELECT id, status FROM videos WHERE id IN ({placeholders})",
                ids,
            )
            rows = cur.fetchall()
        non_ready = [(str(row[0]), row[1]) for row in rows if row[1] != "ready"]
        assert not non_ready, (
            f"Non-ready videos found in search results: {non_ready}"
        )
