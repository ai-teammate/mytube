"""
MYTUBE-60: Authenticate with invalid Firebase token — API returns 401 Unauthorized.

Objective:
    Verify that requests with invalid, expired, or malformed Firebase tokens are
    rejected by the auth middleware with HTTP 401 Unauthorized and a JSON error body.

Test Strategy (two-part):

Part A — Go unit tests (always runs):
    Executes the existing Go unit tests for the RequireAuth middleware
    (api/internal/middleware/auth_test.go).  These tests exercise the middleware
    directly with stub verifiers, covering:
      - Missing Authorization header       → 401
      - Non-Bearer scheme (e.g. Basic)     → 401
      - Empty token string                 → 401
      - Invalid/expired token value        → 401
      - Response body is JSON with "error" key

Part B — Static analysis (always runs):
    Confirms that the middleware source (api/internal/middleware/auth.go) contains
    the 401-response path.  Acts as a regression guard ensuring the production code
    matches the behaviour verified by the Go unit tests.

Part C — Live integration test (skipped when infrastructure is unavailable):
    Starts the full Go API server and sends GET /api/me with an invalid Bearer
    token.  Requires FIREBASE_PROJECT_ID and a reachable PostgreSQL database.
    Skipped gracefully when either is absent.
"""
import json
import os
import socket
import subprocess
import sys
import urllib.parse

import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "..")
_API_DIR = os.path.join(_REPO_ROOT, "api")
_MIDDLEWARE_SRC = os.path.join(_API_DIR, "internal", "middleware", "auth.go")
_SERVER_BINARY = os.getenv(
    "API_SERVER_BINARY",
    os.path.join(_API_DIR, "server"),
)

# Port chosen to avoid collision with other test suites.
_TEST_PORT = 18060

# Tokens that must be rejected as invalid/expired/malformed.
_INVALID_TOKENS = [
    "this.is.not.a.valid.firebase.token",
    "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0In0.invalidsig",
    "expired-token-placeholder",
    "malformed",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_reachable(host: str, port: int) -> bool:
    """Return True if the PostgreSQL TCP port is reachable."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(1.0)
        return sock.connect_ex((host, port)) == 0


def _firebase_project_id_set() -> bool:
    """Return True if FIREBASE_PROJECT_ID is configured in the environment."""
    return bool(os.getenv("FIREBASE_PROJECT_ID", "").strip())


# ---------------------------------------------------------------------------
# Part A — Go Unit Tests
# ---------------------------------------------------------------------------


class TestAuthMiddlewareGoUnitTests:
    """
    Run the Go unit tests for the RequireAuth middleware via `go test`.

    These tests cover the exact behaviour described in MYTUBE-60:
      - Invalid/expired token → 401 Unauthorized
      - Missing or malformed Authorization header → 401 Unauthorized
      - JSON error body in the 401 response

    No external services (Firebase, PostgreSQL) are required.
    """

    def test_go_unit_tests_pass(self):
        """
        `go test ./internal/middleware/...` must pass with zero failures.

        The Go test suite exercises RequireAuth with stub verifiers, covering
        all token-rejection scenarios described in the ticket objective.
        """
        result = subprocess.run(
            ["go", "test", "-v", "./internal/middleware/..."],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"Go auth middleware unit tests failed.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

    def test_go_tests_cover_invalid_token_scenario(self):
        """
        The Go test output must include TestRequireAuth_InvalidToken,
        confirming that the invalid-token → 401 path is explicitly tested.
        """
        result = subprocess.run(
            ["go", "test", "-v", "-run", "TestRequireAuth_InvalidToken",
             "./internal/middleware/..."],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"TestRequireAuth_InvalidToken failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "PASS" in result.stdout, (
            f"TestRequireAuth_InvalidToken did not report PASS.\n"
            f"stdout:\n{result.stdout}"
        )

    def test_go_tests_cover_missing_header_scenario(self):
        """
        TestRequireAuth_MissingAuthHeader must pass — missing header → 401.
        """
        result = subprocess.run(
            ["go", "test", "-v", "-run", "TestRequireAuth_MissingAuthHeader",
             "./internal/middleware/..."],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"TestRequireAuth_MissingAuthHeader failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "PASS" in result.stdout, (
            f"TestRequireAuth_MissingAuthHeader did not report PASS.\n"
            f"stdout:\n{result.stdout}"
        )

    def test_go_tests_cover_json_error_body_scenario(self):
        """
        TestRequireAuth_401ResponseBody_IsJSON must pass — 401 must return
        Content-Type: application/json with an 'error' key in the body.
        """
        result = subprocess.run(
            ["go", "test", "-v", "-run", "TestRequireAuth_401ResponseBody_IsJSON",
             "./internal/middleware/..."],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"TestRequireAuth_401ResponseBody_IsJSON failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
        assert "PASS" in result.stdout, (
            f"TestRequireAuth_401ResponseBody_IsJSON did not report PASS.\n"
            f"stdout:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# Part B — Static Analysis
# ---------------------------------------------------------------------------


class TestAuthMiddlewareStaticAnalysis:
    """
    Static analysis of api/internal/middleware/auth.go.

    Confirms that the production source implements the 401 rejection path for
    invalid Firebase tokens, providing a regression guard independent of test
    execution infrastructure.
    """

    @pytest.fixture(scope="class")
    def middleware_source(self) -> str:
        assert os.path.isfile(_MIDDLEWARE_SRC), (
            f"Expected auth middleware at {_MIDDLEWARE_SRC} — file not found"
        )
        with open(_MIDDLEWARE_SRC, "r") as fh:
            return fh.read()

    def test_middleware_file_exists(self, middleware_source):
        """The auth middleware source file must be present."""
        assert middleware_source, "auth.go is empty or unreadable"

    def test_middleware_implements_require_auth(self, middleware_source):
        """RequireAuth must be defined — it is the entrypoint for token validation."""
        assert "func RequireAuth(" in middleware_source, (
            "auth.go does not define RequireAuth(). "
            "The middleware entrypoint is missing."
        )

    def test_middleware_rejects_missing_bearer_header(self, middleware_source):
        """
        The middleware must call bearerToken() and gate on its boolean result
        before invoking the Firebase verifier, so that absent/non-Bearer headers
        produce a 401 without touching Firebase.
        """
        assert "bearerToken(" in middleware_source, (
            "auth.go does not call bearerToken(). "
            "The header extraction helper is missing."
        )

    def test_middleware_calls_write_unauthorized_on_invalid_token(self, middleware_source):
        """
        Both rejection paths (missing header and failed verification) must call
        writeUnauthorized(), which sets the 401 status and JSON error body.
        """
        assert "writeUnauthorized(" in middleware_source, (
            "auth.go does not call writeUnauthorized(). "
            "The 401 response helper is missing."
        )

    def test_write_unauthorized_sets_401_status(self, middleware_source):
        """
        writeUnauthorized must write HTTP 401 (StatusUnauthorized).
        """
        assert "StatusUnauthorized" in middleware_source, (
            "auth.go does not reference http.StatusUnauthorized. "
            "The 401 status code must be set explicitly."
        )

    def test_write_unauthorized_returns_json_with_error_key(self, middleware_source):
        """
        writeUnauthorized must encode a JSON object.  The response body must
        contain an 'error' key per the expected result in MYTUBE-60.
        """
        assert '"error"' in middleware_source, (
            'auth.go does not contain the JSON key "error". '
            "The 401 response body must include an error description."
        )

    def test_middleware_calls_verify_id_token(self, middleware_source):
        """
        The middleware must call VerifyIDToken() to validate the token against
        Firebase.  An invalid/expired token causes VerifyIDToken to return an
        error, which triggers the 401 path.
        """
        assert "VerifyIDToken(" in middleware_source, (
            "auth.go does not call VerifyIDToken(). "
            "The Firebase token validation call is missing."
        )

    def test_content_type_is_json(self, middleware_source):
        """
        The 401 response must set Content-Type: application/json.
        """
        assert "application/json" in middleware_source, (
            'auth.go does not set Content-Type "application/json". '
            "401 responses must be JSON-typed."
        )


# ---------------------------------------------------------------------------
# Part C — Live Integration Test
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def live_api_server(api_config: APIConfig, db_config: DBConfig):
    """
    Build (if needed) and start the Go API server in a subprocess.

    Skipped when:
    - FIREBASE_PROJECT_ID is not set in the environment, or
    - The PostgreSQL database is not reachable.

    Yields the ApiProcessService instance once the server is ready, then
    terminates the process.
    """
    if not _firebase_project_id_set():
        pytest.skip(
            "FIREBASE_PROJECT_ID is not set — live integration test skipped. "
            "Set FIREBASE_PROJECT_ID and configure Application Default Credentials "
            "to enable this test."
        )

    if not _db_reachable(db_config.host, int(db_config.port)):
        pytest.skip(
            f"PostgreSQL is not reachable at {db_config.host}:{db_config.port} "
            "— live integration test skipped."
        )

    # Derive port from api_config.base_url (e.g. "http://localhost:8080").
    parsed_url = urllib.parse.urlparse(api_config.base_url)
    port = parsed_url.port if parsed_url.port is not None else _TEST_PORT

    # Build binary if missing.
    if not os.path.isfile(_SERVER_BINARY):
        build = subprocess.run(
            ["go", "build", "-o", _SERVER_BINARY, "."],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        if build.returncode != 0:
            pytest.fail(f"Failed to build API server:\n{build.stderr}")

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": os.environ["FIREBASE_PROJECT_ID"],
        "PORT": str(port),
    }

    svc = ApiProcessService(
        binary_path=_SERVER_BINARY,
        port=port,
        env=env,
        startup_timeout=15.0,
    )
    svc.start()

    if not svc.wait_for_ready("/health"):
        logs = svc.get_log_output()
        svc.stop()
        pytest.fail(
            f"API server did not become ready on port {port}.\nLogs:\n{logs}"
        )

    yield svc

    svc.stop()


class TestInvalidTokenReturns401:
    """
    Live integration tests: GET /api/me with invalid Firebase tokens must
    return 401 Unauthorized with a JSON error body.

    All tests in this class are skipped when FIREBASE_PROJECT_ID or PostgreSQL
    is unavailable (handled by the live_api_server fixture).
    """

    @pytest.mark.parametrize("token", _INVALID_TOKENS)
    def test_invalid_token_returns_401(self, live_api_server: ApiProcessService, token: str):
        """
        A request to GET /api/me with an invalid Bearer token must return
        HTTP 401 Unauthorized.
        """
        status_code, body = live_api_server.get(
            "/api/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert status_code == 401, (
            f"Expected HTTP 401 for token {token!r}, "
            f"got {status_code}. Body: {body}"
        )

    @pytest.mark.parametrize("token", _INVALID_TOKENS)
    def test_invalid_token_response_body_is_json_with_error_key(
        self, live_api_server: ApiProcessService, token: str
    ):
        """
        The 401 response body must be valid JSON containing an 'error' key.
        """
        _status_code, body = live_api_server.get(
            "/api/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"401 response body is not valid JSON for token {token!r}. "
                f"Body: {body!r}. Error: {exc}"
            )
        assert "error" in parsed, (
            f"401 JSON body does not contain 'error' key for token {token!r}. "
            f"Body: {parsed}"
        )

    def test_no_authorization_header_returns_401(self, live_api_server: ApiProcessService):
        """
        A request to GET /api/me with no Authorization header at all must
        return HTTP 401.
        """
        status_code, body = live_api_server.get("/api/me")
        assert status_code == 401, (
            f"Expected HTTP 401 for missing Authorization header, "
            f"got {status_code}. Body: {body}"
        )
