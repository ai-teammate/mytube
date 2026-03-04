"""
MYTUBE-229: Update playlist title as non-owner — 403 Forbidden returned.

Objective:
    Ensure that only the owner of a playlist can modify its title.

Preconditions:
    - Playlist exists owned by User A.
    - User B is authenticated.

Steps:
    1. As User B, send a PUT request to /api/playlists/{Playlist_A_ID}
       with body { "title": "Hacked Title" }.

Expected Result:
    The API returns 403 Forbidden. The playlist title remains unchanged
    in the database.

Layer A — Go unit tests (always runs; no Firebase token or DB required):
    Runs TestPlaylistByIDHandler_PUT_Forbidden_Returns403 to verify that
    the handler returns 403 when the playlist store signals ErrForbidden.

Layer B — Integration test via HTTP (runs when FIREBASE_TEST_TOKEN is set):
    Seeds User A (the playlist owner, a synthetic DB-only user) and User B
    (the CI test user, identified by FIREBASE_TEST_TOKEN) in a local
    PostgreSQL database.  Creates a playlist owned by User A, then sends an
    authenticated PUT from User B and asserts HTTP 403.  Follows with a GET
    to confirm the title is unchanged.

Environment variables:
    FIREBASE_TEST_TOKEN   — Firebase ID token for the CI test user (User B).
                            Layer B is skipped when absent.
    FIREBASE_TEST_UID     — Firebase UID of the CI test user (default: "ci-test-user-001").
    FIREBASE_PROJECT_ID   — Firebase project ID (default: "ai-native-478811").
    API_BINARY            — Path to the compiled Go API binary
                            (default: <repo_root>/api/mytube-api).
    DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE
                          — PostgreSQL connection settings.
    GOOGLE_APPLICATION_CREDENTIALS
                          — Path to GCS service-account JSON
                            (falls back to testing/fixtures/mock_service_account.json).
    RAW_UPLOADS_BUCKET    — GCS bucket name (default: "mytube-raw-uploads").
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_DEFAULT_BINARY = os.path.join(_API_DIR, "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18229
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "ai-native-478811")
# User B is the CI test user whose token we hold.
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

# Synthetic User A — owns the playlist; has no real Firebase account.
_USER_A_FIREBASE_UID = "fake-user-a-mytube229"
_USER_A_USERNAME = "testuser_a_mytube229"

# User B — the CI test user who will attempt the forbidden update.
_USER_B_USERNAME = "testuser_b_mytube229"

_ORIGINAL_TITLE = "Original Title MYTUBE-229"
_HACKED_TITLE = "Hacked Title"


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


def _run_go_test(pattern: str) -> subprocess.CompletedProcess:
    """Run Go unit tests matching *pattern* in the handler package."""
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-run", pattern, "./internal/handler/"],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )


def _postgres_available(db_config: DBConfig) -> bool:
    """Return True if PostgreSQL is reachable."""
    try:
        import psycopg2
        conn = psycopg2.connect(db_config.dsn())
        conn.close()
        return True
    except Exception:
        return False


# ===========================================================================
# Layer A — Go unit tests (always run; no external services required)
# ===========================================================================


class TestPlaylistOwnershipGoUnit:
    """Run the Go unit test that covers 403 for a non-owner PUT."""

    def test_put_forbidden_returns_403(self):
        """TestPlaylistByIDHandler_PUT_Forbidden_Returns403 must pass.

        Verifies that when the playlist store signals ErrForbidden (owner
        mismatch), the handler writes HTTP 403 and not any other status code.
        """
        result = _run_go_test("TestPlaylistByIDHandler_PUT_Forbidden_Returns403")
        assert result.returncode == 0, (
            "Go unit test TestPlaylistByIDHandler_PUT_Forbidden_Returns403 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ===========================================================================
# Layer B — HTTP integration test via local API server
# Requires FIREBASE_TEST_TOKEN; skipped gracefully when absent.
# ===========================================================================


@pytest.fixture(scope="module")
def firebase_token() -> str:
    """Load the Firebase test token; skip Layer B tests when absent."""
    token = os.getenv("FIREBASE_TEST_TOKEN", "")
    if not token:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping HTTP integration tests "
            "(Layer A Go unit test still runs)."
        )
    return token


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def require_db(db_config: DBConfig):
    """Skip Layer B tests when PostgreSQL is not reachable."""
    if not _postgres_available(db_config):
        pytest.skip(
            f"PostgreSQL is not reachable at {db_config.host}:{db_config.port} — "
            "skipping Layer B integration tests."
        )


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig, firebase_token: str, require_db):
    """Build (if needed) and start the Go API server; stop on teardown."""
    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "GOOGLE_APPLICATION_CREDENTIALS": _MOCK_CREDS,
        "RAW_UPLOADS_BUCKET": _RAW_UPLOADS_BUCKET,
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
def db_conn(db_config: DBConfig, require_db):
    """Open a direct psycopg2 connection to the test database."""
    try:
        import psycopg2
    except ImportError:
        pytest.skip("psycopg2 not installed — skipping Layer B integration test.")

    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_test_data(api_server, db_conn):
    """Seed User A (owner), User B (CI test user), and a playlist owned by User A.

    Yields a dict with keys: playlist_id, original_title, user_a_id, user_b_id.
    Cleans up only the rows created for this test on teardown.
    """
    # Ensure User A exists (synthetic; no real Firebase account needed).
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO UPDATE SET username = EXCLUDED.username
            RETURNING id
            """,
            (_USER_A_FIREBASE_UID, _USER_A_USERNAME),
        )
        user_a_id = str(cur.fetchone()[0])

    # Ensure User B (CI test user) exists — the API will look them up by
    # firebase_uid when it validates their token.
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_TEST_UID, _USER_B_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        user_b_id = str(cur.fetchone()[0])

    # Create a playlist owned by User A.
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO playlists (owner_id, title) VALUES (%s, %s) RETURNING id",
            (user_a_id, _ORIGINAL_TITLE),
        )
        playlist_id = str(cur.fetchone()[0])

    yield {
        "playlist_id": playlist_id,
        "original_title": _ORIGINAL_TITLE,
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
    }

    # Teardown: remove only the data created for this test.
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM playlists WHERE id = %s", (playlist_id,))
        cur.execute(
            "DELETE FROM users WHERE firebase_uid = %s",
            (_USER_A_FIREBASE_UID,),
        )
        # Leave User B (CI test user) intact — other tests may depend on them.


@pytest.fixture(scope="module")
def auth_client_user_b(firebase_token: str) -> AuthService:
    """Return an AuthService for User B targeting the local test server."""
    return AuthService(base_url=f"http://127.0.0.1:{_PORT}", token=firebase_token)


@pytest.fixture(scope="module")
def put_response(seeded_test_data, auth_client_user_b: AuthService) -> tuple[int, str]:
    """Send PUT /api/playlists/{id} as User B; return (status_code, body)."""
    playlist_id = seeded_test_data["playlist_id"]
    return auth_client_user_b.put(
        f"/api/playlists/{playlist_id}",
        {"title": _HACKED_TITLE},
    )


# ---------------------------------------------------------------------------
# Integration test class
# ---------------------------------------------------------------------------


class TestUpdatePlaylistAsNonOwner:
    """MYTUBE-229: PUT /api/playlists/:id by a non-owner must return 403."""

    def test_non_owner_put_returns_403(self, put_response: tuple[int, str]):
        """PUT by User B (not the owner) must return HTTP 403 Forbidden."""
        status_code, body = put_response
        assert status_code == 403, (
            f"Expected HTTP 403 Forbidden when a non-owner updates a playlist title, "
            f"got {status_code}. Response body: {body}"
        )

    def test_response_body_is_json(self, put_response: tuple[int, str]):
        """403 response body must be valid JSON."""
        status_code, body = put_response
        if status_code != 403:
            pytest.skip(f"Skipping JSON assertion — status was {status_code}, not 403.")
        try:
            json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"403 response body is not valid JSON: {exc}\nBody: {body}"
            )

    def test_response_contains_error_message(self, put_response: tuple[int, str]):
        """403 response body must contain an error field."""
        status_code, body = put_response
        if status_code != 403:
            pytest.skip(f"Skipping error field assertion — status was {status_code}, not 403.")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            pytest.skip("Response body is not JSON — skipping error field check.")
        assert "error" in data, (
            f"Expected 'error' key in 403 response body. "
            f"Got keys: {list(data.keys())}. Body: {body}"
        )

    def test_playlist_title_unchanged_after_403(
        self,
        put_response: tuple[int, str],
        seeded_test_data,
        api_server,
    ):
        """After a 403, a public GET must show the playlist title is still the original.

        This confirms the rejected write did not mutate the stored title.
        """
        put_status, _ = put_response
        if put_status != 403:
            pytest.skip(
                f"Skipping title-unchanged check — PUT returned {put_status} instead of 403."
            )

        playlist_id = seeded_test_data["playlist_id"]
        original_title = seeded_test_data["original_title"]

        # GET /api/playlists/:id is a public endpoint; no auth needed.
        import urllib.request
        import urllib.error

        url = f"http://127.0.0.1:{_PORT}/api/playlists/{playlist_id}"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                get_status = resp.status
                get_body = resp.read().decode()
        except urllib.error.HTTPError as exc:
            get_status = exc.code
            get_body = exc.read().decode()

        assert get_status == 200, (
            f"Expected HTTP 200 from GET /api/playlists/{playlist_id}, got {get_status}. "
            f"Body: {get_body}"
        )

        try:
            data = json.loads(get_body)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"GET response body is not valid JSON: {exc}\nBody: {get_body}"
            )

        actual_title = data.get("title")
        assert actual_title == original_title, (
            f"Playlist title was mutated despite 403. "
            f"Expected {original_title!r}, got {actual_title!r}. "
            f"Full GET response: {get_body}"
        )
