"""
MYTUBE-253: Delete comment with non-existent ID — system returns 404 not found.

Objective
---------
Verify the system's behavior when attempting to delete a comment ID that does
not exist in the database.

Preconditions
-------------
- An authenticated user is logged into the system.

Test Steps
----------
1. Log in as an authenticated user (obtain a valid Firebase ID token).
2. Send a DELETE request to /api/comments/00000000-0000-0000-0000-000000000000
   (valid UUID format that does not exist).

Expected Result
---------------
The system returns a 404 Not Found error.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.auth_service import AuthService
from testing.components.services.comment_api_service import CommentApiService
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

_API_PORT = 18253
_STARTUP_TIMEOUT = 20.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)

_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "test-placeholder-bucket")

# Valid UUID that does not exist in the database
NON_EXISTENT_COMMENT_ID = "00000000-0000-0000-0000-000000000000"


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    """Load database configuration."""
    return DBConfig()


@pytest.fixture(scope="module")
def api_service(db_config: DBConfig) -> ApiProcessService:
    """Start the API service and yield it; stop on teardown."""
    _build_binary()
    
    env_overrides = {
        "GOOGLE_APPLICATION_CREDENTIALS": _MOCK_CREDS,
        "RAW_UPLOADS_BUCKET": _RAW_UPLOADS_BUCKET,
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
    }
    
    service = ApiProcessService(
        binary_path=API_BINARY,
        port=_API_PORT,
        env=env_overrides,
        startup_timeout=_STARTUP_TIMEOUT,
    )
    service.start()
    service.wait_for_ready_or_crash()
    
    yield service
    
    service.stop()


@pytest.fixture(scope="module")
def api_base_url() -> str:
    """Return the API base URL for this test module."""
    return f"http://localhost:{_API_PORT}"


@pytest.fixture(scope="module")
def firebase_token() -> str:
    """Get Firebase test token from environment.
    
    Skips Layer B tests if FIREBASE_TEST_TOKEN is not set.
    """
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping HTTP integration tests."
        )
    return _FIREBASE_TOKEN


@pytest.fixture(scope="module")
def comment_service(api_base_url: str, firebase_token: str) -> CommentApiService:
    """Instantiate comment service with authenticated token."""
    return CommentApiService(base_url=api_base_url, token=firebase_token)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDeleteCommentWithNonExistentId:
    """Verify DELETE /api/comments/{non-existent-id} returns 404."""
    
    def test_delete_nonexistent_comment_returns_404(
        self,
        api_service: ApiProcessService,
        comment_service: CommentApiService,
    ):
        """
        When deleting a comment that does not exist, the system returns 404.
        
        Steps:
        1. Ensure the API is running (api_service fixture starts it).
        2. Send DELETE /api/comments/00000000-0000-0000-0000-000000000000
           with valid Bearer token.
        3. Verify response status is 404 Not Found.
        """
        assert api_service.is_running(), "API service is not running"
        
        status, body = comment_service.delete_comment(NON_EXISTENT_COMMENT_ID)
        
        assert status == 404, (
            f"Expected 404 Not Found when deleting non-existent comment, "
            f"got status {status}. Response body: {body!r}"
        )
