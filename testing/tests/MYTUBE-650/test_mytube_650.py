"""
MYTUBE-650: Delete avatar via API — avatar URL cleared and 204 returned.

Objective
---------
Verify that DELETE /api/me/avatar returns HTTP 204 No Content and clears the
user's avatar_url field in the database, confirmed via a subsequent GET /api/me.

Preconditions
-------------
- A user row exists in the database for the test Firebase UID with a
  non-null avatar_url set.
- The API server is running and the Firebase token is valid.

Test steps
----------
1. Build and start the Go API server.
2. Ensure a test user exists in the database with avatar_url pre-set to a
   known non-null value.
3. Send DELETE /api/me/avatar with Authorization: Bearer <token>.
4. Assert HTTP 204 No Content.
5. Send GET /api/me with Authorization: Bearer <token>.
6. Assert avatar_url in the response is null or an empty string.

Expected result
---------------
DELETE /api/me/avatar returns HTTP 204 No Content.
Subsequent GET /api/me returns a JSON body where avatar_url is null or "".

Environment variables
---------------------
FIREBASE_TEST_TOKEN    : Firebase ID token for the test user (required).
FIREBASE_PROJECT_ID    : Firebase project ID (required by API server).
FIREBASE_TEST_UID      : firebase_uid stored in the DB row (default: ci-test-user-001).
API_BINARY             : Path to the pre-built Go binary.
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE : DB settings.
HLS_BUCKET             : GCS bucket name used by the API.
CDN_BASE_URL           : CDN base URL for the HLS bucket.

Architecture
------------
- ApiProcessService manages the Go API subprocess lifecycle.
- AuthService wraps authenticated DELETE and GET requests.
- psycopg2 seeds the test user with a known avatar_url before the test.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join("/tmp", "mytube-api-650")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18650
_STARTUP_TIMEOUT = 20.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

_HLS_BUCKET = os.getenv("HLS_BUCKET", "mytube-hls-output")
_CDN_BASE_URL = os.getenv("CDN_BASE_URL", "https://storage.googleapis.com/mytube-hls-output")

# Sentinel avatar URL set on the user BEFORE the DELETE call so we can
# confirm it was actually cleared (not already null).
_SEED_AVATAR_URL = "https://example.com/avatars/preset-avatar.jpg"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_binary() -> None:
    """Build the Go API binary fresh to ensure the current source is used."""
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


def _parse_json_body(raw: str) -> dict:
    """Parse a JSON response body; fall back to {'raw': raw} on error."""
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials() -> None:
    """Skip the entire module when Firebase credentials are absent."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping MYTUBE-650 delete-avatar test. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token."
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
    """Build and start the Go API server; yield; stop on teardown."""
    _build_binary()

    raw_uploads_bucket = os.getenv(
        "GCS_RAW_UPLOADS_BUCKET", os.getenv("RAW_BUCKET", "mytube-raw-uploads")
    )
    google_creds = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "HLS_BUCKET": _HLS_BUCKET,
        "CDN_BASE_URL": _CDN_BASE_URL,
        "RAW_UPLOADS_BUCKET": raw_uploads_bucket,
    }
    if google_creds:
        env["GOOGLE_APPLICATION_CREDENTIALS"] = google_creds

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
            f"API server did not become ready within {_STARTUP_TIMEOUT}s.\nLogs:\n{logs}"
        )

    yield svc
    svc.stop()


@pytest.fixture(scope="module")
def db_conn(db_config: DBConfig):
    """Open a direct psycopg2 connection for test-user setup."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_user(api_server, db_conn) -> dict:
    """Ensure a user row exists for *_FIREBASE_TEST_UID* with a pre-set avatar_url."""
    username = "testuser650"
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username, avatar_url)
            VALUES (%s, %s, %s)
            ON CONFLICT (firebase_uid) DO UPDATE
                SET username  = EXCLUDED.username,
                    avatar_url = EXCLUDED.avatar_url
            RETURNING id, firebase_uid, username, avatar_url
            """,
            (_FIREBASE_TEST_UID, username, _SEED_AVATAR_URL),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_FIREBASE_TEST_UID!r}"
        )

    assert row[3] == _SEED_AVATAR_URL, (
        f"Pre-condition failed: expected avatar_url={_SEED_AVATAR_URL!r} in DB "
        f"before DELETE, but got {row[3]!r}"
    )

    return {
        "id": str(row[0]),
        "firebase_uid": row[1],
        "username": row[2],
        "avatar_url": row[3],
    }


@pytest.fixture(scope="module")
def auth_service(api_server) -> AuthService:
    """Return an AuthService pointing at the local test server."""
    base_url = f"http://127.0.0.1:{_PORT}"
    return AuthService(base_url=base_url, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def delete_result(auth_service: AuthService, seeded_user) -> dict:
    """Send DELETE /api/me/avatar and capture the response."""
    status, body = auth_service.delete("/api/me/avatar")
    return {"status": status, "body": body}


@pytest.fixture(scope="module")
def get_me_result(auth_service: AuthService, delete_result) -> dict:
    """Send GET /api/me after the DELETE and capture the parsed response."""
    status, raw = auth_service.get("/api/me")
    return {"status": status, "body": _parse_json_body(raw)}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteAvatar:
    """MYTUBE-650: DELETE /api/me/avatar clears avatar_url and returns 204."""

    def test_delete_returns_204(self, delete_result: dict) -> None:
        """DELETE /api/me/avatar must return HTTP 204 No Content."""
        assert delete_result["status"] == 204, (
            f"Expected HTTP 204 for DELETE /api/me/avatar, "
            f"got {delete_result['status']}. "
            f"Response body: {delete_result['body']!r}"
        )

    def test_delete_response_body_is_empty(self, delete_result: dict) -> None:
        """A 204 response must have no body (or an empty body)."""
        body = delete_result["body"].strip()
        assert body == "", (
            f"Expected an empty response body for HTTP 204, "
            f"got: {body!r}"
        )

    def test_get_me_returns_200(self, get_me_result: dict) -> None:
        """Subsequent GET /api/me must return HTTP 200."""
        assert get_me_result["status"] == 200, (
            f"Expected HTTP 200 for GET /api/me after avatar deletion, "
            f"got {get_me_result['status']}. "
            f"Response body: {get_me_result['body']}"
        )

    def test_avatar_url_is_cleared(self, get_me_result: dict) -> None:
        """GET /api/me must show avatar_url is null or empty after deletion."""
        body = get_me_result["body"]

        assert "avatar_url" in body, (
            f"Expected 'avatar_url' key in GET /api/me response, "
            f"got keys: {list(body.keys())}"
        )

        avatar_url = body["avatar_url"]
        assert not avatar_url, (
            f"Expected avatar_url to be null or empty after DELETE /api/me/avatar, "
            f"but got: {avatar_url!r}. "
            f"The DELETE handler must set avatar_url to NULL in the database."
        )
