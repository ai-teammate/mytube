"""
MYTUBE-227: Create new playlist via API — playlist created with title and owner metadata.

Objective
---------
Verify that an authenticated user can successfully create a new playlist via the API.

Preconditions
-------------
- User is authenticated with a valid Firebase token.

Steps
-----
1. Send a POST request to /api/playlists with body { "title": "My Workout Mix" }.
2. Inspect the API response.

Expected Result
---------------
- API returns 201 Created (or 200 OK).
- The response body contains a unique playlist id, the title "My Workout Mix",
  and the owner_username matching the authenticated user.

Test approach
-------------
- The deployed API (API_BASE_URL) processes the POST request with the CI user's
  Bearer token.
- The CI test user (FIREBASE_TEST_UID) must exist in the database before the
  request is issued; the fixture ensures the row is present (idempotent upsert).
- A direct Cloud SQL connection (cloud-sql-python-connector + pg8000) is used for
  DB-level assertions and teardown.
- PlaylistApiService encapsulates all POST /api/playlists HTTP interaction.

Environment variables
---------------------
FIREBASE_TEST_TOKEN        : Valid Firebase ID token for the CI test user.
                             Test is skipped when absent.
FIREBASE_TEST_UID          : firebase_uid of the CI test user
                             (default: ci-test-user-001).
FIREBASE_TEST_EMAIL        : Email of the CI test user (default: ci-test@mytube.test).
CLOUD_SQL_CONNECTION_NAME  : Cloud SQL instance connection name
                             (default: ai-native-478811:us-central1:learn-ai-db).
API_BASE_URL               : Deployed API base URL.
                             Default: https://mytube-api-80693608388.us-central1.run.app
DB_USER                    : Database user (default: mytube).
DB_PASSWORD                : Database password.
DB_NAME                    : Database name (default: mytube).

Architecture
------------
- PlaylistApiService encapsulates POST /api/playlists HTTP interaction.
- Cloud SQL Python connector provides the direct database connection for seeding
  and teardown.
- No hardcoded credentials — only well-known CI defaults are referenced.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.playlist_api_service import PlaylistApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEPLOYED_API_URL = "https://mytube-api-80693608388.us-central1.run.app"
_API_BASE_URL = os.getenv("API_BASE_URL", _DEPLOYED_API_URL)

# Firebase credentials — required; test skips when absent.
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")

# CI test user identity.
_CI_USER_FIREBASE_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")
_CI_USER_EMAIL = os.getenv("FIREBASE_TEST_EMAIL", "ci-test@mytube.test")
_CI_USERNAME = "ci_test_user_227"

# Playlist to create.
_PLAYLIST_TITLE = "My Workout Mix"

# Cloud SQL — used for direct database access.
_CLOUD_SQL_INSTANCE = os.getenv(
    "CLOUD_SQL_CONNECTION_NAME", "ai-native-478811:us-central1:learn-ai-db"
)
_DB_USER = os.getenv("DB_USER", "mytube")
_DB_PASS = os.getenv("DB_PASSWORD", "")
_DB_NAME = os.getenv("DB_NAME", "mytube")

# UUID pattern for validation.
import re
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_uuid(value: str) -> bool:
    """Return True if *value* is a well-formed UUID string."""
    return bool(_UUID_RE.match(str(value)))


def _cloud_sql_connect():
    """Open a synchronous pg8000 connection to Cloud SQL via the connector.

    Returns (conn, connector); caller is responsible for closing both.
    Raises ImportError if cloud-sql-python-connector is not installed.
    """
    from google.cloud.sql.connector import Connector  # type: ignore

    connector = Connector()
    conn = connector.connect(
        _CLOUD_SQL_INSTANCE,
        "pg8000",
        user=_DB_USER,
        password=_DB_PASS,
        db=_DB_NAME,
    )
    conn.autocommit = True
    return conn, connector


def _api_is_reachable(base_url: str) -> bool:
    """Return True if the API /health endpoint responds successfully."""
    import urllib.request

    try:
        resp = urllib.request.urlopen(f"{base_url}/health", timeout=5)
        return resp.status < 500
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_token():
    """Skip the entire module when FIREBASE_TEST_TOKEN is not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-227 playlist creation "
            "test. Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run."
        )


@pytest.fixture(scope="module", autouse=True)
def require_api(require_firebase_token):
    """Skip when the deployed API is not reachable."""
    if not _api_is_reachable(_API_BASE_URL):
        pytest.skip(
            f"API at {_API_BASE_URL} is not reachable — "
            "skipping MYTUBE-227 integration test."
        )


@pytest.fixture(scope="module")
def db_conn(require_api):
    """Open a direct Cloud SQL connection for test-data seeding and teardown.

    Skips when cloud-sql-python-connector is not installed or the connection
    cannot be established.
    """
    try:
        conn, connector = _cloud_sql_connect()
    except ImportError:
        pytest.skip(
            "cloud-sql-python-connector is not installed. "
            "Run: pip install 'cloud-sql-python-connector[pg8000]'"
        )
    except Exception as exc:
        pytest.skip(f"Cannot connect to Cloud SQL: {exc}")

    yield conn

    try:
        conn.close()
        connector.close()
    except Exception:
        pass


@pytest.fixture(scope="module")
def seeded_user(db_conn):
    """Ensure the CI test user row exists in the database (idempotent upsert).

    Returns a dict with the user's id and username so tests can assert
    the owner_username field in the API response.
    """
    cur = db_conn.cursor()
    cur.execute(
        "SELECT id, username FROM users WHERE firebase_uid = %s",
        (_CI_USER_FIREBASE_UID,),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) RETURNING id, username",
            (_CI_USER_FIREBASE_UID, _CI_USERNAME),
        )
        row = cur.fetchone()

    return {"id": str(row[0]), "username": str(row[1])}


@pytest.fixture(scope="module")
def playlist_service() -> PlaylistApiService:
    """Return a PlaylistApiService pointing at the deployed API with the CI user's token."""
    return PlaylistApiService(base_url=_API_BASE_URL, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def create_response(seeded_user, playlist_service: PlaylistApiService) -> dict:
    """Send POST /api/playlists with title 'My Workout Mix'; return the result.

    Stores the created playlist id for teardown.
    """
    status_code, body = playlist_service.create_playlist(_PLAYLIST_TITLE)
    return {"status_code": status_code, "body": body}


@pytest.fixture(scope="module", autouse=True)
def cleanup_playlist(db_conn, seeded_user, create_response):
    """Yield, then delete the test playlist row created during the test."""
    yield

    # Only attempt cleanup when a playlist was actually created.
    if create_response.get("status_code") not in (200, 201):
        return

    try:
        body = json.loads(create_response["body"])
        playlist_id = body.get("id")
        if playlist_id:
            cur = db_conn.cursor()
            cur.execute("DELETE FROM playlists WHERE id = %s", (playlist_id,))
    except Exception:
        pass  # Best-effort teardown — do not fail the test suite.


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreatePlaylist:
    """POST /api/playlists with a valid payload and Bearer token must succeed."""

    def test_status_code_is_201(self, create_response: dict) -> None:
        """The response status must be HTTP 201 Created.

        The test also accepts 200 OK as some implementations use it, but the
        primary expectation per the spec is 201.
        """
        assert create_response["status_code"] in (200, 201), (
            f"Expected HTTP 201 (or 200), got {create_response['status_code']}. "
            f"Response body: {create_response['body']}"
        )

    def test_response_body_is_valid_json(self, create_response: dict) -> None:
        """The response body must be parseable JSON."""
        try:
            json.loads(create_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\nBody: {create_response['body']}"
            )

    def test_response_contains_id(self, create_response: dict) -> None:
        """The JSON response must contain an 'id' key."""
        body = json.loads(create_response["body"])
        assert "id" in body, (
            f"Expected 'id' key in response, got keys: {list(body.keys())}. "
            f"Body: {create_response['body']}"
        )

    def test_response_id_is_uuid(self, create_response: dict) -> None:
        """The 'id' value must be a valid UUID string."""
        body = json.loads(create_response["body"])
        playlist_id = body.get("id", "")
        assert _is_uuid(str(playlist_id)), (
            f"Expected 'id' to be a UUID, got: {playlist_id!r}"
        )

    def test_response_contains_title(self, create_response: dict) -> None:
        """The JSON response must contain the 'title' key."""
        body = json.loads(create_response["body"])
        assert "title" in body, (
            f"Expected 'title' key in response, got keys: {list(body.keys())}. "
            f"Body: {create_response['body']}"
        )

    def test_response_title_matches_request(self, create_response: dict) -> None:
        """The returned 'title' must equal the title sent in the POST request."""
        body = json.loads(create_response["body"])
        assert body.get("title") == _PLAYLIST_TITLE, (
            f"Expected title={_PLAYLIST_TITLE!r}, got {body.get('title')!r}"
        )

    def test_response_contains_owner_username(self, create_response: dict) -> None:
        """The JSON response must contain an 'owner_username' key."""
        body = json.loads(create_response["body"])
        assert "owner_username" in body, (
            f"Expected 'owner_username' key in response, got keys: {list(body.keys())}. "
            f"Body: {create_response['body']}"
        )

    def test_response_owner_username_matches_authenticated_user(
        self, create_response: dict, seeded_user: dict
    ) -> None:
        """The 'owner_username' must match the username of the authenticated CI user."""
        body = json.loads(create_response["body"])
        expected_username = seeded_user["username"]
        actual_username = body.get("owner_username")
        assert actual_username == expected_username, (
            f"Expected owner_username={expected_username!r}, "
            f"got {actual_username!r}. "
            "The playlist must be attributed to the user whose token was used."
        )
