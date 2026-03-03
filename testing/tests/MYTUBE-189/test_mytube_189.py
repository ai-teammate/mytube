"""
MYTUBE-189: Update video metadata as non-owner — 403 Forbidden returned.

Verifies that a user cannot update metadata for a video they do not own.

Preconditions
-------------
- User A is authenticated (has a valid Firebase ID token).
- Video B is owned by User C (a different user from User A).

Test steps
----------
1. Build and start the Go API server with valid DB and Firebase credentials.
2. Pre-insert User A (matching FIREBASE_TEST_UID) via direct DB access.
3. Pre-insert User C (a separate test user) via direct DB access.
4. Pre-insert Video B owned by User C via direct DB access.
5. User A sends PUT /api/videos/{Video_B_id} with modified metadata fields.
6. Assert HTTP 403 Forbidden is returned.
7. Assert that Video B's title and description in the database are unchanged.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN : Firebase ID token for User A.
                        Test is skipped when absent.
- FIREBASE_PROJECT_ID : Firebase project ID required to initialise the
                        token verifier. Test is skipped when absent.
- FIREBASE_TEST_UID   : The firebase_uid that the test token belongs to
                        (default: "test-uid-user-a-189").
- API_BINARY          : Path to the pre-built Go binary
                        (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                        Database connection settings (all have sensible defaults).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- Direct psycopg2 SQL is used for idempotent test-data setup.
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
- Fixtures are module-scoped for performance.
"""
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService

import psycopg2

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18189
_STARTUP_TIMEOUT = 20.0

# Firebase credentials for User A (the non-owner caller).
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# firebase_uid that matches the test token (User A).
_USER_A_FIREBASE_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-user-a-189")
_USER_A_USERNAME = "testuser_a_189"

# User C (video owner) — no Firebase token needed; only a DB row.
_USER_C_FIREBASE_UID = "test-uid-user-c-189"
_USER_C_USERNAME = "testuser_c_189"

# Original video metadata (must remain unchanged after the rejected PUT).
_ORIGINAL_TITLE = "Original Video Title MYTUBE-189"
_ORIGINAL_DESCRIPTION = "Original description MYTUBE-189"


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
            "FIREBASE_TEST_TOKEN not set — skipping non-owner update test. "
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
        # RAW_UPLOADS_BUCKET is required by the binary at startup even though
        # this test never uploads files. A placeholder satisfies the check
        # without making real GCS calls.
        "RAW_UPLOADS_BUCKET": os.getenv("RAW_UPLOADS_BUCKET", "unused-bucket-mytube-189"),
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
def seeded_users(api_server, db_conn):
    """
    Ensure User A (matching FIREBASE_TEST_UID) and User C (video owner)
    both have rows in the users table.

    Uses ON CONFLICT DO NOTHING so the fixture is safe to run on a database
    that already contains these rows from a previous test run.

    Returns a dict with user_a_id and user_c_id.
    """
    with db_conn.cursor() as cur:
        # Insert User A — must exist so the handler can resolve their internal ID.
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_USER_A_FIREBASE_UID, _USER_A_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_USER_A_FIREBASE_UID,),
        )
        row = cur.fetchone()
        if row is None:
            pytest.fail(
                f"Could not insert or find User A with firebase_uid={_USER_A_FIREBASE_UID!r}"
            )
        user_a_id = str(row[0])

        # Insert User C — the video owner; different user from User A.
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_USER_C_FIREBASE_UID, _USER_C_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_USER_C_FIREBASE_UID,),
        )
        row = cur.fetchone()
        if row is None:
            pytest.fail(
                f"Could not insert or find User C with firebase_uid={_USER_C_FIREBASE_UID!r}"
            )
        user_c_id = str(row[0])

    return {"user_a_id": user_a_id, "user_c_id": user_c_id}


@pytest.fixture(scope="module")
def seeded_video(api_server, db_conn, seeded_users):
    """
    Insert Video B owned by User C into the database.

    Yields a dict with video_id and user_c_id.

    Teardown deletes the video (and its tags) so the database is left clean.
    """
    user_c_id = seeded_users["user_c_id"]

    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, description, status)
            VALUES (%s, %s, %s, %s)
            RETURNING id
            """,
            (user_c_id, _ORIGINAL_TITLE, _ORIGINAL_DESCRIPTION, "ready"),
        )
        video_id = str(cur.fetchone()[0])

    yield {"video_id": video_id, "user_c_id": user_c_id}

    # Cleanup: remove tags first (FK constraint), then the video row.
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM video_tags WHERE video_id = %s", (video_id,))
        cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))


@pytest.fixture(scope="module")
def update_response(api_server, seeded_video):
    """
    User A sends PUT /api/videos/{Video_B_id} with modified metadata fields.

    Returns a dict with status_code and body.
    """
    video_id = seeded_video["video_id"]
    payload = json.dumps(
        {
            "title": "Hacked Title by Non-Owner",
            "description": "This description should not be saved",
            "tags": [],
        }
    ).encode("utf-8")

    status_code, body = api_server.put(
        f"/api/videos/{video_id}",
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


class TestUpdateVideoNonOwner:
    """PUT /api/videos/:id by a non-owner must be rejected with 403 Forbidden."""

    def test_response_status_is_403(self, update_response):
        """Non-owner update attempt must return HTTP 403 Forbidden."""
        assert update_response["status_code"] == 403, (
            f"Expected HTTP 403 Forbidden, got {update_response['status_code']}. "
            f"Response body: {update_response['body']}"
        )

    def test_video_title_unchanged_in_db(self, db_conn, seeded_video):
        """Video title in the database must remain unchanged after the rejected PUT."""
        video_id = seeded_video["video_id"]
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT title FROM videos WHERE id = %s",
                (video_id,),
            )
            row = cur.fetchone()

        assert row is not None, f"Video {video_id} not found in database"
        assert row[0] == _ORIGINAL_TITLE, (
            f"Expected title to be unchanged ({_ORIGINAL_TITLE!r}), got {row[0]!r}"
        )

    def test_video_description_unchanged_in_db(self, db_conn, seeded_video):
        """Video description in the database must remain unchanged after the rejected PUT."""
        video_id = seeded_video["video_id"]
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT description FROM videos WHERE id = %s",
                (video_id,),
            )
            row = cur.fetchone()

        assert row is not None, f"Video {video_id} not found in database"
        assert row[0] == _ORIGINAL_DESCRIPTION, (
            f"Expected description to be unchanged ({_ORIGINAL_DESCRIPTION!r}), got {row[0]!r}"
        )
