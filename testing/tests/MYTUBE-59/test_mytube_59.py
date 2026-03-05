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
  3. Waits until the server is ready using HTTP-level polling (via ApiProcessService).
  4. Issues GET /api/me with the bearer token from FIREBASE_TEST_TOKEN.
  5. Asserts the HTTP 200 response.
  6. Queries the users table via UserService and asserts the auto-provisioned row.
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
import subprocess
import sys

import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.auth_service import AuthService
from testing.components.services.user_service import UserService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SERVER_BINARY = os.getenv(
    "API_SERVER_BINARY",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "api", "server"),
)

SERVER_STARTUP_TIMEOUT = 15  # seconds


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _email_prefix(email: str) -> str:
    """Return the local part (prefix) of an email address."""
    idx = email.find("@")
    return email[:idx] if idx >= 0 else email


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


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
def raw_conn(db_config: DBConfig):
    """Open a plain psycopg2 connection without dropping or recreating the schema.

    This is intentionally separate from the shared ``conn`` fixture in conftest.py,
    which drops all tables.  MYTUBE-59 must NOT drop tables after the API server has
    already inserted a user row — that would destroy the data we are trying to verify.
    Instead this fixture only opens a connection and closes it on teardown.
    """
    import psycopg2
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True
    yield connection
    connection.close()


@pytest.fixture(scope="module")
def api_server(api_config: APIConfig, db_config: DBConfig, firebase_credentials: dict):
    """Build (if needed) and start the Go API server via ApiProcessService; yield; stop.

    The server is responsible for running its own DB migrations on startup.
    The database must be in a fully clean state before this fixture runs so
    that golang-migrate can apply all migrations from scratch without
    encountering pre-existing objects.
    """
    import psycopg2

    # --- Clean the database so the API server's own migrations start fresh ---
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    with conn.cursor() as cur:
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
    conn.close()

    # --- Build binary if needed ---
    api_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..", "api")
    binary = SERVER_BINARY

    if not os.path.isfile(binary):
        build_result = subprocess.run(
            ["go", "build", "-o", binary, "."],
            cwd=api_dir,
            capture_output=True,
            text=True,
        )
        if build_result.returncode != 0:
            pytest.fail(f"Failed to build API server:\n{build_result.stderr}")

    url_parts = api_config.base_url.split(":")
    port = int(url_parts[-1])

    svc = ApiProcessService(
        binary_path=binary,
        port=port,
        startup_timeout=SERVER_STARTUP_TIMEOUT,
        env={
            "DB_HOST": db_config.host,
            "DB_PORT": str(db_config.port),
            "DB_USER": db_config.user,
            "DB_PASSWORD": db_config.password,
            "DB_NAME": db_config.dbname,
            "SSL_MODE": db_config.sslmode,
            "FIREBASE_PROJECT_ID": firebase_credentials["project_id"],
            "RAW_UPLOADS_BUCKET": "test-bucket",
        },
    )
    svc.start()
    if not svc.wait_for_ready():
        pytest.fail(f"API server did not become ready.\n{svc.get_log_output()}")
    yield svc
    svc.stop()


@pytest.fixture(scope="module")
def auth_service(api_config: APIConfig, firebase_credentials: dict) -> AuthService:
    """Return an AuthService configured with the test Firebase token."""
    return AuthService(base_url=api_config.base_url, token=firebase_credentials["token"])


@pytest.fixture(scope="module")
def me_response(api_server, auth_service: AuthService) -> tuple[int, str]:
    """Issue GET /api/me once and share the result across the test class."""
    return auth_service.get("/api/me")


@pytest.fixture(scope="module")
def user_row(me_response, raw_conn, firebase_credentials):
    """Retrieve the auto-provisioned user row via UserService.

    Uses ``raw_conn`` (a plain connection with no schema mutations) so the
    user row written by the API server during ``me_response`` is still present
    when we query it here.
    """
    return UserService(raw_conn).find_by_firebase_uid(firebase_credentials["uid"])


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

    def test_user_row_exists_in_database(self, user_row, firebase_credentials):
        """After GET /api/me, the users table must contain a row for this Firebase UID."""
        assert user_row is not None, (
            f"No row found in users table for firebase_uid='{firebase_credentials['uid']}'. "
            "Auto-provisioning did not insert the expected record."
        )

    def test_user_row_has_generated_uuid(self, user_row):
        """The auto-provisioned user row must have a non-empty UUID as its id."""
        import re
        assert user_row is not None, "User row not found (see test_user_row_exists_in_database)"
        user_id = user_row["id"]
        assert user_id, "User id must not be empty"
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )
        assert uuid_pattern.match(user_id), (
            f"User id '{user_id}' is not a valid UUID format"
        )

    def test_user_row_has_correct_firebase_uid(self, user_row, firebase_credentials):
        """The users row must store the Firebase UID from the token."""
        assert user_row is not None, "User row not found (see test_user_row_exists_in_database)"
        assert user_row["firebase_uid"] == firebase_credentials["uid"], (
            f"Expected firebase_uid '{firebase_credentials['uid']}', "
            f"got '{user_row['firebase_uid']}'"
        )

    def test_user_row_has_username_from_email_prefix(self, user_row, firebase_credentials):
        """The users row must have a username equal to the email prefix."""
        assert user_row is not None, "User row not found (see test_user_row_exists_in_database)"
        expected_username = _email_prefix(firebase_credentials["email"])
        assert user_row["username"] == expected_username, (
            f"Expected username '{expected_username}', got '{user_row['username']}'"
        )
