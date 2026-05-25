"""
MYTUBE-627: Upload oversized file — API returns 413 Payload Too Large.

Objective
---------
Verify that the API rejects avatar uploads exceeding the 5 MB file size limit.

Steps
-----
1. Send a POST request to /api/me/avatar with an image file larger than 5 MB.

Expected Result
---------------
The API returns HTTP 413 Payload Too Large (RequestEntityTooLarge).

Implementation notes
--------------------
The handler (api/internal/handler/me_avatar.go) enforces a hard 5 MB limit
via two complementary checks:

  1. ``http.MaxBytesReader`` caps the entire request body at
     ``maxAvatarSize + multipartOverhead = 6 MB``.  A request body larger
     than 6 MB triggers ``*http.MaxBytesError`` during ``ParseMultipartForm``.

  2. A secondary ``io.LimitReader`` check catches files that are between
     5 MB + 1 byte and 6 MB (i.e. small enough to pass the body cap but
     still above the per-file limit).

This test exercises path (2): a file of exactly 5 MB + 1 byte with a valid
PNG magic header is sent.  The per-file LimitReader detects the excess and
the handler responds with HTTP 413 and JSON
``{"error": "file too large; maximum size is 5 MB"}``.

Strategy
--------
The test starts a local API server subprocess (the compiled Go binary) so
that it always tests the current codebase rather than an older deployed
version.  If the binary does not exist it is compiled from source.

A test user row is seeded in the local DB so the handler can proceed past
the user-lookup step and reach the file-size check.

Environment variables
---------------------
FIREBASE_TEST_TOKEN   : Firebase ID token for the CI test user (required).
                        Test is skipped when absent.
FIREBASE_PROJECT_ID   : Firebase project ID for the Go verifier (required).
                        Test is skipped when absent.
API_BINARY            : Path to the compiled Go binary.
                        Default: <repo_root>/api/mytube-api
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                        Database connection settings.
FIREBASE_TEST_UID     : firebase_uid of the test user seeded in the DB.
                        Default: ci-test-user-001

Architecture
------------
- ApiProcessService manages the local API subprocess lifecycle.
- AvatarApiService encapsulates authenticated multipart POST requests.
- APIConfig / DBConfig centralise env var access.
- psycopg2 seeds a test user row so the handler passes user-lookup.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.avatar_api_service import AvatarApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")

# PNG magic header bytes — causes http.DetectContentType to return "image/png".
_PNG_MAGIC = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])

# One byte beyond the 5 MB per-file limit.
_OVERSIZED_FILE_SIZE = 5 * 1024 * 1024 + 1  # 5,242,881 bytes

_FIREBASE_TEST_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")
_API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_LOCAL_PORT = 18627  # dedicated port for MYTUBE-627
_STARTUP_TIMEOUT = 20.0

_EXPECTED_STATUS = 413
_EXPECTED_ERROR_SUBSTR = "too large"


# ---------------------------------------------------------------------------
# File generation helper
# ---------------------------------------------------------------------------


def _make_oversized_png() -> bytes:
    """Return a byte string > 5 MB starting with a valid PNG magic header.

    The file content is padded with null bytes so that http.DetectContentType
    recognises it as image/png, bypassing the MIME-type rejection and reaching
    the file-size check in the handler.
    """
    buf = bytearray(_OVERSIZED_FILE_SIZE)
    buf[: len(_PNG_MAGIC)] = _PNG_MAGIC
    return bytes(buf)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> None:
    """Compile the Go binary from source if it is missing or outdated.

    Uses ``go build`` in the api/ directory.  Skips the build when the binary
    already exists and is newer than the source directory.
    """
    api_dir = os.path.join(_REPO_ROOT, "api")
    result = subprocess.run(
        ["go", "build", "-o", _API_BINARY, "."],
        cwd=api_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to build API binary:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _seed_test_user(db_config: DBConfig, firebase_uid: str) -> None:
    """Insert a test user row with *firebase_uid* if it does not already exist."""
    try:
        import psycopg2
    except ImportError:
        return  # no DB access; test user must already exist
    try:
        conn = psycopg2.connect(db_config.dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (firebase_uid, username)
                VALUES (%s, %s)
                ON CONFLICT (firebase_uid) DO NOTHING
                """,
                (firebase_uid, f"testuser627"),
            )
        conn.close()
    except Exception:
        pass  # if DB seed fails the test will fail with a clear assertion error


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_credentials():
    """Skip the entire module when Firebase credentials are not available."""
    if not _FIREBASE_TEST_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-627. "
            "Provide a valid Firebase ID token to run this test."
        )
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID is not set — the API server requires it to "
            "initialise the Firebase token verifier."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """Build (if needed), seed the DB, and start the local API server.

    Yields an ApiProcessService configured at localhost:{_LOCAL_PORT}.
    The server is stopped on teardown.
    """
    _build_binary()
    _seed_test_user(db_config, _FIREBASE_TEST_UID)

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        # Fake GCS values — avatar upload never reaches GCS (rejected by size
        # check before the upload step).
        "RAW_UPLOADS_BUCKET": "test-bucket-627",
        "HLS_BUCKET": "test-hls-627",
        "CDN_BASE_URL": "https://cdn.example.com",
    }

    svc = ApiProcessService(
        binary_path=_API_BINARY,
        port=_LOCAL_PORT,
        env=env,
        startup_timeout=_STARTUP_TIMEOUT,
    )
    svc.start()

    ready = svc.wait_for_ready(path="/health")
    if not ready:
        logs = svc.get_log_output()
        svc.stop()
        pytest.fail(
            f"Local API server did not become ready within {_STARTUP_TIMEOUT}s.\n"
            f"Logs:\n{logs}"
        )

    yield svc

    svc.stop()


@pytest.fixture(scope="module")
def avatar_service(api_server: ApiProcessService) -> AvatarApiService:
    """Return an AvatarApiService pointing at the local test server."""
    api_cfg = APIConfig.__new__(APIConfig)
    api_cfg.base_url = f"http://127.0.0.1:{_LOCAL_PORT}"
    api_cfg.health_token = ""
    return AvatarApiService(api_cfg, token=_FIREBASE_TEST_TOKEN)


@pytest.fixture(scope="module")
def oversized_response(avatar_service: AvatarApiService) -> tuple[int, str]:
    """Send a POST /api/me/avatar request with a 5 MB + 1 byte PNG file.

    Returns (status_code, response_body).
    """
    file_bytes = _make_oversized_png()
    status, body = avatar_service.upload_avatar(
        file_bytes=file_bytes,
        mime_type="image/png",
        filename="oversized_avatar.png",
        timeout=60,
    )
    return status, body


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarOversizedUpload:
    """MYTUBE-627 — POST /api/me/avatar with file > 5 MB must return HTTP 413."""

    def test_status_is_413(self, oversized_response: tuple[int, str]) -> None:
        """Step 1: POST /api/me/avatar with an oversized file returns HTTP 413.

        The handler enforces the 5 MB limit via io.LimitReader.  When the
        uploaded file exceeds that limit the handler writes HTTP 413
        (StatusRequestEntityTooLarge) before performing any GCS or DB
        operations.

        Expected: HTTP status code 413.
        """
        status, body = oversized_response

        assert status == _EXPECTED_STATUS, (
            f"Expected HTTP {_EXPECTED_STATUS} (Payload Too Large) when uploading a "
            f"{_OVERSIZED_FILE_SIZE:,}-byte PNG avatar, but received HTTP {status}.\n"
            f"Response body: {body!r}\n"
            "Possible causes:\n"
            "  - The file size limit is not enforced (handler bug).\n"
            "  - The test user does not exist in the DB (would yield 404).\n"
            "  - The Firebase token is invalid or expired (would yield 401)."
        )

    def test_error_body_mentions_too_large(
        self, oversized_response: tuple[int, str]
    ) -> None:
        """Step 1 (continued): The JSON error body mentions the size rejection.

        The handler calls writeJSONError with
        "file too large; maximum size is 5 MB" when the size limit is exceeded.

        Expected: the response body contains "too large" (case-insensitive).
        """
        status, body = oversized_response

        # Only assert body content when we have the right status code to avoid
        # a confusing double failure when the status is already wrong.
        if status != _EXPECTED_STATUS:
            pytest.skip(
                f"Status was {status} (not 413); body assertion skipped — "
                "fix the status assertion first."
            )

        assert _EXPECTED_ERROR_SUBSTR.lower() in body.lower(), (
            f"Expected the response body to contain {_EXPECTED_ERROR_SUBSTR!r} when "
            f"HTTP 413 is returned for an oversized avatar upload, but the body was:\n"
            f"{body!r}\n"
            "The handler should respond with "
            '{"error": "file too large; maximum size is 5 MB"}.'
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
