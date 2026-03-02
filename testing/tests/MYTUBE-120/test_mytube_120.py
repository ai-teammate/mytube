"""
MYTUBE-120: Public profile accessibility — GET /api/users/:username requires no auth token.

Verifies that the public profile endpoint is accessible without any
Authorization header, returns HTTP 200, and provides the expected profile
structure (username and videos array).

Preconditions
-------------
- User is not logged into the application (no Authorization header sent).
- A user with a known username exists in the database.

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a user row with a known username via direct DB access.
3. Send GET /api/users/<username> without any Authorization header.
4. Assert HTTP 200 — no 401 or 403 error.
5. Assert the response body contains the expected fields: username and videos.
6. Assert that the username in the response matches the requested username.
7. Assert that the videos field is a list (may be empty).

Environment variables
---------------------
- API_BINARY          : Path to the pre-built Go binary
                        (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                        Database connection settings (all have sensible
                        defaults matching the test DB configuration).

Architecture notes
------------------
- No Firebase token is required; this endpoint is intentionally unauthenticated.
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- Direct psycopg2 SQL is used for idempotent test-user setup (ON CONFLICT DO NOTHING).
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
- The FIREBASE_PROJECT_ID env var is still passed to the server so it can
  start the Firebase verifier (needed for other protected routes to initialise),
  but this test does not supply any token.
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

_PORT = 18120
_STARTUP_TIMEOUT = 20.0

# Firebase project ID is required by the server to initialise the verifier,
# even though this test sends no token.  If absent, use a placeholder that
# allows the server to start (the verifier is only invoked on protected routes).
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "test-project")

# The username that will be inserted and then looked up via the public endpoint.
_TEST_USERNAME = "pubuser120"
_TEST_FIREBASE_UID = "test-uid-mytube-120"


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
    """Open a direct psycopg2 connection to the test database for setup."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_user(api_server, db_conn):
    """
    Insert a user row with a known username so the public profile endpoint
    can resolve it.

    Uses ON CONFLICT DO NOTHING for idempotency across re-runs.
    Returns a dict with the user's id, firebase_uid, and username.
    """
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_TEST_FIREBASE_UID, _TEST_USERNAME),
        )
        cur.execute(
            "SELECT id, firebase_uid, username, avatar_url FROM users WHERE firebase_uid = %s",
            (_TEST_FIREBASE_UID,),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_TEST_FIREBASE_UID!r}"
        )

    return {
        "id": str(row[0]),
        "firebase_uid": row[1],
        "username": row[2],
        "avatar_url": row[3],
    }


@pytest.fixture(scope="module")
def public_profile_response(api_server, seeded_user):
    """
    Issue GET /api/users/<username> with NO Authorization header and capture
    the response.  This is the core assertion: the endpoint must be publicly
    accessible.
    """
    status_code, body = api_server.get(
        f"/api/users/{_TEST_USERNAME}",
        # Deliberately no Authorization header.
        headers={},
    )
    return {"status_code": status_code, "body": body, "username": _TEST_USERNAME}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPublicProfileAccessibility:
    """GET /api/users/:username without an Authorization header must return 200."""

    def test_status_code_is_200(self, public_profile_response):
        """The response must be HTTP 200, not 401 or 403."""
        assert public_profile_response["status_code"] == 200, (
            f"Expected HTTP 200, got {public_profile_response['status_code']}. "
            f"Response body: {public_profile_response['body']}"
        )

    def test_response_body_is_valid_json(self, public_profile_response):
        """The response body must be parseable as JSON."""
        try:
            json.loads(public_profile_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\n"
                f"Body: {public_profile_response['body']}"
            )

    def test_response_contains_username_field(self, public_profile_response):
        """The JSON body must contain the 'username' field."""
        body = json.loads(public_profile_response["body"])
        assert "username" in body, (
            f"Expected 'username' field in response, got keys: {list(body.keys())}"
        )

    def test_response_username_matches_requested_username(self, public_profile_response):
        """The 'username' in the response must match the requested username."""
        body = json.loads(public_profile_response["body"])
        assert body.get("username") == _TEST_USERNAME, (
            f"Expected username={_TEST_USERNAME!r}, got {body.get('username')!r}"
        )

    def test_response_contains_videos_field(self, public_profile_response):
        """The JSON body must contain the 'videos' field."""
        body = json.loads(public_profile_response["body"])
        assert "videos" in body, (
            f"Expected 'videos' field in response, got keys: {list(body.keys())}"
        )

    def test_videos_field_is_a_list(self, public_profile_response):
        """The 'videos' field must be a list (may be empty for a new user)."""
        body = json.loads(public_profile_response["body"])
        videos = body.get("videos")
        assert isinstance(videos, list), (
            f"Expected 'videos' to be a list, got {type(videos).__name__!r}: {videos!r}"
        )

    def test_no_authorization_header_was_sent(self, public_profile_response):
        """Confirm the test itself sent no auth header — i.e. the 200 is not due to a token."""
        # This test documents the test setup: the fixture explicitly passes no
        # Authorization header.  If we got HTTP 200 without a token, the endpoint
        # is correctly unauthenticated.
        assert public_profile_response["status_code"] == 200, (
            "HTTP 200 was expected without any Authorization header, confirming "
            "the endpoint does not require Firebase Auth."
        )
