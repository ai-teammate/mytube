"""
MYTUBE-63: Access protected endpoint without Authorization header — 401 Unauthorized returned.

Verifies that the Firebase Auth middleware rejects requests that do not supply an
Authorization header.  Specifically:

  1. A GET /api/me request sent without any Authorization header must receive
     HTTP 401 Unauthorized.
  2. The JSON error body must be present (Content-Type: application/json).

The test manages the full server lifecycle:
  - Builds the Go API binary if not already present.
  - Starts a PostgreSQL-backed API server with mock Firebase credentials so that
    the Firebase Admin SDK initialises without a real GCP project.
  - Waits for the server to become ready via socket polling.
  - Issues GET /api/me with no Authorization header and asserts the response.
  - Tears down the server after the test module completes.

Architecture notes
------------------
- ApiProcessService (testing/components/services/api_process_service.py)
  encapsulates all subprocess and HTTP I/O.
- APIConfig / DBConfig load connection settings from environment variables;
  nothing is hardcoded in the test.
- GOOGLE_APPLICATION_CREDENTIALS may point to a mock service-account JSON file
  so the Firebase Admin SDK can initialise without real GCP credentials.
  The mock file is only used to initialise the SDK; token *verification* is
  never reached because the middleware rejects the request before calling
  Firebase.
"""

import json
import os
import socket
import subprocess
import sys
import time

import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

# Resolved binary path: env var override → default build location
API_BINARY = os.getenv(
    "API_BINARY",
    os.path.join(_REPO_ROOT, "api", "mytube-api"),
)

# Port chosen to avoid conflicts with other test suites
_PORT = 18095

# Firebase Admin SDK mock credentials path.
# The SDK requires a valid service-account JSON to initialise; this file
# provides a structurally valid key so init succeeds without a real project.
# Actual token verification is never triggered by this test.
_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT,
    "testing",
    "fixtures",
    "mock_service_account.json",
)
FIREBASE_MOCK_CREDS = os.getenv(
    "GOOGLE_APPLICATION_CREDENTIALS",
    _DEFAULT_MOCK_CREDS,
)

SERVER_STARTUP_TIMEOUT = 20  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> None:
    """Build the Go API binary if it does not already exist."""
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
        pytest.fail(f"Failed to build API binary:\n{result.stderr}")


def _wait_for_port(host: str, port: int, proc: subprocess.Popen, timeout: float) -> None:
    """Block until the TCP port accepts connections or raises on timeout/crash."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            out = proc.stdout.read() if proc.stdout else b""
            pytest.fail(
                f"API server exited before becoming ready.\nOutput: {out.decode(errors='replace')}"
            )
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.3)
            if sock.connect_ex((host, port)) == 0:
                return
        time.sleep(0.1)
    proc.terminate()
    proc.wait(timeout=5)
    pytest.fail(f"API server did not become ready within {timeout}s.")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(api_config: APIConfig, db_config: DBConfig) -> ApiProcessService:
    """
    Build (if needed) and start the API server.

    The server is started with:
    - real DB credentials (from DBConfig / env vars)
    - FIREBASE_PROJECT_ID set to the project_id from the mock credentials file
    - GOOGLE_APPLICATION_CREDENTIALS pointing to the mock credentials file

    This allows the Firebase Admin SDK to initialise successfully.  Actual
    Firebase token verification is never invoked because the request under
    test carries no Authorization header, so the middleware rejects it before
    calling the verifier.
    """
    _build_binary()

    # Determine Firebase project id and mock credentials path.
    firebase_project_id = os.getenv("FIREBASE_PROJECT_ID", "mock-project-id")
    mock_creds = FIREBASE_MOCK_CREDS

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": firebase_project_id,
        "GOOGLE_APPLICATION_CREDENTIALS": mock_creds,
    }

    svc = ApiProcessService(
        binary_path=API_BINARY,
        port=_PORT,
        env=env,
        startup_timeout=SERVER_STARTUP_TIMEOUT,
    )
    svc.start()

    # Wait until the TCP port is accepting connections.
    proc = svc._process  # access underlying Popen for crash detection
    _wait_for_port("127.0.0.1", _PORT, proc, SERVER_STARTUP_TIMEOUT)

    yield svc

    svc.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProtectedEndpointRequiresAuth:
    """GET /api/me without an Authorization header must return 401 Unauthorized."""

    def test_returns_401_status_code(self, api_server: ApiProcessService):
        """HTTP status code must be 401 when Authorization header is absent."""
        status_code, _ = api_server.get("/api/me")
        assert status_code == 401, (
            f"Expected HTTP 401 Unauthorized, got {status_code}. "
            "The Firebase Auth middleware must reject requests with no Authorization header."
        )

    def test_response_body_is_json(self, api_server: ApiProcessService):
        """Response body must be valid JSON (Content-Type: application/json is implied)."""
        _, body = api_server.get("/api/me")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            pytest.fail(
                f"Expected a JSON response body, but got non-JSON content:\n{body}"
            )
        assert isinstance(parsed, dict), (
            f"Expected a JSON object in the response body, got: {parsed!r}"
        )

    def test_response_body_contains_error_field(self, api_server: ApiProcessService):
        """Response JSON must contain an 'error' field describing the rejection reason."""
        _, body = api_server.get("/api/me")
        parsed = json.loads(body)
        assert "error" in parsed, (
            f"Expected an 'error' key in the JSON response body, got: {parsed!r}"
        )
        assert parsed["error"], (
            "The 'error' field in the response body must not be empty."
        )
