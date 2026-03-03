"""
MYTUBE-202: GET /api/videos/:id/comments — comments returned in descending order
with a 100 item cap.

Objective
---------
Verify the retrieval of a flat list of comments ordered by newest first and capped at 100.

Preconditions
-------------
- A video has more than 100 comments.

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a user, a 'ready' video, and 105 comments with explicit, increasing
   timestamps via direct DB access.
3. Send GET /api/videos/:id/comments (public endpoint — no auth token required).
4. Assert HTTP 200.
5. Assert the response array contains exactly 100 items.
6. Assert the first item has the most recent created_at (i.e. items are DESC).
7. Assert every item has author.username (non-empty string) and author.avatar_url key.

Environment variables
---------------------
- FIREBASE_PROJECT_ID : Firebase project ID required to initialise the API verifier.
                        Test is skipped when absent.
- API_BINARY          : Path to the pre-built Go binary
                        (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                        Database connection settings (all have sensible defaults).

Architecture notes
------------------
- ApiProcessService handles the Go subprocess lifecycle.
- CommentService encapsulates the bulk-insert of test comments.
- The GET /api/videos/:id/comments endpoint is public; no Firebase token is needed
  in the request — only FIREBASE_PROJECT_ID is required for server initialisation.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.comment_service import CommentService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18202
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "test-placeholder-bucket-202")

# Stable identifiers so repeated runs don't accumulate stale rows.
_FIREBASE_UID = "test-uid-mytube-202"
_USERNAME = "testuser202"

# Base timestamp for the 105 seeded comments. Comments will have
# created_at = _BASE_TIME + timedelta(seconds=i) for i in 0..104.
# Comment 104 (index 104) is the newest and must be first in the response.
_BASE_TIME = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
_COMMENT_COUNT = 105


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
def require_firebase_project_id():
    """Skip the entire module when FIREBASE_PROJECT_ID is not available."""
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — skipping GET /api/videos/:id/comments test. "
            "Set FIREBASE_PROJECT_ID (e.g. ai-native-478811) to run this test."
        )


@pytest.fixture(scope="module", autouse=True)
def require_db(db_config: DBConfig):
    """Skip the entire module when the PostgreSQL database is not reachable."""
    try:
        conn = psycopg2.connect(db_config.dsn(), connect_timeout=3)
        conn.close()
    except Exception as exc:
        pytest.skip(
            f"PostgreSQL database not reachable ({exc}). "
            "Ensure a PostgreSQL service is running and DB_HOST/DB_PORT/DB_USER/"
            "DB_PASSWORD/DB_NAME are configured."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """Build (if needed), start the Go API server, and wait for readiness."""
    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        # RAW_UPLOADS_BUCKET is required by the binary at startup even though
        # the comments endpoint does not use GCS.
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
def db_conn(db_config: DBConfig):
    """Open a direct psycopg2 connection for test-data setup."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_data(api_server, db_conn):
    """
    Insert a user, a 'ready' video, and 105 comments with explicit, increasing
    timestamps so order and cap can be verified deterministically.

    Returns a dict with:
      - video_id       : UUID string of the seeded video
      - most_recent_at : datetime of the newest comment (expected first in response)
    """
    # ---- user ---------------------------------------------------------------
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_UID, _USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_UID,),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(f"Could not insert or find user for firebase_uid={_FIREBASE_UID!r}")

    user_id = str(row[0])

    # ---- video (status must be 'ready' for the Exists check) ----------------
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status)
            VALUES (%s, %s, 'ready')
            RETURNING id
            """,
            (user_id, "Test Video MYTUBE-202"),
        )
        video_id = str(cur.fetchone()[0])

    # ---- 105 comments with ascending timestamps -----------------------------
    comment_svc = CommentService(db_conn)
    comment_svc.insert_bulk_comments(
        video_id=video_id,
        author_id=user_id,
        count=_COMMENT_COUNT,
        base_time=_BASE_TIME,
    )

    from datetime import timedelta
    most_recent_at = _BASE_TIME + timedelta(seconds=_COMMENT_COUNT - 1)

    return {
        "video_id": video_id,
        "most_recent_at": most_recent_at,
    }


@pytest.fixture(scope="module")
def comments_response(api_server, seeded_data):
    """Issue GET /api/videos/:id/comments and return status + parsed body."""
    video_id = seeded_data["video_id"]
    status_code, body = api_server.get(f"/api/videos/{video_id}/comments")
    return {
        "status_code": status_code,
        "items": json.loads(body),
        "most_recent_at": seeded_data["most_recent_at"],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetCommentsEndpoint:
    """GET /api/videos/:id/comments must return 200, exactly 100 items, newest first,
    with full author details on every item."""

    def test_status_code_is_200(self, comments_response):
        """The response status must be HTTP 200 OK."""
        assert comments_response["status_code"] == 200, (
            f"Expected HTTP 200, got {comments_response['status_code']}. "
            f"First 200 chars of body: {str(comments_response['items'])[:200]}"
        )

    def test_returns_exactly_100_items(self, comments_response):
        """The response array must contain exactly 100 comments (cap enforced)."""
        items = comments_response["items"]
        assert isinstance(items, list), (
            f"Expected a JSON array, got: {type(items).__name__}"
        )
        assert len(items) == 100, (
            f"Expected exactly 100 comments, got {len(items)}"
        )

    def test_items_ordered_newest_first(self, comments_response):
        """All items must be in descending created_at order (newest first)."""
        items = comments_response["items"]

        # Parse every timestamp and verify strict descending order.
        timestamps = []
        for item in items:
            raw = item.get("created_at", "")
            # Go serialises time.Time as RFC3339; Python 3.11+ handles the Z suffix.
            ts = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            timestamps.append(ts)

        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], (
                f"Order violated at index {i}: "
                f"{timestamps[i].isoformat()} is not >= {timestamps[i + 1].isoformat()}"
            )

        # The very first item must match the most recent seeded timestamp.
        expected = comments_response["most_recent_at"]
        actual = timestamps[0]
        assert actual == expected, (
            f"Expected first item created_at={expected.isoformat()}, "
            f"got {actual.isoformat()}"
        )

    def test_each_item_has_author_username(self, comments_response):
        """Every comment must include a non-empty author.username string."""
        items = comments_response["items"]
        for i, item in enumerate(items):
            author = item.get("author", {})
            assert "username" in author, (
                f"Item {i}: missing 'author.username' key. Keys: {list(author.keys())}"
            )
            assert isinstance(author["username"], str) and author["username"], (
                f"Item {i}: 'author.username' must be a non-empty string, "
                f"got: {author['username']!r}"
            )

    def test_each_item_has_author_avatar_url_key(self, comments_response):
        """Every comment must include the author.avatar_url key (value may be null)."""
        items = comments_response["items"]
        for i, item in enumerate(items):
            author = item.get("author", {})
            assert "avatar_url" in author, (
                f"Item {i}: missing 'author.avatar_url' key. Keys: {list(author.keys())}"
            )
