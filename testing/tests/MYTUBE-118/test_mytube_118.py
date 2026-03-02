"""
MYTUBE-118: Profile video list filtering — only videos with "ready" status are displayed.

Verifies that processing or failed videos are excluded from the public profile
video list returned by GET /api/users/:username.

Preconditions
-------------
- User "creator" has 1 video with status "ready" and 1 video with status "processing".

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a "creator" user and two videos (one "ready", one "processing") via direct DB access.
3. Send GET /api/users/creator.
4. Assert HTTP 200 and that the videos array contains exactly the "ready" video and
   excludes the "processing" video.

Environment variables
---------------------
- FIREBASE_PROJECT_ID : Firebase project ID (required to start the API server).
                        Test is skipped when absent.
- API_BINARY          : Path to the pre-built Go binary
                        (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                        Database connection settings (all have sensible
                        defaults matching the test DB configuration).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- Direct psycopg2 SQL is used for idempotent test-data setup (ON CONFLICT DO NOTHING).
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
- No Firebase token required — GET /api/users/:username is a public endpoint.
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


def _db_is_reachable(config: DBConfig) -> bool:
    """Return True if a PostgreSQL connection can be established."""
    try:
        conn = psycopg2.connect(config.dsn(), connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18118
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# Deterministic test data
_CREATOR_USERNAME = "creator"
_CREATOR_FIREBASE_UID = "test-uid-mytube-118-creator"
_READY_VIDEO_TITLE = "Ready Video MYTUBE-118"
_PROCESSING_VIDEO_TITLE = "Processing Video MYTUBE-118"


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
def require_infrastructure():
    """Skip the entire module when required infrastructure is unavailable."""
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — the API server cannot initialise "
            "the Firebase verifier without this variable."
        )
    cfg = DBConfig()
    if not _db_is_reachable(cfg):
        pytest.skip(
            f"PostgreSQL is not reachable at {cfg.host}:{cfg.port} — "
            "skipping integration test. Start the test database to run this test."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """
    Build (if needed) and start the Go API server in a subprocess.

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
def seeded_creator(api_server, db_conn):
    """
    Insert a "creator" user and two videos (one "ready", one "processing").

    Uses ON CONFLICT DO NOTHING so the fixture is safe to re-run.

    Returns a dict with the creator user's id, ready_video_id, and
    processing_video_id.
    """
    with db_conn.cursor() as cur:
        # Insert creator user (idempotent)
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_CREATOR_FIREBASE_UID, _CREATOR_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_CREATOR_FIREBASE_UID,),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_CREATOR_FIREBASE_UID!r}"
        )

    creator_id = str(row[0])

    with db_conn.cursor() as cur:
        # Insert "ready" video (idempotent by title + uploader)
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status)
            VALUES (%s, %s, 'ready')
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (creator_id, _READY_VIDEO_TITLE),
        )
        ready_row = cur.fetchone()
        if ready_row is None:
            # Row already existed; fetch its id
            cur.execute(
                "SELECT id FROM videos WHERE uploader_id = %s AND title = %s",
                (creator_id, _READY_VIDEO_TITLE),
            )
            ready_row = cur.fetchone()
        ready_video_id = str(ready_row[0])

        # Insert "processing" video (idempotent by title + uploader)
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status)
            VALUES (%s, %s, 'processing')
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (creator_id, _PROCESSING_VIDEO_TITLE),
        )
        processing_row = cur.fetchone()
        if processing_row is None:
            cur.execute(
                "SELECT id FROM videos WHERE uploader_id = %s AND title = %s",
                (creator_id, _PROCESSING_VIDEO_TITLE),
            )
            processing_row = cur.fetchone()
        processing_video_id = str(processing_row[0])

    return {
        "creator_id": creator_id,
        "ready_video_id": ready_video_id,
        "processing_video_id": processing_video_id,
    }


@pytest.fixture(scope="module")
def profile_response(api_server, seeded_creator):
    """Issue GET /api/users/creator and capture the response."""
    status_code, body = api_server.get("/api/users/creator", headers=None)
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProfileVideoListFiltering:
    """GET /api/users/creator must return only videos with status='ready'."""

    def test_status_code_is_200(self, profile_response):
        """The response status must be HTTP 200 OK."""
        assert profile_response["status_code"] == 200, (
            f"Expected HTTP 200, got {profile_response['status_code']}. "
            f"Response body: {profile_response['body']}"
        )

    def test_response_body_contains_videos_array(self, profile_response):
        """The JSON body must contain a 'videos' key with an array value."""
        body = json.loads(profile_response["body"])
        assert "videos" in body, (
            f"Expected 'videos' key in response, got keys: {list(body.keys())}"
        )
        assert isinstance(body["videos"], list), (
            f"Expected 'videos' to be a list, got: {type(body['videos'])}"
        )

    def test_ready_video_is_present(self, profile_response, seeded_creator):
        """The 'ready' video must appear in the videos array."""
        body = json.loads(profile_response["body"])
        video_ids = [v["id"] for v in body.get("videos", [])]
        assert seeded_creator["ready_video_id"] in video_ids, (
            f"Expected ready video id {seeded_creator['ready_video_id']!r} "
            f"in videos array, but got ids: {video_ids}"
        )

    def test_processing_video_is_excluded(self, profile_response, seeded_creator):
        """The 'processing' video must NOT appear in the videos array."""
        body = json.loads(profile_response["body"])
        video_ids = [v["id"] for v in body.get("videos", [])]
        assert seeded_creator["processing_video_id"] not in video_ids, (
            f"Processing video id {seeded_creator['processing_video_id']!r} "
            f"was unexpectedly included in the videos array: {video_ids}"
        )

    def test_videos_have_required_fields(self, profile_response):
        """Each video object must contain id, title, thumbnail_url, view_count, created_at."""
        body = json.loads(profile_response["body"])
        for video in body.get("videos", []):
            for field in ("id", "title", "thumbnail_url", "view_count", "created_at"):
                assert field in video, (
                    f"Expected field '{field}' in video object, got keys: {list(video.keys())}"
                )
