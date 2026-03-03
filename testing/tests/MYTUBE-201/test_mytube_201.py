"""
MYTUBE-201: Post comment exceeding character limit — request rejected due to 2000 char cap.

Objective
---------
Verify that the POST /api/videos/:id/comments endpoint enforces a 2000-character
limit on the comment body, rejecting oversized payloads with a 400 Bad Request.

Steps
-----
1. Obtain a Firebase ID token and a valid video ID.
2. Construct a comment body of exactly 2001 characters.
3. POST to /api/videos/{video_id}/comments with the oversized body.
4. Assert the response is HTTP 400 Bad Request.
5. Assert the response body contains an error message indicating the comment
   is too long.

Expected Result
---------------
HTTP 400 with a JSON error message indicating the comment body exceeds the limit.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN    : Firebase ID token for the CI test user.
                           Test is skipped when absent.
- API_BASE_URL           : Base URL of the deployed API.
                           Defaults to https://mytube-api-80693608388.us-central1.run.app
                           via APIConfig.
- MYTUBE_201_VIDEO_ID    : (optional) UUID of a known video to use as the target.
                           When absent, the test discovers a video from the
                           authenticated user's profile.

Architecture
------------
- CommentsService wraps POST /api/videos/:id/comments with Bearer token auth.
- AuthService is used to resolve the current user's profile and video list.
- APIConfig loads API_BASE_URL from the environment.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from typing import Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.components.services.auth_service import AuthService
from testing.components.services.comments_service import CommentsService, CommentResponse

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_COMMENT_CHAR_LIMIT = 2000
_OVERSIZED_COMMENT = "a" * (_COMMENT_CHAR_LIMIT + 1)  # 2001 characters

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_VIDEO_ID_OVERRIDE = os.getenv("MYTUBE_201_VIDEO_ID", "")

# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_token():
    """Skip the entire module when FIREBASE_TEST_TOKEN is not set."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-201 comment limit test. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run this test."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    """Issue an unauthenticated GET and return parsed JSON, or None on error."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _find_any_video_id(base_url: str, token: str) -> Optional[str]:
    """Discover any video ID owned by the authenticated user.

    Strategy:
    1. GET /api/me to retrieve the current user's username.
    2. GET /api/users/{username} to retrieve their video list.
    3. Return the first video ID found (any status is acceptable — we are
       testing comment input validation, not video playback readiness).
    """
    auth = AuthService(base_url=base_url, token=token)
    status, body = auth.get("/api/me")
    if status != 200:
        return None
    try:
        me = json.loads(body)
    except Exception:
        return None

    username = me.get("username")
    if not username:
        return None

    profile = _fetch_json(f"{base_url}/api/users/{username}")
    if not profile:
        return None

    videos = profile.get("videos", [])
    for v in videos:
        vid_id = v.get("id") or v.get("video_id")
        if vid_id:
            return vid_id
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    """Return an APIConfig loaded from environment variables."""
    return APIConfig()


@pytest.fixture(scope="module")
def video_id(api_config: APIConfig) -> str:
    """Return the video ID to use for the comment endpoint.

    Priority:
    1. MYTUBE_201_VIDEO_ID env var (explicit override).
    2. Any video owned by the authenticated CI test user (via /api/me).
    3. Skip the test if no video is available.
    """
    if _VIDEO_ID_OVERRIDE:
        return _VIDEO_ID_OVERRIDE

    vid_id = _find_any_video_id(api_config.base_url, _FIREBASE_TOKEN)
    if not vid_id:
        pytest.skip(
            "No video found for the authenticated user. "
            "Set MYTUBE_201_VIDEO_ID to a valid video UUID to run this test."
        )
    return vid_id


@pytest.fixture(scope="module")
def oversized_comment_response(api_config: APIConfig, video_id: str) -> CommentResponse:
    """POST a 2001-character comment to /api/videos/{video_id}/comments."""
    svc = CommentsService(base_url=api_config.base_url, token=_FIREBASE_TOKEN)
    return svc.post_comment(video_id=video_id, body=_OVERSIZED_COMMENT)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCommentCharacterLimitEnforced:
    """POST /api/videos/:id/comments must reject a comment body exceeding 2000 chars."""

    def test_oversized_comment_body_is_2001_chars(self):
        """Precondition: the test comment is exactly 2001 characters."""
        assert len(_OVERSIZED_COMMENT) == 2001, (
            f"Expected test body of 2001 chars, got {len(_OVERSIZED_COMMENT)}."
        )

    def test_response_status_is_400(self, oversized_comment_response: CommentResponse):
        """The API must return HTTP 400 Bad Request for a 2001-char comment."""
        assert oversized_comment_response.status_code == 400, (
            f"Expected HTTP 400 for an oversized comment, "
            f"got {oversized_comment_response.status_code}. "
            f"Response body: {oversized_comment_response.raw_body!r}"
        )

    def test_response_body_contains_error_message(self, oversized_comment_response: CommentResponse):
        """The response body must be non-empty and indicate the failure reason."""
        assert oversized_comment_response.raw_body.strip(), (
            "Expected a non-empty error response body, but got an empty string."
        )

    def test_response_body_is_json(self, oversized_comment_response: CommentResponse):
        """The response body must be valid JSON."""
        parsed = oversized_comment_response.json
        assert parsed is not None, (
            f"Expected a JSON response body, but could not parse: "
            f"{oversized_comment_response.raw_body!r}"
        )

    def test_error_message_mentions_comment_length(self, oversized_comment_response: CommentResponse):
        """The error message must reference the character limit or 'too long'."""
        error = oversized_comment_response.error_message
        if error is None:
            # Fall back: search the raw body for relevant keywords
            raw = oversized_comment_response.raw_body.lower()
        else:
            raw = error.lower()

        length_keywords = ["long", "limit", "exceed", "character", "2000", "max", "length"]
        matched = any(kw in raw for kw in length_keywords)
        assert matched, (
            f"Expected the error message to mention the character limit "
            f"(one of {length_keywords}), but got: {oversized_comment_response.raw_body!r}"
        )
