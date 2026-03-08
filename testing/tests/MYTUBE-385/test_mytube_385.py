"""
MYTUBE-385: POST /api/videos call by new Firebase-authenticated user —
user auto-provisioned and 201 Created returned.

Objective
---------
Verify that the API automatically provisions a user in the local database when a
first-time Firebase-authenticated user attempts to create a video, preventing a
404 error.  The API must return HTTP 201 Created with a ``video_id`` and a
signed GCS ``upload_url``.

Preconditions
-------------
A valid Firebase ID token in ``FIREBASE_TEST_TOKEN``.  To simulate a
"first-time" user the test attempts to delete any existing row for
``FIREBASE_TEST_UID`` from the ``users`` (and related ``videos``) table before
running, so that auto-provisioning is exercised on every CI run.  If the DB is
not reachable the deletion step is silently skipped and the test still asserts
the HTTP-level contract (201 + expected response fields).

Environment Variables
---------------------
FIREBASE_TEST_TOKEN  — Firebase ID token (required; test skips when absent).
API_BASE_URL         — Base URL of the deployed API (default: http://localhost:8080).
FIREBASE_TEST_UID    — Firebase UID of the test user (used for DB cleanup/check).
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE
                     — Database connection settings for the DB assertion step.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants / environment
# ---------------------------------------------------------------------------

_FIREBASE_TOKEN: str = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_TEST_UID: str = os.getenv("FIREBASE_TEST_UID", "")

_TEST_TITLE = "MYTUBE-385 auto-provision test"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _try_connect_db(db_config: DBConfig):
    """Return a live psycopg2 connection or None if DB is unreachable."""
    try:
        import psycopg2  # noqa: PLC0415
        return psycopg2.connect(db_config.dsn())
    except Exception:
        return None


def _delete_test_user(db_config: DBConfig, firebase_uid: str) -> None:
    """Delete the test user row (and their videos) to simulate first-time user.

    Silently skips if psycopg2 is not installed, DB is unreachable, or
    firebase_uid is empty.
    """
    if not firebase_uid:
        return

    conn = _try_connect_db(db_config)
    if conn is None:
        return

    try:
        with conn:
            with conn.cursor() as cur:
                # Delete videos owned by this user first to avoid FK constraint.
                cur.execute(
                    "DELETE FROM videos WHERE user_id = (SELECT id FROM users WHERE firebase_uid = %s)",
                    (firebase_uid,),
                )
                # Delete the user row.
                cur.execute(
                    "DELETE FROM users WHERE firebase_uid = %s",
                    (firebase_uid,),
                )
    except Exception:
        # If FK cascade or schema differs, fall through — the HTTP assertion
        # is the primary check and is still performed.
        pass
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def firebase_token() -> str:
    """Firebase ID token; skips the entire module when absent."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-385. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run this test."
        )
    return _FIREBASE_TOKEN


@pytest.fixture(scope="module")
def auth_service(api_config: APIConfig, firebase_token: str) -> AuthService:
    return AuthService(base_url=api_config.base_url, token=firebase_token)


@pytest.fixture(scope="module")
def post_video_response(
    auth_service: AuthService,
    db_config: DBConfig,
    firebase_token: str,  # noqa: ARG001  — ensures token guard fires first
) -> dict:
    """Perform the DELETE → POST flow; return a dict with the results.

    Returns::

        {
            "status_code": <int>,
            "body": <str>,
            "body_json": <dict or None>,
        }
    """
    # Delete the test user from the DB so auto-provisioning is always exercised.
    _delete_test_user(db_config, _FIREBASE_TEST_UID)

    status_code, body = auth_service.post(
        "/api/videos",
        {"title": _TEST_TITLE, "mime_type": "video/mp4"},
    )

    body_json: dict | None = None
    if body:
        try:
            body_json = json.loads(body)
        except json.JSONDecodeError:
            pass

    return {
        "status_code": status_code,
        "body": body,
        "body_json": body_json,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNewUserAutoProvisioning:
    """POST /api/videos by a new Firebase user → 201 + auto-provisioned user."""

    def test_post_videos_returns_201(self, post_video_response: dict) -> None:
        """POST /api/videos must return HTTP 201 for a valid Firebase token.

        A 404 here means the API failed to auto-provision the user — the exact
        regression this ticket guards against.
        """
        status_code = post_video_response["status_code"]

        if status_code == 0:
            pytest.skip(
                f"API is not reachable at the configured base URL — "
                "set API_BASE_URL to the deployed API endpoint."
            )

        if status_code == 401:
            pytest.skip(
                "POST /api/videos returned 401 — FIREBASE_TEST_TOKEN may be "
                "expired or invalid. Obtain a fresh token and retry."
            )

        assert status_code == 201, (
            f"Expected HTTP 201 from POST /api/videos; got {status_code}.\n"
            f"A 404 indicates the API did not auto-provision the new user.\n"
            f"Response body: {post_video_response['body']}"
        )

    def test_response_contains_video_id(self, post_video_response: dict) -> None:
        """Response body must include a non-empty ``video_id`` field."""
        body_json = post_video_response["body_json"]
        assert body_json is not None, (
            f"POST /api/videos returned a non-JSON body: {post_video_response['body']!r}"
        )
        assert body_json.get("video_id"), (
            f"POST /api/videos response did not include 'video_id'.\n"
            f"Body: {post_video_response['body']}"
        )

    def test_response_contains_upload_url(self, post_video_response: dict) -> None:
        """Response body must include a non-empty ``upload_url`` (signed GCS URL)."""
        body_json = post_video_response["body_json"]
        assert body_json is not None, (
            f"POST /api/videos returned a non-JSON body: {post_video_response['body']!r}"
        )
        assert body_json.get("upload_url"), (
            f"POST /api/videos response did not include 'upload_url'.\n"
            f"Body: {post_video_response['body']}"
        )

    def test_user_provisioned_in_db(
        self, post_video_response: dict, db_config: DBConfig
    ) -> None:
        """A row for the Firebase UID must exist in the ``users`` table after the call.

        Skipped when psycopg2 is not installed or the DB is not reachable.
        """
        if not _FIREBASE_TEST_UID:
            pytest.skip("FIREBASE_TEST_UID is not set — skipping DB assertion.")

        try:
            import psycopg2  # noqa: PLC0415
        except ImportError:
            pytest.skip("psycopg2 is not installed — skipping DB assertion.")

        conn = _try_connect_db(db_config)
        if conn is None:
            pytest.skip(
                f"Database is not reachable at {db_config.host}:{db_config.port} — "
                "skipping DB assertion."
            )

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, firebase_uid FROM users WHERE firebase_uid = %s",
                    (_FIREBASE_TEST_UID,),
                )
                row = cur.fetchone()
        finally:
            conn.close()

        assert row is not None, (
            f"No row found in the 'users' table for firebase_uid={_FIREBASE_TEST_UID!r} "
            f"after POST /api/videos returned {post_video_response['status_code']}.\n"
            f"The API must auto-provision the user on first request."
        )

    def test_video_saved_for_provisioned_user(
        self, post_video_response: dict, db_config: DBConfig
    ) -> None:
        """A video row must exist in the ``videos`` table for the newly created video.

        Skipped when the DB is not reachable or video_id is absent from the response.
        """
        body_json = post_video_response["body_json"]
        if not body_json:
            pytest.skip("No JSON body — cannot determine video_id for DB check.")

        video_id = body_json.get("video_id")
        if not video_id:
            pytest.skip("No video_id in response body — skipping DB assertion.")

        try:
            import psycopg2  # noqa: PLC0415
        except ImportError:
            pytest.skip("psycopg2 is not installed — skipping DB assertion.")

        conn = _try_connect_db(db_config)
        if conn is None:
            pytest.skip(
                f"Database is not reachable at {db_config.host}:{db_config.port} — "
                "skipping DB assertion."
            )

        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, title FROM videos WHERE id = %s",
                    (video_id,),
                )
                row = cur.fetchone()
        finally:
            conn.close()

        assert row is not None, (
            f"No row found in the 'videos' table for id={video_id!r} "
            f"after POST /api/videos returned 201.\n"
            f"The video record was not saved to the database."
        )
