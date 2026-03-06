"""
MYTUBE-252: Delete comment without authentication — system returns 401 unauthorized.

Objective
---------
Verify that the system prevents unauthenticated users from deleting any comments.

Steps
-----
1. Send a DELETE request to /api/comments/{comment_id} without providing an
   authentication token or session.

Expected Result
---------------
The request is rejected with a 401 Unauthorized error. The comment remains
in the database unchanged.

Architecture notes
------------------
- CommentsService encapsulates all HTTP interaction with /api/comments.
- No raw urllib calls appear in test code.
- Uses deployed API URL (no local server setup required).
- Test is simple: send DELETE without auth token to any comment ID.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.comments_service import CommentsService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The deployed API URL used as the fallback when API_BASE_URL is not set.
_DEPLOYED_API_URL = "https://mytube-api-80693608388.us-central1.run.app"

# A known comment UUID (used for testing unauthorized access).
# This is a valid UUID format but may not exist; that's OK since we're
# testing auth, not the comment's existence.
_TEST_COMMENT_ID = "69f8bc2f-dc91-45c5-a4e1-77365f19fcb0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_base_url() -> str:
    """Return the API base URL, preferring API_BASE_URL env var.

    Falls back to the known deployed API URL.
    """
    return os.getenv("API_BASE_URL", _DEPLOYED_API_URL).rstrip("/")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteCommentWithoutAuthentication:
    """MYTUBE-252: DELETE /api/comments without auth token returns 401."""

    def test_delete_without_token_returns_401(self):
        """
        Sending DELETE /api/comments/{comment_id} without an authentication
        token must return HTTP 401 Unauthorized.

        The system enforces that all comment deletions require a valid Bearer
        token (proving the user's identity and ownership of the comment).
        """
        base_url = _resolve_base_url()

        # CommentsService with no token (pass empty string or None)
        # The service will send DELETE without Authorization header.
        comment_service = CommentsService(base_url=base_url, token="")

        # Send DELETE request without authentication
        resp = comment_service.delete_comment(_TEST_COMMENT_ID)

        # Assert HTTP 401 Unauthorized
        assert resp.status_code == 401, (
            f"Expected HTTP 401 Unauthorized when deleting a comment without "
            f"authentication, but got {resp.status_code}. "
            f"Response body: {resp.raw_body!r}"
        )
