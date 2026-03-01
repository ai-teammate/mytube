"""
MYTUBE-62: Call GET /api/me — returns current user profile data.

Verifies that the /api/me endpoint returns the authenticated user's
identification and profile details.

Preconditions
-------------
- A user exists in the database with a firebase_uid matching the token.
- The API server is running with a valid DB connection and Firebase project.

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a user row via direct DB access using a known firebase_uid.
3. Send GET /api/me with Authorization: Bearer <FIREBASE_TEST_TOKEN>.
4. Assert HTTP 200, and that the JSON body contains id (UUID), username,
   and avatar_url.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN : Firebase ID token for the test user.
                        Test is skipped when absent.
- FIREBASE_PROJECT_ID : Firebase project ID required to initialise the
                        verifier.  Test is skipped when absent.
- API_BINARY          : Path to the pre-built Go binary
                        (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                        Database connection settings (all have sensible
                        defaults matching the test DB configuration).
- FIREBASE_TEST_UID   : The firebase_uid stored in the users row that
                        should match the test token.  When absent the
                        test falls back to pre-inserting a row and relies
                        on the server's upsert behaviour to provision it.

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- UserService provides the direct-DB user insertion helper.
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
"""
import json
import os
import re
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.user_service import UserService

import psycopg2

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18085
_STARTUP_TIMEOUT = 20.0

# Firebase test credentials (required at runtime; test skips when absent).
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# The firebase_uid that the test token belongs to.  When not provided
# explicitly the server's upsert will create the row on first /api/me call
# using the UID embedded in the token — but we still need a pre-existing row
# for the assertion that id / username are returned correctly.
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-62")


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


def _is_uuid(value: str) -> bool:
    """Return True if *value* looks like a UUID."""
    uuid_re = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
        re.IGNORECASE,
    )
    return bool(uuid_re.match(value))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials():
    """Skip the entire module when Firebase credentials are not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping /api/me integration test. "
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
    """
    Open a direct psycopg2 connection to the test database for setup / teardown.

    The server has already applied migrations by the time this fixture is used
    (the api_server fixture starts the server which runs migrations on boot).
    """
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_user(api_server, db_conn):
    """
    Insert a user row with a known firebase_uid so the /api/me handler can
    find / upsert it.

    The INSERT uses ON CONFLICT DO NOTHING to be safe if the row already
    exists (e.g. from a previous partially-completed test run).

    Returns a dict with the inserted user's id, firebase_uid, and username.
    """
    user_svc = UserService(db_conn)

    # Derive a deterministic username from the firebase_uid.
    username = "testuser62"

    # Use raw SQL here because UserService.create_user raises on duplicate;
    # we want idempotent setup.
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
def me_response(api_server, seeded_user):
    """Issue GET /api/me with the Firebase Bearer token and capture the response."""
    status_code, body = api_server.get(
        "/api/me",
        headers={"Authorization": f"Bearer {_FIREBASE_TOKEN}"},
    )
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetMeEndpoint:
    """GET /api/me with a valid Bearer token must return 200 and user profile."""

    def test_status_code_is_200(self, me_response):
        """The response status must be HTTP 200 OK."""
        assert me_response["status_code"] == 200, (
            f"Expected HTTP 200, got {me_response['status_code']}. "
            f"Response body: {me_response['body']}"
        )

    def test_response_body_contains_id(self, me_response):
        """The JSON body must contain the 'id' field."""
        body = json.loads(me_response["body"])
        assert "id" in body, (
            f"Expected 'id' field in response, got keys: {list(body.keys())}"
        )

    def test_id_is_uuid(self, me_response):
        """The 'id' field must be a valid UUID string."""
        body = json.loads(me_response["body"])
        user_id = body.get("id", "")
        assert _is_uuid(user_id), (
            f"Expected 'id' to be a UUID, got: {user_id!r}"
        )

    def test_response_body_contains_username(self, me_response):
        """The JSON body must contain the 'username' field."""
        body = json.loads(me_response["body"])
        assert "username" in body, (
            f"Expected 'username' field in response, got keys: {list(body.keys())}"
        )

    def test_username_is_non_empty_string(self, me_response):
        """The 'username' value must be a non-empty string."""
        body = json.loads(me_response["body"])
        username = body.get("username", "")
        assert isinstance(username, str) and username, (
            f"Expected a non-empty string for 'username', got: {username!r}"
        )

    def test_response_body_contains_avatar_url_key(self, me_response):
        """The JSON body must contain the 'avatar_url' key (may be null)."""
        body = json.loads(me_response["body"])
        assert "avatar_url" in body, (
            f"Expected 'avatar_url' key in response, got keys: {list(body.keys())}"
        )
