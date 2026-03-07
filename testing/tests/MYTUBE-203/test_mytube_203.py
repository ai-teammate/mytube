"""
MYTUBE-203: Delete own comment — comment is hard-deleted from the system.

Objective
---------
Verify that an authenticated owner can permanently delete their own comment
and that the comment is no longer returned in the video's comment list.

Preconditions
-------------
- User A has posted a comment.

Test steps
----------
1. Log in as User A (FIREBASE_TEST_TOKEN in env).
2. Discover a ready video via the deployed API.
3. POST /api/videos/:video_id/comments to create a comment as User A.
4. Send DELETE /api/comments/:comment_id using the ID from step 3.
5. Attempt GET /api/videos/:video_id/comments.

Expected Result
---------------
- The POST returns HTTP 201 with a JSON body containing the comment id.
- The DELETE request returns HTTP 204 No Content.
- The subsequent GET returns HTTP 200.
- The deleted comment is no longer present in the list.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN  : Firebase ID token for the test user (required).
- API_BASE_URL         : Base URL of the API under test.
                         Defaults to https://mytube-api-80693608388.us-central1.run.app
                         (the deployed production-equivalent API).
                         Set to http://localhost:8080 when testing against a local server.

Architecture notes
------------------
- CommentsService encapsulates all /api/comments and /api/videos/:id/comments
  HTTP interaction; no raw urllib calls appear in test code.
- SearchService discovers a ready video via /api/search to use as target.
- No local API server or database is required — tests run against the
  deployed API using a valid Firebase ID token.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.search_service import SearchService
from testing.components.services.comments_service import CommentsService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The deployed API URL used as the fallback when API_BASE_URL is not set.
# This is the production-equivalent API described in the CI credentials.
_DEPLOYED_API_URL = "https://mytube-api-80693608388.us-central1.run.app"

# Firebase test credentials — loaded at import time so the autouse fixture
# can skip the module before any fixture setup runs.
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")

_COMMENT_BODY = "This comment will be deleted — MYTUBE-203 test."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_base_url() -> str:
    """Return the API base URL, preferring API_BASE_URL env var.

    Falls back to the known deployed API URL so that integration tests run
    out-of-the-box in the CI environment described in the instructions.
    """
    return os.getenv("API_BASE_URL", _DEPLOYED_API_URL).rstrip("/")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_token():
    """Skip the entire module when the Firebase ID token is not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping DELETE /api/comments/:id "
            "integration test. Set FIREBASE_TEST_TOKEN to a valid Firebase ID "
            "token to run this test."
        )


@pytest.fixture(scope="module")
def base_url() -> str:
    """Return the API base URL to test against."""
    return _resolve_base_url()


@pytest.fixture(scope="module")
def comment_service(base_url: str) -> CommentsService:
    """Return a CommentsService configured with the Firebase test token."""
    return CommentsService(base_url=base_url, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def video_id(base_url: str) -> str:
    """Discover a ready video to use as the comment target.

    Uses SearchService.search() to find any available video in the API.
    Skips the module if no video is found.
    """
    svc = SearchService(base_url=base_url)
    resp = svc.search(q="", limit=1)
    if resp.status_code != 200 or not resp.items:
        pytest.skip(
            f"No video found via GET /api/search (status={resp.status_code}). "
            "Ensure at least one video exists in the deployed API to run this test."
        )
    return resp.items[0].id


@pytest.fixture(scope="module")
def created_comment(video_id: str, comment_service: CommentsService):
    """POST a comment to the test video; return status_code, body, video_id."""
    resp = comment_service.post_comment(video_id, _COMMENT_BODY)
    return {"status_code": resp.status_code, "body": resp.raw_body, "video_id": video_id}


@pytest.fixture(scope="module")
def delete_response(created_comment, comment_service: CommentsService):
    """
    Extract the comment id from the POST response and issue DELETE.

    Returns a dict with ``status_code``, ``body``, and ``comment_id``.
    Skips if the POST did not return 201 (avoiding a misleading DELETE failure).
    """
    post_status = created_comment["status_code"]
    if post_status != 201:
        pytest.skip(
            f"Skipping DELETE test because POST /api/videos/:id/comments "
            f"returned {post_status} instead of 201. "
            f"Body: {created_comment['body']}"
        )

    parsed = json.loads(created_comment["body"])
    comment_id = parsed.get("id", "")
    if not comment_id:
        pytest.skip(
            "POST response body did not contain a comment 'id'; cannot test DELETE."
        )

    resp = comment_service.delete_comment(comment_id)
    return {"status_code": resp.status_code, "body": resp.raw_body, "comment_id": comment_id}


@pytest.fixture(scope="module")
def comments_after_delete(delete_response, video_id: str, comment_service: CommentsService):
    """
    GET the comment list after deletion; return (status_code, parsed_list).

    Skips if the DELETE did not return 204.
    """
    if delete_response["status_code"] != 204:
        pytest.skip(
            f"Skipping GET-after-delete test because DELETE returned "
            f"{delete_response['status_code']} instead of 204."
        )

    resp = comment_service.list_comments(video_id)
    try:
        comments = json.loads(resp.raw_body)
        if not isinstance(comments, list):
            comments = []
    except json.JSONDecodeError:
        comments = []
    return {"status_code": resp.status_code, "comments": comments}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteOwnComment:
    """MYTUBE-203: Authenticated owner deletes their own comment; it is hard-deleted."""

    def test_post_comment_returns_201(self, created_comment):
        """POST /api/videos/:id/comments must return HTTP 201 Created."""
        assert created_comment["status_code"] == 201, (
            f"Expected HTTP 201 when posting a comment, "
            f"got {created_comment['status_code']}. "
            f"Body: {created_comment['body']}"
        )

    def test_post_comment_response_contains_id(self, created_comment):
        """The POST response body must contain a non-empty 'id' field."""
        assert created_comment["status_code"] == 201, (
            "POST did not return 201; cannot verify id field."
        )
        parsed = json.loads(created_comment["body"])
        assert "id" in parsed, (
            f"Expected 'id' field in POST response, got keys: {list(parsed.keys())}"
        )
        assert parsed["id"], "Comment 'id' must not be empty."

    def test_delete_comment_returns_204(self, delete_response):
        """DELETE /api/comments/:id must return HTTP 204 No Content."""
        assert delete_response["status_code"] == 204, (
            f"Expected HTTP 204 for DELETE /api/comments/:id, "
            f"got {delete_response['status_code']}. "
            f"Body: {delete_response['body']!r}"
        )

    def test_comment_list_status_is_200(self, comments_after_delete):
        """GET /api/videos/:id/comments must return HTTP 200 after the deletion."""
        assert comments_after_delete["status_code"] == 200, (
            f"Expected HTTP 200 for GET /api/videos/:id/comments, "
            f"got {comments_after_delete['status_code']}."
        )

    def test_deleted_comment_absent_from_list(self, delete_response, comments_after_delete):
        """The deleted comment must not appear in the subsequent comment list."""
        deleted_id = delete_response["comment_id"]
        remaining_ids = {c.get("id") for c in comments_after_delete["comments"]}
        assert deleted_id not in remaining_ids, (
            f"Deleted comment id={deleted_id!r} still appears in the comment "
            f"list after DELETE. The comment was NOT hard-deleted."
        )
