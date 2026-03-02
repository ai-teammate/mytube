"""
MYTUBE-136: Submit video metadata without required title — API returns 4xx error.

Objective
---------
Verify that the API enforces the requirement for a video title during metadata
submission. When a POST request to /api/videos is made by an authenticated user
with a JSON body that has an empty or null title, the API must reject the request
with a 4xx status code and an error message indicating that the title is required.

Preconditions
-------------
- User is authenticated (valid Firebase ID token).

Test structure
--------------
Layer A — Go unit tests (always runs; no Firebase token or DB required):
    Runs the existing Go handler unit tests to verify that the videos handler
    correctly rejects empty and whitespace-only titles with 422.

Layer B — Integration test via HTTP (runs when FIREBASE_TEST_TOKEN is set):
    Starts the full Go API server, sends real HTTP POST /api/videos requests
    with a valid Firebase bearer token and an empty/null/missing title, and
    asserts the server returns a 4xx status with a JSON error mentioning "title".

Environment variables
---------------------
- FIREBASE_TEST_TOKEN     : Valid Firebase ID token (Layer B only).
- FIREBASE_PROJECT_ID     : Firebase project (default: "test-project").
- API_BINARY              : Path to the pre-built Go binary
                            (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                            Database connection settings (Layer B only).

Architecture notes
------------------
- Layer A invokes `go test ./internal/handler/ -run ...` via subprocess.
- Layer B uses ApiProcessService (subprocess + HTTP) and a local _post_json
  helper (AuthService only exposes GET; POST needs a local helper).
- Mock GCP credentials (testing/fixtures/mock_service_account.json) allow the
  GCS client to initialise without real GCP project access.
- No hardcoded values — all config comes from environment variables or the
  mock credentials fixture.
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

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18136
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "test-project")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT,
    "testing",
    "fixtures",
    "mock_service_account.json",
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)

# RAW_UPLOADS_BUCKET is required at server startup; a placeholder is sufficient
# because title-validation tests are rejected before GCS is ever invoked.
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "test-placeholder-bucket")


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
    """Run a single Go unit test inside the handler package.

    Returns the CompletedProcess so callers can inspect returncode and output.
    """
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-run", test_name, "./internal/handler/"],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )


def _post_json(
    port: int, path: str, payload: dict, token: str
) -> tuple[int, str]:
    """Issue an authenticated POST request with a JSON body.

    Returns (status_code, response_body).
    """
    url = f"http://127.0.0.1:{port}{path}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()


# ---------------------------------------------------------------------------
# Layer A — Go unit tests (always runs; no external services required)
# ---------------------------------------------------------------------------


class TestSubmitVideoWithoutTitle_GoUnit:
    """Invoke existing Go handler unit tests to verify title validation."""

    def test_empty_title_returns_422_unit(self):
        """The handler must return HTTP 422 when title is an empty string.

        Runs: TestNewVideosHandler_POST_EmptyTitle_Returns422
        """
        result = _run_go_test("TestNewVideosHandler_POST_EmptyTitle_Returns422")
        assert result.returncode == 0, (
            f"Go unit test TestNewVideosHandler_POST_EmptyTitle_Returns422 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_whitespace_title_returns_422_unit(self):
        """The handler must return HTTP 422 when title contains only whitespace.

        Runs: TestNewVideosHandler_POST_WhitespaceTitleOnly_Returns422
        """
        result = _run_go_test("TestNewVideosHandler_POST_WhitespaceTitleOnly_Returns422")
        assert result.returncode == 0, (
            f"Go unit test TestNewVideosHandler_POST_WhitespaceTitleOnly_Returns422 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_full_title_validation_suite_passes(self):
        """All title-related validation unit tests must pass together.

        Runs all EmptyTitle / WhitespaceTitle Go unit tests at once.
        """
        result = _run_go_test(
            "TestNewVideosHandler_POST_EmptyTitle|TestNewVideosHandler_POST_WhitespaceTitleOnly"
        )
        assert result.returncode == 0, (
            f"One or more title-validation Go unit tests failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Layer B — Integration test via HTTP
# Requires FIREBASE_TEST_TOKEN; skipped gracefully when absent.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def firebase_token() -> str:
    """Load the Firebase test token; skip the Layer B test class if absent."""
    token = os.getenv("FIREBASE_TEST_TOKEN", "")
    if not token:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping HTTP integration tests "
            "(Layer A Go unit tests still run)"
        )
    return token


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
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
def empty_title_response(api_server: ApiProcessService, firebase_token: str) -> tuple[int, str]:
    """POST /api/videos with an empty title string; capture (status, body)."""
    return _post_json(_PORT, "/api/videos", {
        "title": "",
        "description": "A video with no title",
        "category_id": 1,
        "mime_type": "video/mp4",
    }, firebase_token)


@pytest.fixture(scope="module")
def null_title_response(api_server: ApiProcessService, firebase_token: str) -> tuple[int, str]:
    """POST /api/videos with title explicitly null; capture (status, body)."""
    return _post_json(_PORT, "/api/videos", {
        "title": None,
        "description": "A video with null title",
        "category_id": 1,
        "mime_type": "video/mp4",
    }, firebase_token)


@pytest.fixture(scope="module")
def missing_title_response(api_server: ApiProcessService, firebase_token: str) -> tuple[int, str]:
    """POST /api/videos without a title key; capture (status, body)."""
    return _post_json(_PORT, "/api/videos", {
        "description": "A video with missing title key",
        "category_id": 1,
        "mime_type": "video/mp4",
    }, firebase_token)


class TestSubmitVideoWithoutTitle_Integration:
    """HTTP integration: POST /api/videos with empty/null/missing title returns 4xx."""

    def test_empty_title_returns_4xx_status(self, empty_title_response: tuple[int, str]):
        """Submitting an empty title must be rejected with a 4xx status code."""
        status_code, body = empty_title_response
        assert 400 <= status_code < 500, (
            f"Expected a 4xx status code for an empty title, "
            f"got {status_code}. Response body: {body}"
        )

    def test_empty_title_response_is_valid_json(self, empty_title_response: tuple[int, str]):
        """The rejection response body must be valid JSON."""
        _, body = empty_title_response
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Response body is not valid JSON: {exc}\nBody: {body}")

    def test_empty_title_response_contains_error_field(self, empty_title_response: tuple[int, str]):
        """The rejection response JSON must contain an 'error' field."""
        _, body = empty_title_response
        data = json.loads(body)
        assert "error" in data, (
            f"Expected an 'error' field in the response JSON, got keys: {list(data.keys())}. "
            f"Body: {body}"
        )

    def test_empty_title_error_mentions_title(self, empty_title_response: tuple[int, str]):
        """The error message must mention 'title'."""
        _, body = empty_title_response
        data = json.loads(body)
        error_msg = data.get("error", "").lower()
        assert "title" in error_msg, (
            f"Expected the error message to mention 'title', got: '{data.get('error')}'"
        )

    def test_null_title_returns_4xx_status(self, null_title_response: tuple[int, str]):
        """Submitting null as title must also be rejected with a 4xx status code."""
        status_code, body = null_title_response
        assert 400 <= status_code < 500, (
            f"Expected a 4xx status code for a null title, "
            f"got {status_code}. Response body: {body}"
        )

    def test_null_title_response_contains_error_field(self, null_title_response: tuple[int, str]):
        """The null-title rejection response must contain an 'error' field."""
        _, body = null_title_response
        data = json.loads(body)
        assert "error" in data, (
            f"Expected an 'error' field for null title response, "
            f"got keys: {list(data.keys())}. Body: {body}"
        )

    def test_missing_title_returns_4xx_status(self, missing_title_response: tuple[int, str]):
        """Omitting the title key entirely must be rejected with a 4xx status code."""
        status_code, body = missing_title_response
        assert 400 <= status_code < 500, (
            f"Expected a 4xx status code when title key is absent, "
            f"got {status_code}. Response body: {body}"
        )

    def test_missing_title_response_contains_error_field(self, missing_title_response: tuple[int, str]):
        """The missing-title rejection response must contain an 'error' field."""
        _, body = missing_title_response
        data = json.loads(body)
        assert "error" in data, (
            f"Expected an 'error' field for missing title response, "
            f"got keys: {list(data.keys())}. Body: {body}"
        )
