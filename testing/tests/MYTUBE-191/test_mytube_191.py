"""
MYTUBE-191: Delete video as non-owner — 403 Forbidden returned.

Verifies that authenticated users cannot delete videos owned by other users.

Preconditions
-------------
- User A is authenticated (FIREBASE_TEST_TOKEN is set).
- Video B is owned by User C (a different user in the database).

Test steps
----------
1. Build and start the Go API server with valid DB credentials and FIREBASE_PROJECT_ID.
2. Pre-insert User A (FIREBASE_TEST_UID) in DB using ON CONFLICT DO NOTHING.
3. Pre-insert User C (a synthetic test-only owner) in DB.
4. Pre-insert Video B owned by User C with status 'ready'.
5. User A sends DELETE /api/videos/{Video_B_id} with Authorization: Bearer <FIREBASE_TEST_TOKEN>.
6. Assert HTTP 403 Forbidden.
7. Assert the video still exists in the DB with status 'ready' (unchanged).

Environment variables
---------------------
- FIREBASE_TEST_TOKEN   : Firebase ID token for User A (the non-owner).
                          Test is skipped when absent.
- FIREBASE_PROJECT_ID   : Firebase project ID required to initialise the
                          token verifier.  Test is skipped when absent.
- FIREBASE_TEST_UID     : firebase_uid for User A.
                          Defaults to 'ci-test-user-001'.
- API_BINARY            : Path to the pre-built Go binary
                          (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                          Database connection settings.

Architecture notes
------------------
- AuthService.delete() issues an authenticated DELETE with a Bearer token.
- Direct psycopg2 SQL is used for test data setup and DB-state assertions.
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
- Video teardown is handled in the seeded_video fixture.
"""
import os
import subprocess
import sys

import psycopg2
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
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18091
_STARTUP_TIMEOUT = 20.0

# Firebase credentials for User A (the non-owner who attempts the delete).
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

# Synthetic DB-only owner (User C) — has no Firebase token.
_OWNER_UID = "test-owner-mytube-191"
_OWNER_USERNAME = "testowner-mytube191"
_NON_OWNER_USERNAME = "testnonowner-mytube191"


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
            "FIREBASE_TEST_TOKEN not set — skipping delete-as-non-owner test. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run this test."
        )
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — the API server cannot initialise "
            "the Firebase token verifier without this variable."
        )
    # Verify the database is reachable before attempting to seed data.
    db = DBConfig()
    try:
        conn = psycopg2.connect(db.dsn())
        conn.close()
    except Exception:
        pytest.skip(
            f"PostgreSQL is not reachable at {db.host}:{db.port} — "
            "start a PostgreSQL instance and set DB_HOST / DB_PORT (or ensure "
            "the default localhost:5432 is running) before running this test."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """Build (if needed) and start the Go API server in a subprocess.

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
    """Open a direct psycopg2 connection for test data setup and assertions."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_users(api_server, db_conn):
    """Insert User A (non-owner) and User C (owner) into the database.

    Uses ON CONFLICT DO NOTHING for idempotent setup — safe to re-run.

    Returns a dict with ``user_a_id`` and ``user_c_id``.
    """
    with db_conn.cursor() as cur:
        # User A — the non-owner who will attempt the delete.
        # Uses FIREBASE_TEST_UID so the Bearer token resolves to this user.
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_TEST_UID, _NON_OWNER_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()
        if row is None:
            pytest.fail(
                f"Could not find User A (firebase_uid={_FIREBASE_TEST_UID!r}) in DB."
            )
        user_a_id = str(row[0])

        # User C — the synthetic video owner (DB-only, no Firebase token).
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_OWNER_UID, _OWNER_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_OWNER_UID,),
        )
        row = cur.fetchone()
        if row is None:
            pytest.fail(
                f"Could not find User C (firebase_uid={_OWNER_UID!r}) in DB."
            )
        user_c_id = str(row[0])

    return {"user_a_id": user_a_id, "user_c_id": user_c_id}


@pytest.fixture(scope="module")
def seeded_video(api_server, db_conn, seeded_users):
    """Insert Video B owned by User C with status 'ready'.

    Yields the video UUID string.  Removes the row on teardown.
    """
    user_c_id = seeded_users["user_c_id"]
    with db_conn.cursor() as cur:
        cur.execute(
            "INSERT INTO videos (uploader_id, title, status) "
            "VALUES (%s, %s, %s) RETURNING id",
            (user_c_id, "Test video MYTUBE-191", "ready"),
        )
        video_id = str(cur.fetchone()[0])

    yield video_id

    # Teardown: remove the test video so repeated runs start clean.
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))


@pytest.fixture(scope="module")
def delete_response(api_server, seeded_video):
    """User A sends DELETE /api/videos/{video_b_id} with their Bearer token.

    Returns a dict with ``status_code`` and ``body``.
    """
    auth = AuthService(
        base_url=f"http://127.0.0.1:{_PORT}",
        token=_FIREBASE_TOKEN,
    )
    status_code, body = auth.delete(f"/api/videos/{seeded_video}")
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteVideoNonOwner:
    """DELETE /api/videos/:id as a non-owner must return 403 Forbidden."""

    def test_returns_403_forbidden(self, delete_response):
        """API must reject the request with HTTP 403 when the caller does not own the video."""
        assert delete_response["status_code"] == 403, (
            f"Expected HTTP 403 Forbidden, got {delete_response['status_code']}. "
            f"Response body: {delete_response['body']}"
        )

    def test_video_status_unchanged_in_db(self, db_conn, seeded_video, delete_response):
        """The video must still exist in the DB with its original status 'ready'."""
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM videos WHERE id = %s",
                (seeded_video,),
            )
            row = cur.fetchone()

        assert row is not None, (
            f"Video {seeded_video} was not found in the DB after the DELETE attempt. "
            "The video should NOT have been deleted by a non-owner."
        )
        assert row[0] == "ready", (
            f"Expected video status 'ready', got {row[0]!r}. "
            "The video's status must remain unchanged after a rejected DELETE request."
        )
