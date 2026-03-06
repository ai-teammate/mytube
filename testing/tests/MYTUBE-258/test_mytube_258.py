"""
MYTUBE-258: Update metadata for non-existent video ID — 404 Not Found returned.

Verifies that the API correctly handles metadata update requests for video IDs
that do not exist in the system.

Preconditions
-------------
- User is authenticated (FIREBASE_TEST_TOKEN is set).

Test steps
----------
1. Send a PUT request to /api/videos/00000000-0000-0000-0000-000000000000
   (a non-existent UUID) with valid title, description, and category_id.
2. Inspect the response status code.

Expected result
---------------
The API returns a 404 Not Found status code, indicating the video resource
was not located.

Environment variables
---------------------
- API_BASE_URL       : Backend API base URL (default: http://localhost:8080)
- FIREBASE_TEST_TOKEN: Firebase ID token for test user (required)
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.auth_service import AuthService
from testing.core.config.api_config import APIConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NONEXISTENT_VIDEO_ID = "00000000-0000-0000-0000-000000000000"
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpdateMetadataForNonExistentVideoReturns404:
    """
    Verify that attempting to update metadata for a non-existent video ID
    returns HTTP 404 Not Found.
    """

    def test_update_nonexistent_video_returns_404(self):
        """
        Sending a PUT request to /api/videos/{nonexistent_id} with metadata
        should return 404 Not Found.

        Precondition: User is authenticated via FIREBASE_TEST_TOKEN.
        """
        if not _FIREBASE_TOKEN:
            pytest.skip(
                "FIREBASE_TEST_TOKEN is not set. "
                "Cannot run this test without a valid Firebase token."
            )

        api_config = APIConfig()
        service = AuthService(base_url=api_config.base_url, token=_FIREBASE_TOKEN)

        # Prepare the metadata update payload
        update_payload = {
            "title": "Test Video Title",
            "description": "Test video description",
            "category_id": 1,
            "tags": ["test"],
        }

        # Send PUT request to update metadata for non-existent video
        status_code, response_body = service.put(
            f"/api/videos/{_NONEXISTENT_VIDEO_ID}",
            payload=update_payload,
        )

        # Assert that the response status code is 404 Not Found
        assert status_code == 404, (
            f"Expected HTTP 404 Not Found when updating metadata for "
            f"non-existent video ID {_NONEXISTENT_VIDEO_ID}, "
            f"but got {status_code}. Response body: {response_body}"
        )
