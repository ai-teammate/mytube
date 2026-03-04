"""
MYTUBE-204: Delete another user's comment — system returns 403 forbidden.

Objective
---------
Verify that users cannot delete comments they do not own.

Preconditions
-------------
- User A has posted a comment.
- User B is authenticated.

Steps
-----
1. Log in as User B.
2. Send a DELETE request to /api/comments/[id_of_user_a_comment].

Expected Result
---------------
The request is rejected with a 403 Forbidden error.
The comment remains in the database.

Test approach
-------------
- The deployed API (API_BASE_URL) processes the DELETE request with User B's
  Bearer token.
- User A (the comment owner) is a synthetic DB-only row — no real Firebase
  account is required.
- User B is the CI test user (FIREBASE_TEST_UID / FIREBASE_TEST_TOKEN). Their
  row must exist in the database before the test runs.
- A video and a comment owned by User A are inserted via a direct Cloud SQL
  connection (cloud-sql-python-connector + pg8000).
- DELETE /api/comments/{comment_id} is issued with User B's Bearer token.
- The response status code is expected to be 403 Forbidden.
- The comment is verified to still exist in the database after the attempt.

Environment variables
---------------------
FIREBASE_TEST_TOKEN        : Valid Firebase ID token for the CI test user (User B).
                             Test is skipped when absent.
FIREBASE_TEST_UID          : firebase_uid of the CI test user / User B
                             (default: ci-test-user-001).
CLOUD_SQL_CONNECTION_NAME  : Cloud SQL instance connection name
                             (default: ai-native-478811:us-central1:learn-ai-db).
API_BASE_URL               : Deployed API base URL.
                             Default: https://mytube-api-80693608388.us-central1.run.app
DB_USER                    : Database user (default: mytube).
DB_PASSWORD                : Database password.
DB_NAME                    : Database name (default: mytube).

Architecture
------------
- CommentApiService encapsulates DELETE /api/comments HTTP interaction.
- Cloud SQL Python connector provides the direct database connection.
- No hardcoded credentials — only well-known CI defaults are referenced.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.comment_api_service import CommentApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEPLOYED_API_URL = "https://mytube-api-80693608388.us-central1.run.app"
_API_BASE_URL = os.getenv("API_BASE_URL", _DEPLOYED_API_URL)

# Firebase credentials — required; test skips when absent.
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")

# User B: the CI test user whose Firebase token we hold.
_USER_B_FIREBASE_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")
_USER_B_USERNAME = "testuser_204_userb"

# User A: the comment owner (synthetic — no real Firebase account needed).
_USER_A_FIREBASE_UID = "test-uid-mytube-204-usera"
_USER_A_USERNAME = "testuser_204_usera"

_VIDEO_TITLE = "MYTUBE-204 Test Video"
_COMMENT_BODY = "User A comment for MYTUBE-204 authorization test"

# Cloud SQL — used for direct database access.
_CLOUD_SQL_INSTANCE = os.getenv(
    "CLOUD_SQL_CONNECTION_NAME", "ai-native-478811:us-central1:learn-ai-db"
)
_DB_USER = os.getenv("DB_USER", "mytube")
_DB_PASS = os.getenv("DB_PASSWORD", "")
_DB_NAME = os.getenv("DB_NAME", "mytube")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
            "FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-204 authorization "
            "test. Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run."
        )


@pytest.fixture(scope="module", autouse=True)
def require_api(require_firebase_token):
    """Skip when the deployed API is not reachable."""
    if not _api_is_reachable(_API_BASE_URL):
        pytest.skip(
            f"API at {_API_BASE_URL} is not reachable — "
            "skipping MYTUBE-204 integration test."
        )


@pytest.fixture(scope="module")
def db_conn(require_api):
    """Open a direct Cloud SQL connection for test-data seeding.

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
def seeded_data(db_conn):
    """Seed User A, a video, and a comment owned by User A.

    User B (CI test user) must already exist in the database — they are the
    real Firebase user whose token we hold.

    Returns a dict with:
      user_a_id   : DB id of User A
      user_b_id   : DB id of User B
      video_id    : DB id of the test video
      comment_id  : DB id of User A's comment
    """
    cur = db_conn.cursor()

    # --- User B: look up the existing CI test user row ---
    cur.execute(
        "SELECT id FROM users WHERE firebase_uid = %s",
        (_USER_B_FIREBASE_UID,),
    )
    row_b = cur.fetchone()
    if row_b is None:
        # Insert User B if they don't exist yet (idempotent).
        cur.execute(
            "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) RETURNING id",
            (_USER_B_FIREBASE_UID, _USER_B_USERNAME),
        )
        row_b = cur.fetchone()
    user_b_id = str(row_b[0])

    # --- User A: synthetic test user (no real Firebase account needed) ---
    cur.execute(
        "SELECT id FROM users WHERE firebase_uid = %s",
        (_USER_A_FIREBASE_UID,),
    )
    row_a = cur.fetchone()
    if row_a is None:
        cur.execute(
            "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) RETURNING id",
            (_USER_A_FIREBASE_UID, _USER_A_USERNAME),
        )
        row_a = cur.fetchone()
    user_a_id = str(row_a[0])

    # --- Video owned by User A ---
    cur.execute(
        "INSERT INTO videos (uploader_id, title, status) "
        "VALUES (%s, %s, 'ready') RETURNING id",
        (user_a_id, _VIDEO_TITLE),
    )
    video_id = str(cur.fetchone()[0])

    # --- Comment owned by User A on User A's video ---
    cur.execute(
        "INSERT INTO comments (video_id, author_id, body) "
        "VALUES (%s, %s, %s) RETURNING id",
        (video_id, user_a_id, _COMMENT_BODY),
    )
    comment_id = str(cur.fetchone()[0])

    yield {
        "user_a_id": user_a_id,
        "user_b_id": user_b_id,
        "video_id": video_id,
        "comment_id": comment_id,
    }

    # Teardown: delete the test comment and video in FK-safe order.
    cur.execute("DELETE FROM comments WHERE id = %s", (comment_id,))
    cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))


@pytest.fixture(scope="module")
def comment_service() -> CommentApiService:
    """Return a CommentApiService pointing at the deployed API with User B's token."""
    return CommentApiService(base_url=_API_BASE_URL, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def delete_response(seeded_data, comment_service: CommentApiService) -> dict:
    """Send DELETE /api/comments/{user_a_comment_id} as User B; return the result."""
    status_code, body = comment_service.delete_comment(seeded_data["comment_id"])
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteOtherUsersComment:
    """MYTUBE-204: User B must not be able to delete User A's comment."""

    def test_response_status_is_403_forbidden(
        self, delete_response: dict
    ) -> None:
        """DELETE /api/comments/{user_a_comment_id} by User B must return 403 Forbidden.

        The server must reject the request because User B is not the comment
        owner. Returning 403 signals an explicit authorization denial, clearly
        distinguishing 'you are authenticated but not authorised' from
        'resource not found' (404).
        """
        assert delete_response["status_code"] == 403, (
            f"Expected HTTP 403 Forbidden when User B attempts to delete "
            f"User A's comment, but got HTTP {delete_response['status_code']}. "
            f"Response body: {delete_response['body']}"
        )

    def test_comment_still_exists_in_database(
        self, delete_response: dict, seeded_data: dict, db_conn
    ) -> None:
        """User A's comment must still be present in the database after the
        failed delete attempt — it must not have been deleted.
        """
        comment_id = seeded_data["comment_id"]
        cur = db_conn.cursor()
        cur.execute(
            "SELECT id FROM comments WHERE id = %s",
            (comment_id,),
        )
        row = cur.fetchone()

        assert row is not None, (
            f"Expected comment {comment_id!r} to still exist in the database "
            "after a rejected delete attempt, but the row was not found. "
            "The comment was incorrectly deleted despite the authorization check."
        )
