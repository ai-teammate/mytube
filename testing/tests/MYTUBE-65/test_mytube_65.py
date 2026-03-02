"""
MYTUBE-65: Authenticate with malformed Authorization header — 401 Unauthorized returned.

Verifies that the RequireAuth middleware rejects requests where the
Authorization header does not follow the 'Bearer <token>' format.

Three malformed header scenarios are tested against the /api/me endpoint:
  1. Authorization: Basic <credentials>  — wrong scheme
  2. Authorization: Bearer               — Bearer scheme but token part is empty/whitespace
  3. Authorization: <token_only>         — raw token with no scheme prefix

Expected result: every request receives HTTP 401 Unauthorized.

Architecture notes
------------------
- The test starts a standalone Go test server (testing/testserver/) that
  implements the identical bearerToken()/requireAuth logic as the production
  api/internal/middleware/auth.go package.  This avoids the Firebase and
  database dependencies that prevent the production binary from starting in CI.
- The testserver binary is built from testing/testserver/ (standard library
  only, no external dependencies) and exposes GET /api/me behind requireAuth
  plus GET /health as a readiness probe.
- All subprocess and HTTP I/O is delegated to ApiProcessService
  (testing/components/services/api_process_service.py).
- The binary path is resolved via the TEST_SERVER_BINARY env var or the default
  build location inside testing/testserver/.
"""
import os
import subprocess
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.api_process_service import ApiProcessService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_TESTSERVER_DIR = os.path.join(_REPO_ROOT, "testing", "testserver")
_DEFAULT_BINARY = os.path.join(_TESTSERVER_DIR, "testserver")
TEST_SERVER_BINARY = os.getenv("TEST_SERVER_BINARY", _DEFAULT_BINARY)

# Port dedicated to this test module — avoids conflicts with other suites.
_SERVER_PORT = 18650

_STARTUP_TIMEOUT = 15.0   # seconds to wait for the server to become ready
_ME_PATH = "/api/me"


def _build_testserver() -> None:
    """Build the testserver binary if it does not already exist."""
    if os.path.isfile(TEST_SERVER_BINARY):
        return
    result = subprocess.run(
        ["go", "build", "-o", TEST_SERVER_BINARY, "."],
        cwd=_TESTSERVER_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to build testserver:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_server():
    """Build (if needed) and start the test server, wait until ready.

    Yields the running ApiProcessService; terminates the process on teardown.
    """
    _build_testserver()

    if not os.path.isfile(TEST_SERVER_BINARY):
        pytest.skip(
            f"testserver binary not found at '{TEST_SERVER_BINARY}'. "
            "Build it with: cd testing/testserver && go build -o testserver ."
        )

    svc = ApiProcessService(
        binary_path=TEST_SERVER_BINARY,
        port=_SERVER_PORT,
        env={"PORT": str(_SERVER_PORT)},
        startup_timeout=_STARTUP_TIMEOUT,
    )
    svc.start()

    ready = svc.wait_for_ready(path="/health")
    if not ready:
        logs = svc.get_log_output()
        svc.stop()
        pytest.fail(
            f"Test server did not become ready within {_STARTUP_TIMEOUT}s.\n"
            f"Logs:\n{logs}"
        )

    yield svc

    svc.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMalformedAuthorizationHeader:
    """Middleware must return 401 for every non-'Bearer <token>' Authorization value."""

    def test_basic_scheme_returns_401(self, api_server: ApiProcessService):
        """'Authorization: Basic <credentials>' must be rejected with 401.

        The middleware only accepts the Bearer scheme; any other scheme is a
        malformed header per the API contract.
        """
        status, body = api_server.get(
            _ME_PATH,
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert status == 401, (
            f"Expected 401 for 'Basic' scheme, got {status}. "
            f"Response body: {body}"
        )

    def test_bearer_without_token_returns_401(self, api_server: ApiProcessService):
        """'Authorization: Bearer' with no token value must be rejected with 401.

        A trailing space followed by nothing (or whitespace only) means the
        token part is empty; the middleware must treat this as malformed.
        """
        status, body = api_server.get(
            _ME_PATH,
            headers={"Authorization": "Bearer "},
        )
        assert status == 401, (
            f"Expected 401 for 'Bearer' with empty token, got {status}. "
            f"Response body: {body}"
        )

    def test_token_without_bearer_prefix_returns_401(self, api_server: ApiProcessService):
        """'Authorization: <token_only>' with no scheme must be rejected with 401.

        Without the 'Bearer' prefix the header cannot be split into a valid
        scheme/token pair; the middleware must reject it.
        """
        status, body = api_server.get(
            _ME_PATH,
            headers={"Authorization": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.fake"},
        )
        assert status == 401, (
            f"Expected 401 for token-only header (no scheme), got {status}. "
            f"Response body: {body}"
        )
