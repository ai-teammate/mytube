"""
MYTUBE-177: Search pagination — offset and limit parameters correctly slice results.

Objective
---------
Verify that the search API supports offset-based pagination for large result sets.

Preconditions
-------------
At least 25 videos with the same keyword exist in the database.

Test steps
----------
1. Send GET /api/search?q=<keyword>&limit=20&offset=0
2. Send GET /api/search?q=<keyword>&limit=20&offset=20

Expected Result
---------------
- The first request returns exactly 20 matches.
- The second request returns exactly 5 matches (the remaining ones).
- No video IDs overlap between the two result sets.

Environment variables
---------------------
- API_BINARY  : Path to the pre-built Go binary
                (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                Database connection settings.

Architecture notes
------------------
- SearchService encapsulates all /api/search HTTP interaction.
- ApiProcessService manages the Go API subprocess lifecycle.
- The API binary runs migrations on startup; this test only seeds data AFTER
  the server is ready (using a direct psycopg2 connection).
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
"""
import os
import subprocess
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.search_service import SearchService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18077
_STARTUP_TIMEOUT = 30.0

# Unique keyword used to seed and search — unlikely to collide with other data.
_SEARCH_KEYWORD = "paginationtestmytube177"
_TOTAL_VIDEOS = 25
_PAGE_SIZE = 20
_UPLOADER_FIREBASE_UID = "test-uid-mytube-177"
_UPLOADER_USERNAME = "testuser177"


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
    """
    Build (if needed) and start the Go API server.

    The binary runs database migrations on startup, so no pre-seeding happens
    here — data is seeded in the seeded_db fixture AFTER the server is ready.
    """
    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        # RAW_UPLOADS_BUCKET is required by the binary at startup even though
        # the search endpoint never touches GCS. Provide a placeholder value so
        # the process does not exit immediately.
        "RAW_UPLOADS_BUCKET": os.getenv("RAW_UPLOADS_BUCKET", "unused-bucket-mytube-177"),
        # No FIREBASE_PROJECT_ID — the search endpoint is unauthenticated.
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
def seeded_db(api_server, db_config: DBConfig):
    """
    Open a direct psycopg2 connection and seed 25 ready videos after the API
    server (and its migrations) are up.

    Returns the uploader_id so tests can reference it if needed.
    """
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True

    # Insert (or re-use) the uploader user.
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO UPDATE SET username = EXCLUDED.username
            RETURNING id
            """,
            (_UPLOADER_FIREBASE_UID, _UPLOADER_USERNAME),
        )
        uploader_id = str(cur.fetchone()[0])

    # Delete any pre-existing videos seeded by a previous run so the count is
    # deterministic — the keyword is unique to this test, so this is safe.
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM videos WHERE uploader_id = %s AND title LIKE %s",
            (uploader_id, f"{_SEARCH_KEYWORD}%"),
        )

    # Insert exactly 25 ready videos whose titles all contain the keyword.
    with conn.cursor() as cur:
        for i in range(1, _TOTAL_VIDEOS + 1):
            cur.execute(
                """
                INSERT INTO videos (uploader_id, title, status)
                VALUES (%s, %s, 'ready')
                """,
                (uploader_id, f"{_SEARCH_KEYWORD} video {i:02d}"),
            )

    yield uploader_id

    # Teardown: remove seeded videos so the DB is clean for future runs.
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM videos WHERE uploader_id = %s AND title LIKE %s",
            (uploader_id, f"{_SEARCH_KEYWORD}%"),
        )
    conn.close()


@pytest.fixture(scope="module")
def search_service(api_server) -> SearchService:
    """Return a SearchService pointed at the local test API server."""
    return SearchService(base_url=f"http://127.0.0.1:{_PORT}")


@pytest.fixture(scope="module")
def page_one(seeded_db, search_service: SearchService):
    """GET /api/search?q=<keyword>&limit=20&offset=0."""
    return search_service.search(q=_SEARCH_KEYWORD, limit=_PAGE_SIZE, offset=0)


@pytest.fixture(scope="module")
def page_two(seeded_db, search_service: SearchService):
    """GET /api/search?q=<keyword>&limit=20&offset=20."""
    return search_service.search(q=_SEARCH_KEYWORD, limit=_PAGE_SIZE, offset=_PAGE_SIZE)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchPagination:
    """
    Verify that GET /api/search correctly slices results using limit and offset.
    """

    # ---- Page 1 assertions ------------------------------------------------

    def test_page_one_status_is_200(self, page_one):
        """First page request must respond with HTTP 200."""
        assert page_one.status_code == 200, (
            f"Expected HTTP 200 for page 1, got {page_one.status_code}. "
            f"Body: {page_one.raw_body[:500]}"
        )

    def test_page_one_returns_20_results(self, page_one):
        """First page with limit=20 and offset=0 must return exactly 20 items."""
        assert len(page_one.items) == 20, (
            f"Expected 20 items on page 1, got {len(page_one.items)}."
        )

    def test_page_one_all_titles_contain_keyword(self, page_one):
        """Every item on page 1 must have a title matching the search keyword."""
        for item in page_one.items:
            assert _SEARCH_KEYWORD in item.title, (
                f"Unexpected title on page 1 (keyword not present): {item.title!r}"
            )

    # ---- Page 2 assertions ------------------------------------------------

    def test_page_two_status_is_200(self, page_two):
        """Second page request must respond with HTTP 200."""
        assert page_two.status_code == 200, (
            f"Expected HTTP 200 for page 2, got {page_two.status_code}. "
            f"Body: {page_two.raw_body[:500]}"
        )

    def test_page_two_returns_5_results(self, page_two):
        """Second page with limit=20 and offset=20 must return exactly 5 items."""
        assert len(page_two.items) == 5, (
            f"Expected 5 items on page 2, got {len(page_two.items)}."
        )

    def test_page_two_all_titles_contain_keyword(self, page_two):
        """Every item on page 2 must have a title matching the search keyword."""
        for item in page_two.items:
            assert _SEARCH_KEYWORD in item.title, (
                f"Unexpected title on page 2 (keyword not present): {item.title!r}"
            )

    # ---- No-overlap assertion --------------------------------------------

    def test_no_overlap_between_pages(self, page_one, page_two):
        """No video ID must appear in both page 1 and page 2."""
        ids_page_one = {item.id for item in page_one.items}
        ids_page_two = {item.id for item in page_two.items}
        overlap = ids_page_one & ids_page_two
        assert not overlap, (
            f"Found {len(overlap)} overlapping video ID(s) across pages: {overlap}"
        )

    # ---- Combined coverage -----------------------------------------------

    def test_combined_results_cover_all_25_videos(self, page_one, page_two):
        """Pages 1 and 2 together must account for all 25 seeded videos."""
        all_ids = {item.id for item in page_one.items} | {item.id for item in page_two.items}
        assert len(all_ids) == _TOTAL_VIDEOS, (
            f"Expected {_TOTAL_VIDEOS} unique IDs across both pages, got {len(all_ids)}."
        )
