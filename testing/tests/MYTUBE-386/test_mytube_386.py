"""
MYTUBE-386: POST /api/videos call by user missing from database —
API returns clear error code instead of 404.

Objective
---------
Ensure that if a user record is missing and auto-provisioning is not
implemented, the API returns a meaningful error code (403 or 422 Unprocessable
Entity) instead of a generic 404 Not Found.

Preconditions
-------------
- User is authenticated via Firebase, but their UID has no corresponding row
  in the ``users`` database table.

Test Steps
----------
1. Send a POST request to /api/videos with valid metadata.
2. Use a valid Firebase Bearer token for the unseeded user.

Expected Result
---------------
The API returns HTTP 403 Forbidden or 422 Unprocessable Entity with a
descriptive error message such as {"error": "user account not registered"}.
The status code must NOT be 404 Not Found.

Layer A — Go unit tests (always run; no Firebase token or DB required):
    Runs all Go handler unit tests for the videos handler to verify existing
    handler logic, and specifically looks for any test that validates the
    403/422 response for a missing user.

Layer B — Integration test via HTTP (runs when FIREBASE_TEST_TOKEN is set):
    Starts the full Go API server, ensures no user row exists for the test
    Firebase UID, issues an authenticated POST /api/videos request, and
    asserts the response is 403 or 422 (not 404).

Environment variables
---------------------
- FIREBASE_TEST_TOKEN       : Valid Firebase ID token (Layer B only).
- FIREBASE_PROJECT_ID       : Firebase project (Layer B; default: "ai-native-478811").
- FIREBASE_TEST_UID         : Firebase UID of the test user (Layer B;
                              default: "ci-test-user-386").
- API_BINARY                : Path to the pre-built Go binary
                              (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE:
                              Database connection settings (Layer B).
- GOOGLE_APPLICATION_CREDENTIALS: Path to GCS service-account JSON
                              (Layer B; falls back to
                              testing/fixtures/mock_service_account.json).
- RAW_UPLOADS_BUCKET        : GCS bucket name (Layer B; default: "mytube-raw-uploads").

Architecture notes
------------------
- Layer A invokes ``go test ./internal/handler/ -run TestNewVideosHandler``
  via subprocess to verify handler-level behaviour.
- Layer B uses ApiProcessService (subprocess + HTTP) and AuthService to issue
  authenticated POST requests without raw HTTP calls inline.
- DB cleanup (delete user row for the test UID before request) is done via
  psycopg2 for isolation.
- No hardcoded values — all config comes from environment variables.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18386
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "ai-native-478811")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-386")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

# Valid POST /api/videos payload — metadata only.
_CREATE_VIDEO_PAYLOAD = {
    "title": "MYTUBE-386 Missing User Test Video",
    "mime_type": "video/mp4",
}


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


def _run_go_test(pattern: str) -> subprocess.CompletedProcess:
    """Run Go unit tests matching *pattern* in the handler package."""
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-run", pattern, "./internal/handler/"],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )


def _postgres_available(db_config: DBConfig) -> bool:
    """Return True if PostgreSQL is reachable at the configured host/port."""
    try:
        import psycopg2
        conn = psycopg2.connect(db_config.dsn())
        conn.close()
        return True
    except Exception:
        return False


# ===========================================================================
# Layer A — Go unit tests (always run; no external services required)
# ===========================================================================


class TestVideosHandler_GoUnit:
    """Run existing Go unit tests for the videos handler.

    These tests verify handler-level behaviour without a live DB or Firebase.
    They specifically highlight that the current implementation auto-provisions
    users via Upsert, returning 201 rather than 403/422 for unseeded users.
    """

    def test_all_videos_handler_unit_tests_pass(self):
        """All Go unit tests for the videos handler must pass.

        Runs TestNewVideosHandler* to cover: 401 without auth, 400 on bad
        JSON, 422 on missing/invalid fields, 201 on valid request, auto-
        provisioning of unseeded users, tag and title validation.
        """
        result = _run_go_test("TestNewVideosHandler")
        assert result.returncode == 0, (
            f"One or more Go unit tests for the videos handler failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_no_auth_returns_401(self):
        """POST /api/videos without a Firebase token must return 401."""
        result = _run_go_test("TestNewVideosHandler_POST_NoClaims_Returns401")
        assert result.returncode == 0, (
            f"TestNewVideosHandler_POST_NoClaims_Returns401 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_unseeded_user_returns_403(self):
        """POST /api/videos for a Firebase-authenticated user with no DB row must return 403.

        MYTUBE-388 replaced the Upsert auto-provisioning path with GetByFirebaseUID,
        so the handler now rejects unregistered users with 403 Forbidden.
        Wraps TestNewVideosHandler_POST_UserNotSeeded_Returns403.
        """
        result = _run_go_test("TestNewVideosHandler_POST_UserNotSeeded_Returns403")
        assert result.returncode == 0, (
            f"TestNewVideosHandler_POST_UserNotSeeded_Returns403 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_missing_title_returns_422(self):
        """POST /api/videos with an empty title must return 422."""
        result = _run_go_test("TestNewVideosHandler_POST_EmptyTitle_Returns422")
        assert result.returncode == 0, (
            f"TestNewVideosHandler_POST_EmptyTitle_Returns422 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_missing_mime_type_returns_422(self):
        """POST /api/videos with a missing mime_type must return 422."""
        result = _run_go_test("TestNewVideosHandler_POST_MissingMIMEType_Returns422")
        assert result.returncode == 0, (
            f"TestNewVideosHandler_POST_MissingMIMEType_Returns422 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ===========================================================================
# Layer B — Integration test via HTTP
# Requires FIREBASE_TEST_TOKEN; skipped gracefully when absent.
# ===========================================================================


@pytest.fixture(scope="module")
def firebase_token() -> str:
    """Load the Firebase test token; skip Layer B tests if absent."""
    token = os.getenv("FIREBASE_TEST_TOKEN", "")
    if not token:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping HTTP integration tests "
            "(Layer A Go unit tests still run)."
        )
    return token


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def require_db(db_config: DBConfig):
    """Skip Layer B tests when PostgreSQL is not reachable."""
    if not _postgres_available(db_config):
        pytest.skip(
            f"PostgreSQL is not reachable at {db_config.host}:{db_config.port} — "
            "skipping Layer B integration tests."
        )


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig, firebase_token: str, require_db):
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
def db_conn(db_config: DBConfig):
    """Open a direct psycopg2 connection to the test database."""
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed — skipping Layer B integration test.")

    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def ensure_user_absent(api_server, db_conn):
    """Delete any existing users row for the test Firebase UID before the test.

    This guarantees the precondition described in MYTUBE-386: the user is
    authenticated via Firebase but has no row in the ``users`` table.

    Teardown also removes any row that was created during the test run.
    """
    def _remove_user():
        with db_conn.cursor() as cur:
            # Remove child rows first (FK constraints).
            cur.execute(
                """DELETE FROM ratings WHERE user_id IN (
                       SELECT id FROM users WHERE firebase_uid = %s
                   )""",
                (_FIREBASE_TEST_UID,),
            )
            cur.execute(
                """DELETE FROM comments WHERE author_id IN (
                       SELECT id FROM users WHERE firebase_uid = %s
                   )""",
                (_FIREBASE_TEST_UID,),
            )
            cur.execute(
                """DELETE FROM video_tags WHERE video_id IN (
                       SELECT id FROM videos WHERE uploader_id IN (
                           SELECT id FROM users WHERE firebase_uid = %s
                       )
                   )""",
                (_FIREBASE_TEST_UID,),
            )
            cur.execute(
                """DELETE FROM playlist_videos WHERE playlist_id IN (
                       SELECT id FROM playlists WHERE owner_id IN (
                           SELECT id FROM users WHERE firebase_uid = %s
                       )
                   )""",
                (_FIREBASE_TEST_UID,),
            )
            cur.execute(
                """DELETE FROM videos WHERE uploader_id IN (
                       SELECT id FROM users WHERE firebase_uid = %s
                   )""",
                (_FIREBASE_TEST_UID,),
            )
            cur.execute(
                """DELETE FROM playlists WHERE owner_id IN (
                       SELECT id FROM users WHERE firebase_uid = %s
                   )""",
                (_FIREBASE_TEST_UID,),
            )
            cur.execute(
                "DELETE FROM users WHERE firebase_uid = %s",
                (_FIREBASE_TEST_UID,),
            )

    _remove_user()
    yield
    _remove_user()


@pytest.fixture(scope="module")
def auth_client(firebase_token: str) -> AuthService:
    """Return an AuthService configured to hit the local test server."""
    return AuthService(base_url=f"http://127.0.0.1:{_PORT}", token=firebase_token)


@pytest.fixture(scope="module")
def post_video_response(
    api_server, ensure_user_absent, auth_client: AuthService
) -> tuple[int, str]:
    """POST /api/videos with valid metadata as the unseeded Firebase user.

    Returns (status_code, body_str).
    """
    return auth_client.post("/api/videos", _CREATE_VIDEO_PAYLOAD)


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------


class TestMissingUserPostVideo:
    """MYTUBE-386: POST /api/videos for unseeded Firebase user returns 403 or 422."""

    def test_response_status_is_not_404(
        self, post_video_response: tuple[int, str]
    ):
        """The response must NOT be 404 Not Found.

        404 is a generic, misleading error. The API must return a meaningful
        status code (403 or 422) when the authenticated user has no DB record.
        """
        status_code, body = post_video_response
        assert status_code != 404, (
            f"POST /api/videos returned 404 for an unseeded Firebase user "
            f"(UID={_FIREBASE_TEST_UID!r}). Expected 403 or 422. "
            f"Response body: {body}"
        )

    def test_response_status_is_403_or_422(
        self, post_video_response: tuple[int, str]
    ):
        """The response status must be 403 Forbidden or 422 Unprocessable Entity.

        The API must reject the request with a meaningful error when the
        authenticated Firebase user has no row in the users table, rather than
        auto-provisioning the user (which returns 201).
        """
        status_code, body = post_video_response
        assert status_code in (403, 422), (
            f"POST /api/videos returned HTTP {status_code} for unseeded user "
            f"(UID={_FIREBASE_TEST_UID!r}). Expected 403 or 422. "
            f"Response body: {body}"
        )

    def test_response_body_is_valid_json(
        self, post_video_response: tuple[int, str]
    ):
        """The error response body must be parseable JSON."""
        status_code, body = post_video_response
        if status_code not in (403, 422):
            pytest.skip(
                f"Skipping JSON body check — status was {status_code}, not 403/422."
            )
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Error response body is not valid JSON: {exc}\nBody: {body}"
            )

    def test_response_body_contains_error_field(
        self, post_video_response: tuple[int, str]
    ):
        """The error response body must contain an 'error' key with a descriptive message."""
        status_code, body = post_video_response
        if status_code not in (403, 422):
            pytest.skip(
                f"Skipping error field check — status was {status_code}, not 403/422."
            )
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            pytest.skip("Skipping error field check — response body is not JSON.")

        assert "error" in data, (
            f"Expected 'error' key in response body. Got keys: {list(data.keys())}. "
            f"Body: {body}"
        )
        assert data["error"], (
            f"Expected non-empty 'error' value in response body. Body: {body}"
        )
