"""
MYTUBE-392: POST /api/videos by registered user — video record created and 201 response returned.

Objective
---------
Verify that an authenticated user who is already registered in the system can
successfully create a video record without triggering auto-provisioning logic.
The API must return HTTP 201 Created with a ``video_id`` and a signed GCS
``upload_url``.

Preconditions
-------------
A user record must exist in the ``users`` database table for the specific
Firebase UID.  If the row is absent (e.g. fresh test DB), this test inserts
it before running so that the pre-existing-user path is always exercised.

Environment Variables
---------------------
FIREBASE_TEST_TOKEN  — Firebase ID token (required; test skips when absent).
API_BASE_URL         — Base URL of the deployed API (default: http://localhost:8080).
FIREBASE_TEST_UID    — Firebase UID of the pre-existing test user.
                       Defaults to "ci-registered-user".
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
from testing.components.services.user_db_service import UserDbService

# ---------------------------------------------------------------------------
# Constants / environment
# ---------------------------------------------------------------------------

_FIREBASE_TOKEN: str = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_TEST_UID: str = os.getenv("FIREBASE_TEST_UID", "ci-registered-user")
_TEST_USERNAME = "ci_registered_user_mytube392"
_TEST_TITLE = "MYTUBE-392 registered user test"


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
            "FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-392. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run this test."
        )
    return _FIREBASE_TOKEN


@pytest.fixture(scope="module")
def auth_service(api_config: APIConfig, firebase_token: str) -> AuthService:
    return AuthService(base_url=api_config.base_url, token=firebase_token)


@pytest.fixture(scope="module")
def user_db_service(db_config: DBConfig):
    """Open a UserDbService connection; yields None if DB is unreachable."""
    svc = UserDbService(db_config)
    if not svc.connect():
        yield None
        return
    yield svc
    svc.close()


@pytest.fixture(scope="module")
def post_video_response(
    auth_service: AuthService,
    user_db_service,
    firebase_token: str,  # noqa: ARG001  — ensures token guard fires first
) -> dict:
    """Ensure user exists, capture pre-POST user count, POST /api/videos, return results.

    Returns::

        {
            "status_code": <int>,
            "body": <str>,
            "body_json": <dict or None>,
            "user_count_before": <int or None>,
            "user_count_after": <int or None>,
        }
    """
    user_count_before: int | None = None
    user_count_after: int | None = None

    if user_db_service is not None and _FIREBASE_TEST_UID:
        # Ensure the user already exists in the DB (the precondition).
        # Uses INSERT ... ON CONFLICT DO NOTHING so the row is always present
        # without wiping any pre-existing data.
        try:
            with user_db_service._conn.cursor() as cur:  # noqa: SLF001
                cur.execute(
                    "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) "
                    "ON CONFLICT (firebase_uid) DO NOTHING",
                    (_FIREBASE_TEST_UID, _TEST_USERNAME),
                )
                user_db_service._conn.commit()  # noqa: SLF001
        except Exception:
            pass

        # Count users with this firebase_uid BEFORE the API call.
        try:
            with user_db_service._conn.cursor() as cur:  # noqa: SLF001
                cur.execute(
                    "SELECT COUNT(*) FROM users WHERE firebase_uid = %s",
                    (_FIREBASE_TEST_UID,),
                )
                row = cur.fetchone()
                user_count_before = int(row[0]) if row else None
        except Exception:
            pass

    status_code, body = auth_service.post(
        "/api/videos",
        {"title": _TEST_TITLE, "mime_type": "video/mp4"},
    )

    if user_db_service is not None and _FIREBASE_TEST_UID:
        # Count users after the API call to detect spurious duplicate rows.
        try:
            with user_db_service._conn.cursor() as cur:  # noqa: SLF001
                cur.execute(
                    "SELECT COUNT(*) FROM users WHERE firebase_uid = %s",
                    (_FIREBASE_TEST_UID,),
                )
                row = cur.fetchone()
                user_count_after = int(row[0]) if row else None
        except Exception:
            pass

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
        "user_count_before": user_count_before,
        "user_count_after": user_count_after,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegisteredUserVideoCreation:
    """POST /api/videos by an already-registered user → 201 + no duplicate user."""

    def test_post_videos_returns_201(self, post_video_response: dict) -> None:
        """POST /api/videos must return HTTP 201 for a pre-registered Firebase user."""
        status_code = post_video_response["status_code"]

        if status_code == 0:
            pytest.skip(
                "API is not reachable at the configured base URL — "
                "set API_BASE_URL to the deployed API endpoint."
            )

        if status_code == 401:
            pytest.skip(
                "POST /api/videos returned 401 — FIREBASE_TEST_TOKEN may be "
                "expired or invalid. Obtain a fresh token and retry."
            )

        assert status_code == 201, (
            f"Expected HTTP 201 from POST /api/videos for a pre-registered user; "
            f"got {status_code}.\n"
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

    def test_video_saved_in_db(
        self, post_video_response: dict, user_db_service
    ) -> None:
        """A video row must exist in the ``videos`` table for the returned video_id.

        Skipped when the DB is not reachable or video_id is absent from the response.
        """
        body_json = post_video_response["body_json"]
        if not body_json:
            pytest.skip("No JSON body — cannot determine video_id for DB check.")

        video_id = body_json.get("video_id")
        if not video_id:
            pytest.skip("No video_id in response body — skipping DB assertion.")

        if user_db_service is None:
            pytest.skip("Database is not reachable — skipping DB assertion.")

        row = user_db_service.get_video_by_id(video_id)
        assert row is not None, (
            f"No row found in the 'videos' table for id={video_id!r} "
            f"after POST /api/videos returned 201.\n"
            f"The video record was not saved to the database."
        )

    def test_no_duplicate_user_created(
        self, post_video_response: dict, user_db_service
    ) -> None:
        """The user row count for the Firebase UID must not increase after the POST.

        Ensures the API does not create a duplicate user record when the user
        is already registered.  Skipped when the DB is not reachable.
        """
        if not _FIREBASE_TEST_UID:
            pytest.skip("FIREBASE_TEST_UID is not set — skipping duplicate-user assertion.")

        if user_db_service is None:
            pytest.skip("Database is not reachable — skipping duplicate-user assertion.")

        before = post_video_response["user_count_before"]
        after = post_video_response["user_count_after"]

        if before is None or after is None:
            pytest.skip("Could not read user count from the database — skipping assertion.")

        assert after == before, (
            f"User count for firebase_uid={_FIREBASE_TEST_UID!r} changed from "
            f"{before} to {after} after POST /api/videos.\n"
            f"The API must not create duplicate user records for an already-registered user."
        )

    def test_user_still_exists_in_db(
        self, post_video_response: dict, user_db_service
    ) -> None:
        """The pre-existing user row must still be present after the API call.

        Skipped when the DB is not reachable.
        """
        if not _FIREBASE_TEST_UID:
            pytest.skip("FIREBASE_TEST_UID is not set — skipping DB assertion.")

        if user_db_service is None:
            pytest.skip("Database is not reachable — skipping DB assertion.")

        row = user_db_service.get_user_by_firebase_uid(_FIREBASE_TEST_UID)
        assert row is not None, (
            f"No row found in the 'users' table for firebase_uid={_FIREBASE_TEST_UID!r} "
            f"after POST /api/videos returned {post_video_response['status_code']}.\n"
            f"The pre-existing user record must remain intact."
        )
