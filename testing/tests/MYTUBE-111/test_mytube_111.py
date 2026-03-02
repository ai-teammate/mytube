"""
MYTUBE-111: Update user profile settings — username and avatar URL updated via API.

Verifies that PUT /api/me correctly updates the user's username and avatar_url
and returns the updated profile in the response body.

Preconditions
-------------
- The user is logged in (a valid Firebase Bearer token is provided).
- The user record exists in the database (pre-seeded via fixture).

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a user row via direct DB access using a known firebase_uid.
3. Send PUT /api/me with Authorization: Bearer <FIREBASE_TEST_TOKEN> and a
   JSON body containing a new username and avatar_url.
4. Assert HTTP 200.
5. Assert the response body contains the updated username and avatar_url.
6. Assert the database row reflects the new values.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN  : Firebase ID token for the test user.
                         Test is skipped when absent.
- FIREBASE_PROJECT_ID  : Firebase project ID required to initialise the
                         verifier.  Test is skipped when absent.
- API_BINARY           : Path to the pre-built Go binary
                         (default: <repo_root>/api/mytube-api).
- FIREBASE_TEST_UID    : The firebase_uid stored in the users row that must
                         match the test token (default: test-uid-mytube-111).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                         Database connection settings (all have sensible
                         defaults matching the test DB configuration).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- Direct psycopg2 SQL is used for idempotent test-user setup (ON CONFLICT DO NOTHING).
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
"""
import json
import os
import subprocess
import sys

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

_PORT = 18111
_STARTUP_TIMEOUT = 20.0

# Firebase test credentials (required at runtime; test skips when absent).
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# The firebase_uid that the test token belongs to.
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-111")

# The new values the test will submit via PUT /api/me.
_NEW_USERNAME = "updated_user_111"
_NEW_AVATAR_URL = "https://example.com/avatar_111.png"


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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials():
    """Skip the entire module when Firebase credentials are not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping PUT /api/me integration test. "
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
    """
    Build (if needed) and start the Go API server in a subprocess.

    Yields the ApiProcessService once /health is reachable, then stops the
    process on teardown.
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
    """Open a direct psycopg2 connection to the test database."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_user(api_server, db_conn):
    """
    Insert a user row with a known firebase_uid before the PUT is issued.

    Uses ON CONFLICT DO NOTHING so the fixture is idempotent.  Resets
    username / avatar_url to their original values so each run starts from a
    clean state.
    """
    original_username = "original_user_111"

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO UPDATE SET username = EXCLUDED.username,
                                                      avatar_url = NULL
            """,
            (_FIREBASE_TEST_UID, original_username),
        )
        cur.execute(
            "SELECT id, firebase_uid, username, avatar_url FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_FIREBASE_TEST_UID!r}"
        )

    return {
        "id": str(row[0]),
        "firebase_uid": row[1],
        "username": row[2],
        "avatar_url": row[3],
    }


@pytest.fixture(scope="module")
def put_me_response(api_server, seeded_user):
    """Issue PUT /api/me with a new username and avatar_url; capture the response."""
    payload = json.dumps(
        {"username": _NEW_USERNAME, "avatar_url": _NEW_AVATAR_URL}
    ).encode()

    status_code, body = api_server.put(
        "/api/me",
        body=payload,
        headers={
            "Authorization": f"Bearer {_FIREBASE_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPutMeEndpoint:
    """PUT /api/me with valid payload and Bearer token must update the profile."""

    def test_status_code_is_200(self, put_me_response):
        """The response status must be HTTP 200 OK."""
        assert put_me_response["status_code"] == 200, (
            f"Expected HTTP 200, got {put_me_response['status_code']}. "
            f"Response body: {put_me_response['body']}"
        )

    def test_response_body_contains_username(self, put_me_response):
        """The JSON response body must contain the 'username' field."""
        body = json.loads(put_me_response["body"])
        assert "username" in body, (
            f"Expected 'username' field in response, got keys: {list(body.keys())}"
        )

    def test_response_username_matches_submitted_value(self, put_me_response):
        """The returned 'username' must equal the value sent in the PUT request."""
        body = json.loads(put_me_response["body"])
        assert body.get("username") == _NEW_USERNAME, (
            f"Expected username={_NEW_USERNAME!r}, got {body.get('username')!r}"
        )

    def test_response_body_contains_avatar_url(self, put_me_response):
        """The JSON response body must contain the 'avatar_url' field."""
        body = json.loads(put_me_response["body"])
        assert "avatar_url" in body, (
            f"Expected 'avatar_url' field in response, got keys: {list(body.keys())}"
        )

    def test_response_avatar_url_matches_submitted_value(self, put_me_response):
        """The returned 'avatar_url' must equal the value sent in the PUT request."""
        body = json.loads(put_me_response["body"])
        assert body.get("avatar_url") == _NEW_AVATAR_URL, (
            f"Expected avatar_url={_NEW_AVATAR_URL!r}, got {body.get('avatar_url')!r}"
        )

    def test_database_username_is_updated(self, put_me_response, db_conn):
        """The users table must reflect the new username after the PUT."""
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT username FROM users WHERE firebase_uid = %s",
                (_FIREBASE_TEST_UID,),
            )
            row = cur.fetchone()
        assert row is not None, "User row not found after PUT."
        assert row[0] == _NEW_USERNAME, (
            f"Expected DB username={_NEW_USERNAME!r}, got {row[0]!r}"
        )

    def test_database_avatar_url_is_updated(self, put_me_response, db_conn):
        """The users table must reflect the new avatar_url after the PUT."""
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT avatar_url FROM users WHERE firebase_uid = %s",
                (_FIREBASE_TEST_UID,),
            )
            row = cur.fetchone()
        assert row is not None, "User row not found after PUT."
        assert row[0] == _NEW_AVATAR_URL, (
            f"Expected DB avatar_url={_NEW_AVATAR_URL!r}, got {row[0]!r}"
        )
