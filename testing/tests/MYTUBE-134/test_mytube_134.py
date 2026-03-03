"""
MYTUBE-134: Create video metadata via POST /api/videos — metadata saved and signed URL returned.

Verifies that an authenticated user can successfully submit video metadata and
receive a GCS signed URL for upload.

Preconditions
-------------
- User is authenticated with a valid Firebase ID token.
- The user record exists in the database (pre-seeded via fixture).
- RAW_UPLOADS_BUCKET is set (defaults to "mytube-raw-uploads").

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a user row via direct DB access using the known firebase_uid.
3. Send POST /api/videos with:
   - Authorization: Bearer <FIREBASE_TEST_TOKEN>
   - Content-Type: application/json
   - JSON body: title, description, category_id, tags, mime_type
4. Assert HTTP 201 Created.
5. Assert the JSON body contains video_id (UUID) and upload_url (GCS signed PUT URL).
6. Assert the video row exists in the database with status "pending".

Environment variables
---------------------
- FIREBASE_TEST_TOKEN  : Firebase ID token for the test user.
                         Test is skipped when absent.
- FIREBASE_PROJECT_ID  : Firebase project ID required to initialise the
                         verifier.  Test is skipped when absent.
- FIREBASE_TEST_UID    : The firebase_uid stored in the users row that must
                         match the test token (default: test-uid-mytube-134).
- API_BINARY           : Path to the pre-built Go binary
                         (default: <repo_root>/api/mytube-api).
- RAW_UPLOADS_BUCKET   : GCS bucket for raw video uploads
                         (default: "mytube-raw-uploads").
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                         Database connection settings (all have sensible
                         defaults matching the test DB configuration).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- Direct psycopg2 SQL is used for idempotent test-user setup (ON CONFLICT DO NOTHING).
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
- post() method on ApiProcessService follows the same pattern as put().
"""
import json
import os
import re
import subprocess
import sys

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

_PORT = 18134
_STARTUP_TIMEOUT = 20.0

# Firebase test credentials (required at runtime; test skips when absent).
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# The firebase_uid that the test token belongs to.
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-134")

# GCS raw uploads bucket.
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

# Test video metadata payload.
_VIDEO_TITLE = "Test Video MYTUBE-134"
_VIDEO_DESCRIPTION = "Integration test for POST /api/videos"
_VIDEO_TAGS = ["tutorial", "tech"]
_VIDEO_MIME_TYPE = "video/mp4"

# GCS signed URL pattern: starts with https://storage.googleapis.com/ or https://storage.cloud.google.com/
_GCS_SIGNED_URL_RE = re.compile(r"^https://storage\.googleapis\.com/.+X-Goog-Signature=.+$")

# UUID pattern.
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


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


def _is_uuid(value: str) -> bool:
    """Return True if *value* looks like a UUID."""
    return bool(_UUID_RE.match(value))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials():
    """Skip the entire module when Firebase credentials are not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping POST /api/videos integration test. "
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
def seeded_user(api_server, db_conn):
    """Insert a user row with a known firebase_uid before the POST is issued.

    Uses ON CONFLICT DO NOTHING so the fixture is idempotent.
    Returns a dict with the user's id, firebase_uid, and username.
    """
    username = "testuser134"

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_TEST_UID, username),
        )
        cur.execute(
            "SELECT id, firebase_uid, username FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_FIREBASE_TEST_UID!r}"
        )

    return {
        "id": str(row[0]),
        "firebase_uid": row[1],
        "username": row[2],
    }


@pytest.fixture(scope="module")
def post_video_response(api_server, seeded_user):
    """Issue POST /api/videos with a valid payload and capture the response."""
    payload = json.dumps(
        {
            "title": _VIDEO_TITLE,
            "description": _VIDEO_DESCRIPTION,
            "tags": _VIDEO_TAGS,
            "mime_type": _VIDEO_MIME_TYPE,
        }
    ).encode()

    status_code, body = api_server.post(
        "/api/videos",
        body=payload,
        headers={
            "Authorization": f"Bearer {_FIREBASE_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateVideoMetadata:
    """POST /api/videos with a valid payload and Bearer token must return 201."""

    def test_status_code_is_201(self, post_video_response):
        """The response status must be HTTP 201 Created."""
        assert post_video_response["status_code"] == 201, (
            f"Expected HTTP 201, got {post_video_response['status_code']}. "
            f"Response body: {post_video_response['body']}"
        )

    def test_response_body_is_valid_json(self, post_video_response):
        """The response body must be parseable JSON."""
        try:
            json.loads(post_video_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\nBody: {post_video_response['body']}"
            )

    def test_response_contains_video_id(self, post_video_response):
        """The JSON response must contain a 'video_id' key."""
        body = json.loads(post_video_response["body"])
        assert "video_id" in body, (
            f"Expected 'video_id' key in response, got keys: {list(body.keys())}"
        )

    def test_video_id_is_uuid(self, post_video_response):
        """The 'video_id' value must be a valid UUID string."""
        body = json.loads(post_video_response["body"])
        video_id = body.get("video_id", "")
        assert _is_uuid(video_id), (
            f"Expected 'video_id' to be a UUID, got: {video_id!r}"
        )

    def test_response_contains_upload_url(self, post_video_response):
        """The JSON response must contain an 'upload_url' key."""
        body = json.loads(post_video_response["body"])
        assert "upload_url" in body, (
            f"Expected 'upload_url' key in response, got keys: {list(body.keys())}"
        )

    def test_upload_url_is_non_empty_string(self, post_video_response):
        """The 'upload_url' must be a non-empty string."""
        body = json.loads(post_video_response["body"])
        upload_url = body.get("upload_url", "")
        assert isinstance(upload_url, str) and upload_url, (
            f"Expected a non-empty string for 'upload_url', got: {upload_url!r}"
        )

    def test_upload_url_is_gcs_signed_url(self, post_video_response):
        """The 'upload_url' must be a GCS V4 signed PUT URL."""
        body = json.loads(post_video_response["body"])
        upload_url = body.get("upload_url", "")
        assert _GCS_SIGNED_URL_RE.match(upload_url), (
            f"Expected a GCS signed URL (https://storage.googleapis.com/...?X-Goog-Signature=...), "
            f"got: {upload_url!r}"
        )

    def test_video_row_exists_in_database(self, post_video_response, db_conn):
        """The video must be persisted in the videos table with status 'pending'."""
        body = json.loads(post_video_response["body"])
        video_id = body.get("video_id", "")
        assert video_id, "video_id missing from response — cannot verify DB row."

        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id, title, status FROM videos WHERE id = %s",
                (video_id,),
            )
            row = cur.fetchone()

        assert row is not None, (
            f"Expected a video row with id={video_id!r} in the database, but none was found."
        )
        assert row[1] == _VIDEO_TITLE, (
            f"Expected title={_VIDEO_TITLE!r}, got {row[1]!r}"
        )
        assert row[2] == "pending", (
            f"Expected status='pending', got {row[2]!r}"
        )
