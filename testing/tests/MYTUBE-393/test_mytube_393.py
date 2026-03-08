"""
MYTUBE-393: POST /api/videos by unregistered user — request rejected with 403/422
and no auto-provisioning occurs.

Objective
---------
Ensure that the API correctly rejects unregistered users and does NOT automatically
create a user row in the database (reverting the regression introduced in MYTUBE-383).

Preconditions
-------------
The Firebase UID (ci-test-user-001) has no corresponding row in the users database
table. If a row exists it is deleted before the test. Restored in teardown.

Test steps
----------
1. Obtain a valid Firebase Bearer token for the unregistered UID (from env).
2. Send POST /api/videos with payload {"title": "Test Video", "mime_type": "video/mp4"}.
3. Verify HTTP response status is 403 or 422 — NOT 201 and NOT 404.
4. Verify response body contains {"error": "user account not registered"}.
5. Query users table — no new row for the UID.
6. Query videos table — no new record linked to the unregistered user.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN : Firebase ID token for ci-test-user-001 (required).
- FIREBASE_TEST_UID   : Firebase UID embedded in the token (default: ci-test-user-001).
- API_BASE_URL        : Base URL of the deployed API (default: http://localhost:8080).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE : DB config.

Architecture notes
------------------
- AuthService wraps authenticated HTTP calls.
- UserDbService handles DB operations (delete/query by firebase_uid).
- The deployed API is used directly (no local server startup required).
"""
from __future__ import annotations

import json
import os
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

_POST_PAYLOAD = {"title": "Test Video", "mime_type": "video/mp4"}

# Allowed rejection status codes per the ticket spec.
_ALLOWED_STATUS_CODES = {403, 422}
_FORBIDDEN_STATUS_CODES = {201, 404}

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_token():
    """Skip the module when the Firebase test token is not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-393 integration test. "
            "Provide a valid Firebase ID token to run this test."
        )


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def db_conn(db_config: DBConfig):
    """Open a direct psycopg2 connection for setup and assertions."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def precondition_no_user(db_conn):
    """Ensure ci-test-user-001 does NOT exist in users before the test runs.

    Saves the current state (user_id if present) and deletes the row (plus any
    owned videos) so the test starts from a clean slate.  After the test suite
    the fixture cleans up any rows that may have been inadvertently created by
    a regression (i.e. auto-provisioning bug).

    Teardown does NOT re-insert the original row because other tests that rely
    on a pre-existing user row seed their own data idempotently.
    """
    with db_conn.cursor() as cur:
        # Capture existing state.
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()
        pre_existing_user_id = str(row[0]) if row else None

    if pre_existing_user_id:
        # Delete FK-dependent rows first.
        with db_conn.cursor() as cur:
            cur.execute(
                "DELETE FROM videos WHERE uploader_id = %s",
                (pre_existing_user_id,),
            )
            cur.execute(
                "DELETE FROM users WHERE id = %s",
                (pre_existing_user_id,),
            )

    yield pre_existing_user_id  # provides pre-existing user ID if needed by tests

    # Teardown: remove any user/video rows that a regression may have created.
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()
        if row:
            leftover_user_id = str(row[0])
            cur.execute(
                "DELETE FROM videos WHERE uploader_id = %s",
                (leftover_user_id,),
            )
            cur.execute(
                "DELETE FROM users WHERE id = %s",
                (leftover_user_id,),
            )


@pytest.fixture(scope="module")
def auth_service(api_config: APIConfig) -> AuthService:
    return AuthService(base_url=api_config.base_url, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def post_response(auth_service: AuthService, precondition_no_user) -> dict:
    """Issue POST /api/videos once and cache (status_code, body) for all tests."""
    status_code, body = auth_service.post("/api/videos", _POST_PAYLOAD)
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPostVideoUnregisteredUser:
    """MYTUBE-393: POST /api/videos by unregistered user must be rejected."""

    def test_response_status_is_rejection_code(self, post_response: dict) -> None:
        """Step 3a: HTTP status must be 403 or 422 — a rejection code."""
        sc = post_response["status_code"]
        assert sc in _ALLOWED_STATUS_CODES, (
            f"Expected HTTP 403 or 422 (rejection), but got HTTP {sc}. "
            f"Response body: {post_response['body']!r}. "
            "The API may be auto-provisioning users (regression from MYTUBE-383) "
            "or returning an unexpected status code."
        )

    def test_response_status_is_not_201_created(self, post_response: dict) -> None:
        """Step 3b: HTTP 201 Created must NOT be returned for an unregistered user."""
        sc = post_response["status_code"]
        assert sc != 201, (
            "API returned HTTP 201 Created for an unregistered user. "
            "This indicates the auto-provisioning regression (MYTUBE-383) is still present. "
            f"Response body: {post_response['body']!r}"
        )

    def test_response_status_is_not_404(self, post_response: dict) -> None:
        """Step 3c: HTTP 404 must NOT be returned — it would indicate a routing issue."""
        sc = post_response["status_code"]
        assert sc != 404, (
            f"API returned HTTP 404 for POST /api/videos. "
            "This suggests the endpoint is missing or the route was removed. "
            f"Response body: {post_response['body']!r}"
        )

    def test_response_body_contains_user_not_registered_error(
        self, post_response: dict
    ) -> None:
        """Step 3d: Response body must contain {"error": "user account not registered"}."""
        try:
            body_dict = json.loads(post_response["body"])
        except (json.JSONDecodeError, TypeError):
            pytest.fail(
                f"Response body is not valid JSON. "
                f"HTTP {post_response['status_code']}. "
                f"Raw body: {post_response['body']!r}"
            )

        error_value = body_dict.get("error", "")
        assert error_value == "user account not registered", (
            f"Expected error message 'user account not registered', "
            f"but got: {error_value!r}. "
            f"Full response body: {post_response['body']!r}"
        )

    def test_no_user_row_created_in_db(self, db_conn, post_response: dict) -> None:
        """Step 4: No new row must appear in the users table for the unregistered UID."""
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE firebase_uid = %s",
                (_FIREBASE_TEST_UID,),
            )
            row = cur.fetchone()
        assert row is None, (
            f"A user row was created in the users table for firebase_uid "
            f"{_FIREBASE_TEST_UID!r} despite the API rejecting the request with "
            f"HTTP {post_response['status_code']}. "
            "This indicates auto-provisioning is still occurring (MYTUBE-383 regression). "
            f"User ID created: {row[0] if row else 'N/A'}"
        )

    def test_no_video_row_created_in_db(self, db_conn, post_response: dict) -> None:
        """Step 5: No new row must appear in the videos table linked to the unregistered user.

        Since no user row should exist, we verify via a subquery using firebase_uid.
        """
        with db_conn.cursor() as cur:
            cur.execute(
                """
                SELECT v.id, v.title
                FROM videos v
                JOIN users u ON v.uploader_id = u.id
                WHERE u.firebase_uid = %s
                """,
                (_FIREBASE_TEST_UID,),
            )
            row = cur.fetchone()
        assert row is None, (
            f"A video row was created in the videos table linked to unregistered user "
            f"{_FIREBASE_TEST_UID!r} despite the API rejecting the request with "
            f"HTTP {post_response['status_code']}. "
            f"Video row: id={row[0]}, title={row[1]!r}" if row else ""
        )
