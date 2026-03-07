"""
MYTUBE-200: Post video comment — comment created with author info and returned in response.

Objective
---------
Verify that an authenticated user can post a comment on a video and receives the
full comment object in the response (id, body, author.username, author.avatar_url,
created_at).

Preconditions
-------------
- User is logged in (a valid Firebase ID token is provided).
- A video exists in the database.

Test steps
----------
1. Send POST /api/videos/:id/comments with Authorization: Bearer <FIREBASE_TEST_TOKEN>
   and JSON body: { "body": "Great video!" }.
2. Assert the response status is 201 Created.
3. Assert the response body is valid JSON containing:
   - id     — a non-empty UUID string
   - body   — equals "Great video!"
   - author — an object with username (non-empty string) and avatar_url key
   - created_at — a non-empty string

Test structure
--------------
Layer A — Go unit tests (always runs; no Firebase token or DB required):
    Invokes the existing Go comment handler unit test that exercises a successful
    POST, confirming the handler logic returns 201 and includes all required fields.

Layer B — Integration test via HTTP (runs when FIREBASE_TEST_TOKEN is set):
    Starts the full Go API server, seeds a user and video row in the test DB, then
    issues a real POST /api/videos/:id/comments request and asserts the full
    contract.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN  : Valid Firebase ID token.  Layer B skipped when absent.
- FIREBASE_PROJECT_ID  : Firebase project ID (default: "test-project").
- FIREBASE_TEST_UID    : firebase_uid for the test user row
                         (default: "test-uid-mytube-200").
- API_BINARY           : Path to the pre-built Go binary
                         (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                         Database connection settings (all have sensible defaults).

Architecture notes
------------------
- Layer A invokes ``go test`` as a subprocess.
- Layer B uses ApiProcessService (subprocess + HTTP) and CommentService.
- Mock GCP credentials allow the GCS client to initialise without real GCP access.
- No hardcoded values — all config comes from environment variables.
"""
from __future__ import annotations

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
from testing.components.services.comment_service import CommentService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18200
_STARTUP_TIMEOUT = 20.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "test-project")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-200")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)

_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "test-placeholder-bucket")

_COMMENT_BODY = "Great video!"

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
    result = subprocess.run(
        ["go", "build", "-o", API_BINARY, "."],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to build API binary:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _run_go_test(test_name: str) -> subprocess.CompletedProcess:
    """Run a Go unit test in the handler package and return the result."""
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-run", test_name, "./internal/handler/"],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )


def _is_uuid(value: str) -> bool:
    """Return True if *value* looks like a UUID v4."""
    return bool(_UUID_RE.match(value))


# ---------------------------------------------------------------------------
# Layer A — Go unit tests (always run; no credentials required)
# ---------------------------------------------------------------------------


class TestPostCommentGoUnit:
    """Invoke existing Go handler unit tests to verify comment creation logic."""

    def test_post_comment_success_returns_201_unit(self):
        """The handler must return 201 and include all comment fields on success.

        Runs: TestVideoCommentsHandler_POST_Success_Returns201WithComment
        """
        result = _run_go_test("TestVideoCommentsHandler_POST_Success_Returns201WithComment")
        assert result.returncode == 0, (
            f"Go unit test TestVideoCommentsHandler_POST_Success_Returns201WithComment failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_post_comment_no_auth_returns_401_unit(self):
        """Without auth, the handler must return 401 Unauthorized.

        Runs: TestVideoCommentsHandler_POST_NoAuth_Returns401
        """
        result = _run_go_test("TestVideoCommentsHandler_POST_NoAuth_Returns401")
        assert result.returncode == 0, (
            f"Go unit test TestVideoCommentsHandler_POST_NoAuth_Returns401 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_post_comment_empty_body_returns_422_unit(self):
        """The handler must return 422 when the comment body is empty.

        Runs: TestVideoCommentsHandler_POST_EmptyBody_Returns422
        """
        result = _run_go_test("TestVideoCommentsHandler_POST_EmptyBody_Returns422")
        assert result.returncode == 0, (
            f"Go unit test TestVideoCommentsHandler_POST_EmptyBody_Returns422 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Layer B — Integration test via HTTP
# Requires FIREBASE_TEST_TOKEN; skipped gracefully when absent.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def firebase_token() -> str:
    """Return the Firebase test token; skip Layer B tests when absent."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping HTTP integration tests "
            "(Layer A Go unit tests still run)."
        )
    return _FIREBASE_TOKEN


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig, firebase_token: str):
    """Build (if needed) and start the Go API server; yield it; stop on teardown."""
    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "GOOGLE_APPLICATION_CREDENTIALS": _MOCK_CREDS,
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
def db_conn(db_config: DBConfig, api_server: ApiProcessService):
    """Open a psycopg2 connection to the test DB (after migrations have run)."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_user(db_conn) -> dict:
    """Insert a user row with a known firebase_uid; return user metadata.

    Uses ON CONFLICT DO NOTHING so the fixture is idempotent.
    """
    username = "testuser200"
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
            "SELECT id, firebase_uid, username, avatar_url FROM users WHERE firebase_uid = %s",
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
        "avatar_url": row[3],
    }


@pytest.fixture(scope="module")
def seeded_video(db_conn, seeded_user: dict) -> str:
    """Insert a video row owned by the seeded user; return the video UUID."""
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO videos (uploader_id, title, status) "
            "VALUES (%s, %s, %s) RETURNING id",
            (seeded_user["id"], "Test Video MYTUBE-200", "ready"),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail("Could not insert video row for MYTUBE-200 test.")

    return str(row[0])


@pytest.fixture(scope="module")
def comment_service(api_server: ApiProcessService, firebase_token: str) -> CommentService:
    """Return a CommentService configured for the local test server."""
    return CommentService(api_client=api_server, token=firebase_token)


@pytest.fixture(scope="module")
def post_comment_response(
    comment_service: CommentService,
    seeded_video: str,
) -> tuple[int, str]:
    """Issue POST /api/videos/:id/comments with the test body; capture the response."""
    return comment_service.post_comment(video_id=seeded_video, body=_COMMENT_BODY)


# ---------------------------------------------------------------------------
# Tests — Layer B
# ---------------------------------------------------------------------------


class TestPostVideoComment:
    """POST /api/videos/:id/comments with a valid Bearer token must return 201."""

    def test_status_code_is_201(self, post_comment_response: tuple[int, str]):
        """The response status must be HTTP 201 Created."""
        status_code, body = post_comment_response
        assert status_code == 201, (
            f"Expected HTTP 201, got {status_code}. Response body: {body}"
        )

    def test_response_body_is_valid_json(self, post_comment_response: tuple[int, str]):
        """The response body must be parseable JSON."""
        _, body = post_comment_response
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Response body is not valid JSON: {exc}\nBody: {body}")

    def test_response_contains_id(self, post_comment_response: tuple[int, str]):
        """The JSON response must contain an 'id' field."""
        _, body = post_comment_response
        data = json.loads(body)
        assert "id" in data, (
            f"Expected 'id' field in response, got keys: {list(data.keys())}"
        )

    def test_id_is_uuid(self, post_comment_response: tuple[int, str]):
        """The 'id' field must be a valid UUID string."""
        _, body = post_comment_response
        data = json.loads(body)
        comment_id = data.get("id", "")
        assert _is_uuid(comment_id), (
            f"Expected 'id' to be a UUID, got: {comment_id!r}"
        )

    def test_response_contains_body(self, post_comment_response: tuple[int, str]):
        """The JSON response must contain a 'body' field."""
        _, body = post_comment_response
        data = json.loads(body)
        assert "body" in data, (
            f"Expected 'body' field in response, got keys: {list(data.keys())}"
        )

    def test_body_matches_submitted_text(self, post_comment_response: tuple[int, str]):
        """The returned 'body' must equal the submitted comment text."""
        _, body = post_comment_response
        data = json.loads(body)
        assert data.get("body") == _COMMENT_BODY, (
            f"Expected body={_COMMENT_BODY!r}, got {data.get('body')!r}"
        )

    def test_response_contains_author(self, post_comment_response: tuple[int, str]):
        """The JSON response must contain an 'author' object."""
        _, body = post_comment_response
        data = json.loads(body)
        assert "author" in data, (
            f"Expected 'author' field in response, got keys: {list(data.keys())}"
        )
        assert isinstance(data["author"], dict), (
            f"Expected 'author' to be an object, got: {type(data['author'])!r}"
        )

    def test_author_has_username(self, post_comment_response: tuple[int, str]):
        """The 'author' object must contain a non-empty 'username'."""
        _, body = post_comment_response
        data = json.loads(body)
        author = data.get("author", {})
        username = author.get("username", "")
        assert isinstance(username, str) and username, (
            f"Expected non-empty 'author.username', got: {username!r}"
        )

    def test_author_has_avatar_url_key(self, post_comment_response: tuple[int, str]):
        """The 'author' object must contain an 'avatar_url' key (may be null)."""
        _, body = post_comment_response
        data = json.loads(body)
        author = data.get("author", {})
        assert "avatar_url" in author, (
            f"Expected 'avatar_url' key in 'author', got keys: {list(author.keys())}"
        )

    def test_response_contains_created_at(self, post_comment_response: tuple[int, str]):
        """The JSON response must contain a non-empty 'created_at' timestamp."""
        _, body = post_comment_response
        data = json.loads(body)
        assert "created_at" in data, (
            f"Expected 'created_at' field in response, got keys: {list(data.keys())}"
        )
        created_at = data.get("created_at", "")
        assert created_at, (
            f"Expected non-empty 'created_at', got: {created_at!r}"
        )
