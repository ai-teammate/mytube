"""
MYTUBE-59: Authenticate with valid new Firebase token — user auto-provisioned in database.

Verifies that when a new user sends their first request to a protected endpoint
(GET /api/me) with a valid Firebase ID token, the API:
  1. Returns HTTP 200 OK.
  2. Automatically inserts a new row into the ``users`` table with:
       - a generated UUID as ``id``
       - the correct ``firebase_uid`` (matching the UID in the token)
       - a ``username`` derived from the email prefix (the part before "@")

The test manages the full lifecycle:
  1. Drops and recreates the database schema from scratch (clean state).
  2. Starts the Go API server process with database env vars and FIREBASE_PROJECT_ID.
  3. Waits until the server is ready using socket-level polling.
  4. Issues GET /api/me with the bearer token from FIREBASE_TEST_TOKEN.
  5. Asserts the HTTP 200 response.
  6. Queries the users table and asserts the auto-provisioned row.
  7. Tears down the server and database connection.

Environment variables required:
  - FIREBASE_TEST_TOKEN   — a valid Firebase ID token for a user not yet in the DB
  - FIREBASE_TEST_UID     — the Firebase UID that the token encodes
  - FIREBASE_TEST_EMAIL   — the email address associated with the token
  - FIREBASE_PROJECT_ID   — Firebase project the token was issued for
  - DB_*                  — PostgreSQL connection parameters (see core/config/db_config.py)
  - API_SERVER_BINARY     — path to the pre-built Go server binary (optional)
"""
import json
import os
import socket
import subprocess
import sys
import time

import psycopg2
import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVER_BINARY = os.getenv(
    "API_SERVER_BINARY",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "api", "server"),
)

SERVER_STARTUP_TIMEOUT = 15  # seconds
SOCKET_POLL_INTERVAL = 0.2   # seconds per socket probe

MIGRATION_SQL = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "api",
    "migrations",
    "0001_initial_schema.up.sql",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wait_for_server(host: str, port: int, proc: subprocess.Popen, timeout: float) -> None:
    """Block until the server's TCP port accepts connections or timeout elapses.

    Uses socket-level probing rather than time.sleep to implement an explicit
    wait as required by the test architecture rules.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            stdout = proc.stdout.read().decode()
            stderr = proc.stderr.read().decode()
            pytest.fail(
                f"API server exited unexpectedly before becoming ready.\n"
                f"stdout: {stdout}\nstderr: {stderr}"
            )
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(SOCKET_POLL_INTERVAL)
            if sock.connect_ex((host, port)) == 0:
                return
    proc.terminate()
    proc.wait(timeout=5)
    stdout = proc.stdout.read().decode()
    stderr = proc.stderr.read().decode()
    pytest.fail(
        f"API server did not become ready within {timeout}s.\n"
        f"stdout: {stdout}\nstderr: {stderr}"
    )


def _email_prefix(email: str) -> str:
    """Return the local part (prefix) of an email address."""
    idx = email.find("@")
    return email[:idx] if idx >= 0 else email


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """Open a direct psycopg2 connection; rebuild schema; yield; close."""
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    # Drop all public tables for a clean slate.
    with connection.cursor() as cur:
        cur.execute(
            """
            DO $$ DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
            """
        )
        cur.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE;")

    # Apply the migration.
    with open(MIGRATION_SQL, "r") as fh:
        migration_sql = fh.read()
    with connection.cursor() as cur:
        cur.execute(migration_sql)

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def firebase_credentials() -> dict:
    """Load Firebase token and associated claims from environment variables.

    Raises pytest.skip when the required env vars are absent so that the test
    is skipped gracefully rather than failing with an uninformative KeyError.
    """
    token = os.getenv("FIREBASE_TEST_TOKEN", "")
    uid = os.getenv("FIREBASE_TEST_UID", "")
    email = os.getenv("FIREBASE_TEST_EMAIL", "")
    project_id = os.getenv("FIREBASE_PROJECT_ID", "")

    missing = [
        name
        for name, val in [
            ("FIREBASE_TEST_TOKEN", token),
            ("FIREBASE_TEST_UID", uid),
            ("FIREBASE_TEST_EMAIL", email),
            ("FIREBASE_PROJECT_ID", project_id),
        ]
        if not val
    ]
    if missing:
        pytest.skip(f"Required env vars not set: {', '.join(missing)}")

    return {"token": token, "uid": uid, "email": email, "project_id": project_id}


@pytest.fixture(scope="module")
def api_server(api_config: APIConfig, db_config: DBConfig, firebase_credentials: dict):
    """Build (if needed) and start the Go API server; yield; terminate."""
    api_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "api")
    binary = SERVER_BINARY

    # Build the binary if it doesn't exist yet.
    if not os.path.isfile(binary):
        build_result = subprocess.run(
            ["go", "build", "-o", binary, "."],
            cwd=api_dir,
            capture_output=True,
            text=True,
        )
        if build_result.returncode != 0:
            pytest.fail(f"Failed to build API server:\n{build_result.stderr}")

    # Parse host and port from base_url (format: http://host:port)
    url_parts = api_config.base_url.split(":")
    host = url_parts[1].lstrip("/")
    port = int(url_parts[-1])

    env = {
        **os.environ,
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "PORT": str(port),
        "FIREBASE_PROJECT_ID": firebase_credentials["project_id"],
    }

    proc = subprocess.Popen(
        [binary],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    _wait_for_server(host, port, proc, SERVER_STARTUP_TIMEOUT)

    yield proc

    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(scope="module")
def auth_service(api_config: APIConfig, firebase_credentials: dict) -> AuthService:
    """Return an AuthService configured with the test Firebase token."""
    return AuthService(base_url=api_config.base_url, token=firebase_credentials["token"])


@pytest.fixture(scope="module")
def me_response(api_server, auth_service: AuthService) -> tuple[int, str]:
    """Issue GET /api/me once and share the result across the test class."""
    return auth_service.get("/api/me")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFirebaseAutoProvision:
    """GET /api/me with a new Firebase token must return 200 and create a user row."""

    def test_returns_200_ok(self, me_response):
        """The API must return HTTP 200 OK for a valid new Firebase token."""
        status_code, body = me_response
        assert status_code == 200, (
            f"Expected HTTP 200 for valid Firebase token, got {status_code}. "
            f"Response body: {body}"
        )

    def test_response_body_is_valid_json(self, me_response):
        """The response body must be valid JSON."""
        _, body = me_response
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(f"Response body is not valid JSON: {exc}\nBody: {body}")

    def test_response_body_contains_id(self, me_response):
        """The response JSON must contain a non-empty 'id' field."""
        _, body = me_response
        data = json.loads(body)
        assert "id" in data, f"Response JSON missing 'id' field: {data}"
        assert data["id"], f"Response 'id' field must not be empty: {data}"

    def test_response_body_contains_username(self, me_response, firebase_credentials):
        """The response JSON must contain a 'username' derived from the email prefix."""
        _, body = me_response
        data = json.loads(body)
        expected_username = _email_prefix(firebase_credentials["email"])
        assert "username" in data, f"Response JSON missing 'username' field: {data}"
        assert data["username"] == expected_username, (
            f"Expected username '{expected_username}' (email prefix of "
            f"'{firebase_credentials['email']}'), got '{data['username']}'"
        )

    def test_user_row_exists_in_database(self, me_response, conn, firebase_credentials):
        """After GET /api/me, the users table must contain a row for this Firebase UID."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, firebase_uid, username FROM users WHERE firebase_uid = %s",
                (firebase_credentials["uid"],),
            )
            row = cur.fetchone()

        assert row is not None, (
            f"No row found in users table for firebase_uid='{firebase_credentials['uid']}'. "
            "Auto-provisioning did not insert the expected record."
        )

    def test_user_row_has_generated_uuid(self, me_response, conn, firebase_credentials):
        """The auto-provisioned user row must have a non-empty UUID as its id."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE firebase_uid = %s",
                (firebase_credentials["uid"],),
            )
            row = cur.fetchone()

        assert row is not None, "User row not found (see test_user_row_exists_in_database)"
        user_id = str(row[0])
        assert user_id, "User id must not be empty"
        # UUID format: 8-4-4-4-12 hex digits
        import re
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        assert uuid_pattern.match(user_id), (
            f"User id '{user_id}' is not a valid UUID format"
        )

    def test_user_row_has_correct_firebase_uid(self, me_response, conn, firebase_credentials):
        """The users row must store the Firebase UID from the token."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT firebase_uid FROM users WHERE firebase_uid = %s",
                (firebase_credentials["uid"],),
            )
            row = cur.fetchone()

        assert row is not None, "User row not found (see test_user_row_exists_in_database)"
        assert row[0] == firebase_credentials["uid"], (
            f"Expected firebase_uid '{firebase_credentials['uid']}', "
            f"got '{row[0]}'"
        )

    def test_user_row_has_username_from_email_prefix(
        self, me_response, conn, firebase_credentials
    ):
        """The users row must have a username equal to the email prefix."""
        expected_username = _email_prefix(firebase_credentials["email"])
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username FROM users WHERE firebase_uid = %s",
                (firebase_credentials["uid"],),
            )
            row = cur.fetchone()

        assert row is not None, "User row not found (see test_user_row_exists_in_database)"
        assert row[0] == expected_username, (
            f"Expected username '{expected_username}', got '{row[0]}'"
        )
