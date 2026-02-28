"""
MYTUBE-30: Access health endpoint — GET /health returns success after migration.

Verifies that once the database schema migration has run and the API server is
started, GET /health responds with HTTP 200 and a JSON body indicating
{"status": "ok", "db": "connected"}.

The test manages the full lifecycle:
  1. Starts a PostgreSQL-backed API server process with the correct DB env vars.
  2. Waits until the server is ready (or times out).
  3. Issues GET /health and asserts the response.
  4. Tears down the server process after the test.
"""
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error

import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.health_service import HealthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Path to the pre-built server binary (built from api/ via `go build -o ...`)
SERVER_BINARY = os.getenv(
    "API_SERVER_BINARY",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "api", "server"),
)

SERVER_STARTUP_TIMEOUT = 15  # seconds
SERVER_POLL_INTERVAL = 0.3   # seconds


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
def api_server(api_config: APIConfig, db_config: DBConfig):
    """
    Build (if needed) and start the Go API server in a subprocess.
    Yields once the /health endpoint is reachable, then terminates the process.
    """
    api_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "api")
    binary = SERVER_BINARY

    # Build the binary if it doesn't exist yet.
    if not os.path.isfile(binary):
        build_result = subprocess.run(
            ["go", "build", "-o", binary, "."],
            cwd=api_dir,
            capture_output=True,
            text=True,
        )
        if build_result.returncode != 0:
            pytest.fail(
                f"Failed to build API server:\n{build_result.stderr}"
            )

    port = api_config.base_url.split(":")[-1]
    env = {
        **os.environ,
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "PORT": port,
    }
    if api_config.health_token:
        env["HEALTH_TOKEN"] = api_config.health_token

    proc = subprocess.Popen(
        [binary],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for the server to start accepting connections.
    health_url = api_config.health_url()
    deadline = time.monotonic() + SERVER_STARTUP_TIMEOUT
    while time.monotonic() < deadline:
        try:
            req = urllib.request.Request(health_url, method="GET")
            if api_config.health_token:
                req.add_header("X-Health-Token", api_config.health_token)
            with urllib.request.urlopen(req, timeout=1):
                break  # server is up
        except Exception:
            if proc.poll() is not None:
                stdout = proc.stdout.read().decode()
                stderr = proc.stderr.read().decode()
                pytest.fail(
                    f"API server exited unexpectedly before becoming ready.\n"
                    f"stdout: {stdout}\nstderr: {stderr}"
                )
            time.sleep(SERVER_POLL_INTERVAL)
    else:
        proc.terminate()
        proc.wait(timeout=5)
        stdout = proc.stdout.read().decode()
        stderr = proc.stderr.read().decode()
        pytest.fail(
            f"API server did not become ready within {SERVER_STARTUP_TIMEOUT}s.\n"
            f"stdout: {stdout}\nstderr: {stderr}"
        )

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """GET /health must return 200 OK with a healthy JSON body after migration."""

    def test_returns_200_ok(self, api_server, api_config: APIConfig):
        """The status code must be 200."""
        svc = HealthService(api_config)
        response = svc.get_health()
        assert response.status_code == 200, (
            f"Expected HTTP 200, got {response.status_code}. "
            "Database migration may have failed or the server is not connected to the DB."
        )

    def test_response_body_status_ok(self, api_server, api_config: APIConfig):
        """The JSON body must contain status == 'ok'."""
        svc = HealthService(api_config)
        response = svc.get_health()
        assert response.status == "ok", (
            f"Expected status 'ok', got '{response.status}'. "
            "The health check indicates the database is not reachable."
        )

    def test_response_body_db_connected(self, api_server, api_config: APIConfig):
        """The JSON body must contain db == 'connected'."""
        svc = HealthService(api_config)
        response = svc.get_health()
        assert response.db == "connected", (
            f"Expected db 'connected', got '{response.db}'. "
            "The API server cannot ping the database."
        )

    def test_content_type_is_json(self, api_server, api_config: APIConfig):
        """The response Content-Type must be application/json."""
        url = api_config.health_url()
        req = urllib.request.Request(url, method="GET")
        if api_config.health_token:
            req.add_header("X-Health-Token", api_config.health_token)
        with urllib.request.urlopen(req) as resp:
            content_type = resp.headers.get("Content-Type", "")
        assert "application/json" in content_type, (
            f"Expected Content-Type to contain 'application/json', got '{content_type}'"
        )
