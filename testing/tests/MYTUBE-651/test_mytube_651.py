"""
MYTUBE-651: Delete avatar without authentication — API returns 401 Unauthorized.

Objective
---------
Ensure that the DELETE /api/me/avatar endpoint is protected and requires valid
authentication.  A request sent without an Authorization header must be rejected
with HTTP 401 Unauthorized.

Steps
-----
1. Start the Go API server with mock Firebase credentials.
2. Send a DELETE request to /api/me/avatar with no Authorization header.
3. Assert that the HTTP response status is 401.

Expected Result
---------------
The API returns HTTP 401 Unauthorized.

Architecture notes
------------------
- ApiProcessService manages the Go API subprocess lifecycle.
- APIConfig / DBConfig load connection settings from environment variables.
- GOOGLE_APPLICATION_CREDENTIALS points to a mock service-account JSON so
  the Firebase Admin SDK can initialise without real GCP credentials.
  Token verification is never reached because the middleware rejects the
  request before calling Firebase.

Run from repo root:
    pytest testing/tests/MYTUBE-651/test_mytube_651.py -v
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

import pytest

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

API_BINARY = os.getenv(
    "API_BINARY",
    os.path.join(_REPO_ROOT, "api", "mytube-api"),
)

# Port chosen to avoid conflicts with other test suites.
_PORT = 18097

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


def _delete(port: int, path: str) -> tuple[int, str]:
    """Issue a DELETE request to *path* on localhost:*port* without auth.

    Returns ``(status_code, response_body)``.
    """
    url = f"http://127.0.0.1:{port}{path}"
    req = urllib.request.Request(url, method="DELETE")
    # Deliberately no Authorization header — this is the scenario under test.
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


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
    """Build (if needed) and start the API server; tear it down after the module."""
    _build_binary()

    firebase_project_id = os.getenv("FIREBASE_PROJECT_ID", "mock-project-id")

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": firebase_project_id,
        "GOOGLE_APPLICATION_CREDENTIALS": FIREBASE_MOCK_CREDS,
        # RAW_UPLOADS_BUCKET is required by main.go at startup; a placeholder
        # value is fine because the DELETE /api/me/avatar middleware rejects
        # unauthenticated requests before any GCS interaction.
        "RAW_UPLOADS_BUCKET": os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads"),
    }

    svc = ApiProcessService(
        binary_path=API_BINARY,
        port=_PORT,
        env=env,
        startup_timeout=SERVER_STARTUP_TIMEOUT,
    )
    svc.start()
    svc.wait_for_ready_or_crash()

    yield svc

    svc.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteAvatarRequiresAuth:
    """DELETE /api/me/avatar without an Authorization header must return 401."""

    def test_returns_401_status_code(self, api_server: ApiProcessService) -> None:
        """HTTP status code must be 401 when no Authorization header is present."""
        status_code, _ = _delete(_PORT, "/api/me/avatar")
        assert status_code == 401, (
            f"Expected HTTP 401 Unauthorized, got {status_code}. "
            "DELETE /api/me/avatar must reject unauthenticated requests."
        )

    def test_response_body_is_json(self, api_server: ApiProcessService) -> None:
        """Response body must be valid JSON."""
        _, body = _delete(_PORT, "/api/me/avatar")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            pytest.fail(
                f"Expected a JSON response body for 401, got non-JSON:\n{body}"
            )
        assert isinstance(parsed, dict), (
            f"Expected a JSON object in the response body, got: {parsed!r}"
        )

    def test_response_body_contains_error_field(self, api_server: ApiProcessService) -> None:
        """JSON body must contain a non-empty 'error' field."""
        _, body = _delete(_PORT, "/api/me/avatar")
        parsed = json.loads(body)
        assert "error" in parsed, (
            f"Expected an 'error' key in the JSON response body, got: {parsed!r}"
        )
        assert parsed["error"], "The 'error' field must not be empty."
