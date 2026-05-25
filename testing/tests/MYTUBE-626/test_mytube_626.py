"""
MYTUBE-626: Upload unsupported file type — API returns 400 Bad Request.

Objective
---------
Verify that the POST /api/me/avatar endpoint rejects file types other than
image/jpeg and image/png with HTTP 400 Bad Request and an appropriate error
message indicating the MIME type is not supported.

Steps
-----
1. Start the Go API server locally with valid DB and Firebase credentials.
2. Seed the test user so authentication succeeds.
3. Send POST /api/me/avatar with a multipart form containing a file whose
   Content-Type is image/gif (an unsupported type).
4. Assert the response is HTTP 400.
5. Assert the JSON error body contains a message about the unsupported type.
6. Repeat with application/pdf to confirm the rule applies broadly.

Expected Result
---------------
- HTTP 400 Bad Request for both image/gif and application/pdf.
- JSON body: {"error": "unsupported file type; accepted types: jpeg, png"}

Environment variables
---------------------
- FIREBASE_TEST_TOKEN : Firebase ID token for the test user. Required.
- FIREBASE_PROJECT_ID : Firebase project ID for the verifier. Required.
- FIREBASE_TEST_UID   : firebase_uid of the test user (default: ci-test-user-001).
- API_BINARY          : Path to the pre-built Go binary
                        (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                        Database connection settings.

Architecture notes
------------------
- ApiProcessService starts/stops the Go API binary; all HTTP calls go through it.
- Multipart form data is encoded manually with email.mime / io.BytesIO.
- Direct psycopg2 SQL is used for idempotent test-user seeding.
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.

Run from repo root:
    pytest testing/tests/MYTUBE-626/test_mytube_626.py -v
"""
from __future__ import annotations

import base64
import email.generator
import email.mime.multipart
import email.mime.base
import io
import json
import os
import subprocess
import sys
import uuid

import psycopg2
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
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18626
_STARTUP_TIMEOUT = 20.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

# Minimal 1×1 GIF (35 bytes) — syntactically valid but MIME type is not allowed.
_MINIMAL_GIF = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

# Minimal PDF header bytes — Content-Type application/pdf is not allowed.
_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"

# The exact error message the handler returns for unsupported MIME types.
_EXPECTED_ERROR_FRAGMENT = "unsupported file type"

# GCS bucket env var — the binary requires it; a fake value is fine because
# we expect the 400 rejection to happen before any storage call.
_FAKE_BUCKET = "mytube-test-fake-bucket"
_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> None:
    """Build the Go API binary if it is not already present."""
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
        pytest.fail(
            f"Failed to build API binary:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _build_multipart_body(
    file_bytes: bytes, content_type: str, filename: str
) -> tuple[bytes, str]:
    """Encode a single-file multipart/form-data body.

    Returns (body_bytes, content_type_header) where content_type_header
    includes the boundary parameter.

    We use Python's email library to produce a standards-compliant body
    without pulling in third-party dependencies.
    """
    boundary = f"----FormBoundary{uuid.uuid4().hex}"
    body_lines: list[bytes] = []

    # Part header
    body_lines.append(f"--{boundary}\r\n".encode())
    body_lines.append(
        f'Content-Disposition: form-data; name="avatar"; filename="{filename}"\r\n'.encode()
    )
    body_lines.append(f"Content-Type: {content_type}\r\n".encode())
    body_lines.append(b"\r\n")
    body_lines.append(file_bytes)
    body_lines.append(b"\r\n")
    # Closing boundary
    body_lines.append(f"--{boundary}--\r\n".encode())

    return b"".join(body_lines), f"multipart/form-data; boundary={boundary}"


def _post_avatar(svc: ApiProcessService, file_bytes: bytes, mime_type: str, filename: str) -> tuple[int, str]:
    """POST a multipart avatar upload to /api/me/avatar.

    Returns (status_code, response_body_str).
    """
    body, ct_header = _build_multipart_body(file_bytes, mime_type, filename)
    status, resp_body = svc.post(
        "/api/me/avatar",
        body=body,
        headers={
            "Authorization": f"Bearer {_FIREBASE_TOKEN}",
            "Content-Type": ct_header,
        },
    )
    return status, resp_body


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials() -> None:
    """Skip the entire module when Firebase credentials are not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping MYTUBE-626 avatar upload test. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run this test."
        )
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — the API server cannot initialise "
            "the Firebase verifier without this variable."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """Build (if needed), start the Go API server, and yield the service.

    The server is stopped after all tests in the module have run.
    """
    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "RAW_UPLOADS_BUCKET": _FAKE_BUCKET,
        "HLS_OUTPUT_BUCKET": _FAKE_BUCKET,
        "GOOGLE_APPLICATION_CREDENTIALS": _MOCK_CREDS,
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
    """Open a direct psycopg2 connection for test-data setup."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_user(api_server, db_conn):
    """Ensure a user row exists for _FIREBASE_TEST_UID so auth succeeds."""
    username = "testuser626"
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_TEST_UID, username),
        )
        cur.execute(
            "SELECT id, firebase_uid, username FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_FIREBASE_TEST_UID!r}"
        )
    return {"id": str(row[0]), "firebase_uid": row[1], "username": row[2]}


@pytest.fixture(scope="module")
def gif_response(api_server, seeded_user) -> dict:
    """POST an image/gif avatar and capture the response."""
    status, body = _post_avatar(api_server, _MINIMAL_GIF, "image/gif", "test.gif")
    return {"status_code": status, "body": body}


@pytest.fixture(scope="module")
def pdf_response(api_server, seeded_user) -> dict:
    """POST an application/pdf avatar and capture the response."""
    status, body = _post_avatar(api_server, _MINIMAL_PDF, "application/pdf", "test.pdf")
    return {"status_code": status, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarUnsupportedMimeTypeGif:
    """POST /api/me/avatar with image/gif must be rejected with HTTP 400."""

    def test_gif_status_is_400(self, gif_response: dict) -> None:
        """The server must return HTTP 400 Bad Request for image/gif."""
        assert gif_response["status_code"] == 400, (
            f"Expected HTTP 400 for image/gif upload, "
            f"got {gif_response['status_code']}. "
            f"Response body: {gif_response['body']}"
        )

    def test_gif_error_message_mentions_unsupported_type(self, gif_response: dict) -> None:
        """The JSON error body must mention the unsupported file type."""
        body = json.loads(gif_response["body"])
        error_msg = body.get("error", "")
        assert _EXPECTED_ERROR_FRAGMENT in error_msg, (
            f"Expected error message to contain {_EXPECTED_ERROR_FRAGMENT!r}, "
            f"got: {error_msg!r}. Full body: {gif_response['body']}"
        )

    def test_gif_error_message_mentions_accepted_types(self, gif_response: dict) -> None:
        """The error message should mention the accepted types (jpeg/png)."""
        body = json.loads(gif_response["body"])
        error_msg = body.get("error", "").lower()
        assert "jpeg" in error_msg or "png" in error_msg, (
            f"Expected the error message to name accepted MIME types (jpeg/png), "
            f"got: {error_msg!r}"
        )


class TestAvatarUnsupportedMimeTypePdf:
    """POST /api/me/avatar with application/pdf must be rejected with HTTP 400."""

    def test_pdf_status_is_400(self, pdf_response: dict) -> None:
        """The server must return HTTP 400 Bad Request for application/pdf."""
        assert pdf_response["status_code"] == 400, (
            f"Expected HTTP 400 for application/pdf upload, "
            f"got {pdf_response['status_code']}. "
            f"Response body: {pdf_response['body']}"
        )

    def test_pdf_error_message_mentions_unsupported_type(self, pdf_response: dict) -> None:
        """The JSON error body must mention the unsupported file type."""
        body = json.loads(pdf_response["body"])
        error_msg = body.get("error", "")
        assert _EXPECTED_ERROR_FRAGMENT in error_msg, (
            f"Expected error message to contain {_EXPECTED_ERROR_FRAGMENT!r}, "
            f"got: {error_msg!r}. Full body: {pdf_response['body']}"
        )

    def test_pdf_error_message_mentions_accepted_types(self, pdf_response: dict) -> None:
        """The error message should mention the accepted types (jpeg/png)."""
        body = json.loads(pdf_response["body"])
        error_msg = body.get("error", "").lower()
        assert "jpeg" in error_msg or "png" in error_msg, (
            f"Expected the error message to name accepted MIME types (jpeg/png), "
            f"got: {error_msg!r}"
        )
