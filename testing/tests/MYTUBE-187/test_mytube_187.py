"""
MYTUBE-187: GET /api/me/videos — returns correct metadata for authenticated uploader.

Verifies that the /api/me/videos endpoint returns the correct list of videos
owned by the authenticated user, and no videos from other users.

Preconditions
-------------
- User is authenticated with a valid Firebase ID token.
- Multiple videos exist in the system: some owned by the test user,
  others owned by a different user.

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert the test user row via direct DB access (ON CONFLICT DO NOTHING).
3. Insert 3 video rows for the test user and 2 for a different (other) user.
4. Send GET /api/me/videos with Authorization: Bearer <FIREBASE_TEST_TOKEN>.
5. Assert HTTP 200.
6. Assert the response body is a JSON array.
7. Assert all returned videos belong only to the authenticated user.
8. Assert each video entry contains: id, title, status, thumbnail_url,
   view_count, created_at.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN  : Firebase ID token for the test user.
                         Test is skipped when absent.
- FIREBASE_PROJECT_ID  : Firebase project ID required to initialise the
                         verifier.  Test is skipped when absent.
- FIREBASE_TEST_UID    : The firebase_uid stored in the users row that must
                         match the test token (default: test-uid-mytube-187).
- API_BINARY           : Path to the pre-built Go binary
                         (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                         Database connection settings (all have sensible
                         defaults matching the test DB configuration).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- Direct psycopg2 SQL is used for idempotent test-user setup (ON CONFLICT DO NOTHING).
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
- Teardown cleans up all seeded video rows and the other user row.
"""
import json
import os
import subprocess
import sys
import uuid

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18187
_STARTUP_TIMEOUT = 20.0

# Firebase test credentials (required at runtime; test skips when absent).
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# The firebase_uid that the test token belongs to.
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-187")

# RAW_UPLOADS_BUCKET is required by the API binary at startup; a placeholder
# is sufficient here because this test never exercises the upload path.
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

# Test video titles — deterministic and unique to this test suite.
_OWNER_VIDEO_TITLES = [
    "MYTUBE-187 Owner Video Alpha",
    "MYTUBE-187 Owner Video Beta",
    "MYTUBE-187 Owner Video Gamma",
]
_OTHER_VIDEO_TITLES = [
    "MYTUBE-187 Other Video Delta",
    "MYTUBE-187 Other Video Epsilon",
]

# Required fields that every video entry in the response must contain.
_REQUIRED_VIDEO_FIELDS = {"id", "title", "status", "thumbnail_url", "view_count", "created_at"}


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
            "FIREBASE_TEST_TOKEN not set — skipping GET /api/me/videos integration test. "
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
    """Open a direct psycopg2 connection to the test database."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_data(api_server, db_conn):
    """Seed the database with the owner user, 3 owner videos, another user,
    and 2 videos owned by the other user.

    Uses ON CONFLICT DO NOTHING for the owner user so the fixture is idempotent.
    Cleans up all seeded videos and the other user on teardown.

    Returns a dict with:
    - owner_user_id: str
    - owner_video_ids: list[str]
    - other_user_id: str
    - other_video_ids: list[str]
    """
    other_firebase_uid = f"other-user-mytube-187-{uuid.uuid4().hex[:8]}"

    # --- Insert owner user (idempotent) ---
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_TEST_UID, "testuser187"),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        owner_row = cur.fetchone()

    if owner_row is None:
        pytest.fail(
            f"Could not insert or find owner user row for firebase_uid={_FIREBASE_TEST_UID!r}"
        )
    owner_user_id = str(owner_row[0])

    # --- Insert other user ---
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) RETURNING id",
            (other_firebase_uid, f"otheruser187_{other_firebase_uid[-8:]}"),
        )
        other_user_id = str(cur.fetchone()[0])

    # --- Insert owner's videos ---
    owner_video_ids = []
    for title in _OWNER_VIDEO_TITLES:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO videos (uploader_id, title, status) VALUES (%s, %s, %s) RETURNING id",
                (owner_user_id, title, "ready"),
            )
            owner_video_ids.append(str(cur.fetchone()[0]))

    # --- Insert other user's videos ---
    other_video_ids = []
    for title in _OTHER_VIDEO_TITLES:
        with db_conn.cursor() as cur:
            cur.execute(
                "INSERT INTO videos (uploader_id, title, status) VALUES (%s, %s, %s) RETURNING id",
                (other_user_id, title, "ready"),
            )
            other_video_ids.append(str(cur.fetchone()[0]))

    yield {
        "owner_user_id": owner_user_id,
        "owner_video_ids": owner_video_ids,
        "other_user_id": other_user_id,
        "other_video_ids": other_video_ids,
    }

    # --- Teardown: remove seeded videos and other user ---
    all_video_ids = owner_video_ids + other_video_ids
    if all_video_ids:
        with db_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM videos WHERE id = ANY(%s::uuid[])",
                (all_video_ids,),
            )
    with db_conn.cursor() as cur:
        cur.execute(
            "DELETE FROM users WHERE firebase_uid = %s",
            (other_firebase_uid,),
        )


@pytest.fixture(scope="module")
def me_videos_response(api_server, seeded_data):
    """Issue GET /api/me/videos with the Firebase Bearer token and capture the response."""
    status_code, body = api_server.get(
        "/api/me/videos",
        headers={"Authorization": f"Bearer {_FIREBASE_TOKEN}"},
    )
    return {
        "status_code": status_code,
        "body": body,
        "seeded_data": seeded_data,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetMeVideos:
    """GET /api/me/videos with a valid Bearer token must return only the owner's videos."""

    def test_status_code_is_200(self, me_videos_response):
        """The response status must be HTTP 200 OK."""
        assert me_videos_response["status_code"] == 200, (
            f"Expected HTTP 200, got {me_videos_response['status_code']}. "
            f"Response body: {me_videos_response['body']}"
        )

    def test_response_body_is_valid_json(self, me_videos_response):
        """The response body must be parseable JSON."""
        try:
            json.loads(me_videos_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\nBody: {me_videos_response['body']}"
            )

    def test_response_body_is_array(self, me_videos_response):
        """The JSON response must be an array."""
        body = json.loads(me_videos_response["body"])
        assert isinstance(body, list), (
            f"Expected a JSON array, got type: {type(body).__name__}. "
            f"Body: {me_videos_response['body']}"
        )

    def test_response_contains_all_owner_videos(self, me_videos_response):
        """The response must include all videos owned by the authenticated user."""
        videos = json.loads(me_videos_response["body"])
        returned_ids = {v["id"] for v in videos if "id" in v}
        owner_ids = set(me_videos_response["seeded_data"]["owner_video_ids"])
        missing = owner_ids - returned_ids
        assert not missing, (
            f"Response is missing {len(missing)} owner video(s): {missing}. "
            f"Returned ids: {returned_ids}"
        )

    def test_response_excludes_other_user_videos(self, me_videos_response):
        """The response must NOT include any videos belonging to a different user."""
        videos = json.loads(me_videos_response["body"])
        returned_ids = {v["id"] for v in videos if "id" in v}
        other_ids = set(me_videos_response["seeded_data"]["other_video_ids"])
        overlap = returned_ids & other_ids
        assert not overlap, (
            f"Response includes {len(overlap)} video(s) belonging to another user: {overlap}"
        )

    def test_each_video_has_required_fields(self, me_videos_response):
        """Each video entry must contain id, title, status, thumbnail_url, view_count, created_at."""
        videos = json.loads(me_videos_response["body"])
        for i, video in enumerate(videos):
            missing = _REQUIRED_VIDEO_FIELDS - set(video.keys())
            assert not missing, (
                f"Video at index {i} is missing required field(s): {missing}. "
                f"Video keys present: {list(video.keys())}"
            )

    def test_video_id_is_non_empty_string(self, me_videos_response):
        """Each video's 'id' field must be a non-empty string."""
        videos = json.loads(me_videos_response["body"])
        for i, video in enumerate(videos):
            vid_id = video.get("id", "")
            assert isinstance(vid_id, str) and vid_id, (
                f"Expected 'id' to be a non-empty string at index {i}, got: {vid_id!r}"
            )

    def test_video_title_is_non_empty_string(self, me_videos_response):
        """Each video's 'title' field must be a non-empty string."""
        videos = json.loads(me_videos_response["body"])
        for i, video in enumerate(videos):
            title = video.get("title", "")
            assert isinstance(title, str) and title, (
                f"Expected 'title' to be a non-empty string at index {i}, got: {title!r}"
            )

    def test_video_status_is_string(self, me_videos_response):
        """Each video's 'status' field must be a string."""
        videos = json.loads(me_videos_response["body"])
        for i, video in enumerate(videos):
            status = video.get("status", None)
            assert isinstance(status, str), (
                f"Expected 'status' to be a string at index {i}, got: {status!r}"
            )

    def test_video_view_count_is_non_negative_integer(self, me_videos_response):
        """Each video's 'view_count' must be a non-negative integer."""
        videos = json.loads(me_videos_response["body"])
        for i, video in enumerate(videos):
            view_count = video.get("view_count", None)
            assert isinstance(view_count, int) and view_count >= 0, (
                f"Expected 'view_count' to be a non-negative integer at index {i}, "
                f"got: {view_count!r}"
            )

    def test_video_created_at_is_non_empty_string(self, me_videos_response):
        """Each video's 'created_at' must be a non-empty string (ISO timestamp)."""
        videos = json.loads(me_videos_response["body"])
        for i, video in enumerate(videos):
            created_at = video.get("created_at", "")
            assert isinstance(created_at, str) and created_at, (
                f"Expected 'created_at' to be a non-empty string at index {i}, "
                f"got: {created_at!r}"
            )
