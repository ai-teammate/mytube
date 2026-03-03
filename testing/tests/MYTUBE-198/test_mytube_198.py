"""
MYTUBE-198: Submit rating without authentication — system returns 401 Unauthorized.

Objective
---------
Verify that rating submission is restricted to authenticated users.

Test steps
----------
1. Build and start the testserver (testing/testserver/) — no DB or Firebase
   credentials required; the testserver implements the identical requireAuth
   middleware logic as the production API.
2. Send a POST request to /api/videos/<uuid>/rating with {"stars": 4} and
   no Authorization header.
3. Assert the response status is 401 Unauthorized.
4. Assert the response body is valid JSON.
5. Assert the JSON body contains an "error" key.
6. Assert the error value is a non-empty string.

Expected Result
---------------
The server returns 401 Unauthorized. No rating data is stored because the
request is rejected by the auth middleware before the handler executes.

Environment variables
---------------------
- TEST_SERVER_BINARY : Path to the pre-built testserver binary
                       (default: testing/testserver/testserver).

Architecture notes
------------------
- The auth middleware fires before the handler body, so no video needs to
  exist — a placeholder UUID is sufficient.
- The testserver (testing/testserver/) implements bearerToken() and
  requireAuth() identically to api/internal/middleware/auth.go using only
  the Go standard library.
- ApiProcessService manages the subprocess lifecycle and HTTP requests.
- No hardcoded waits; wait_for_ready() polls /health.
"""
import json
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

_PORT = 18198
_STARTUP_TIMEOUT = 15.0

# Placeholder video UUID — auth fires before any DB lookup, so the video
# does not need to exist in the database.
_PLACEHOLDER_VIDEO_ID = "00000000-0000-0000-0000-000000000000"
_RATING_PATH = f"/api/videos/{_PLACEHOLDER_VIDEO_ID}/rating"

_RATING_PAYLOAD = json.dumps({"stars": 4}).encode("utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
            f"Failed to build testserver:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_server():
    """Build (if needed) and start the testserver, wait until /health responds.

    Yields the running ApiProcessService; stops the process on teardown.
    """
    _build_testserver()

    if not os.path.isfile(TEST_SERVER_BINARY):
        pytest.skip(
            f"testserver binary not found at '{TEST_SERVER_BINARY}'. "
            "Build it with: cd testing/testserver && go build -o testserver ."
        )

    svc = ApiProcessService(
        binary_path=TEST_SERVER_BINARY,
        port=_PORT,
        env={"PORT": str(_PORT)},
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


@pytest.fixture(scope="module")
def unauthenticated_rating_response(api_server: ApiProcessService) -> dict:
    """POST /api/videos/:id/rating with valid payload but NO Authorization header."""
    status_code, body = api_server.post(
        _RATING_PATH,
        body=_RATING_PAYLOAD,
        headers={"Content-Type": "application/json"},
    )
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSubmitRatingUnauthenticated:
    """POST /api/videos/:id/rating without an Authorization header must return 401."""

    def test_status_code_is_401(self, unauthenticated_rating_response: dict):
        """The response status must be HTTP 401 Unauthorized."""
        assert unauthenticated_rating_response["status_code"] == 401, (
            f"Expected HTTP 401, got {unauthenticated_rating_response['status_code']}. "
            f"Response body: {unauthenticated_rating_response['body']}"
        )

    def test_response_body_is_valid_json(self, unauthenticated_rating_response: dict):
        """The response body must be parseable JSON."""
        try:
            json.loads(unauthenticated_rating_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\n"
                f"Body: {unauthenticated_rating_response['body']}"
            )

    def test_response_contains_error_key(self, unauthenticated_rating_response: dict):
        """The JSON response must contain an 'error' key."""
        body = json.loads(unauthenticated_rating_response["body"])
        assert "error" in body, (
            f"Expected 'error' key in response, got keys: {list(body.keys())}"
        )

    def test_error_message_is_non_empty(self, unauthenticated_rating_response: dict):
        """The 'error' value must be a non-empty string."""
        body = json.loads(unauthenticated_rating_response["body"])
        assert isinstance(body.get("error"), str) and body["error"], (
            f"Expected a non-empty error string, got: {body.get('error')!r}"
        )
