"""
MYTUBE-268: Request videos for non-existent category ID — empty data array returned

Objective
---------
Verify that the API returns an empty list instead of an error or unfiltered 
videos when a valid-format but non-existent ID is used.

Preconditions
-------------
- The backend API is deployed and reachable at API_BASE_URL.
- No authentication required for GET /api/videos endpoint.

Test Steps
----------
1. Identify a category ID that does not exist in the database (e.g., 99999).
2. Send a GET request to /api/videos?category_id=99999&limit=20.

Expected Result
---------------
The API returns a 200 OK status code with an empty data array [], 
confirming no videos were found for that ID.

Environment Variables
---------------------
API_BASE_URL         Backend API base URL.
                     Default: http://localhost:8080 (via APIConfig).
                     Set to https://mytube-api-*.run.app in CI.

Architecture
------------
- CategoryBrowseService (API service component) for querying /api/videos.
- APIConfig from testing/core/config/ for environment config.
- No hardcoded URLs or credentials.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.components.services.category_browse_service import CategoryBrowseService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Use a category ID that should not exist in any test environment
_NONEXISTENT_CATEGORY_ID = 99999
_EXPECTED_LIMIT = 20


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    """Return an APIConfig loaded from environment variables."""
    return APIConfig()


@pytest.fixture(scope="module")
def category_service(api_config: APIConfig) -> CategoryBrowseService:
    """Return a CategoryBrowseService instance."""
    return CategoryBrowseService(api_config)


@pytest.fixture(scope="module")
def nonexistent_category_response(
    category_service: CategoryBrowseService,
) -> object:
    """Query the API for videos in a non-existent category."""
    return category_service.get_videos_by_category(
        category_id=_NONEXISTENT_CATEGORY_ID, limit=_EXPECTED_LIMIT
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNonexistentCategoryVideos:
    """GET /api/videos?category_id=99999 must return 200 with empty array."""

    def test_status_code_is_200(self, nonexistent_category_response: object) -> None:
        """The response status must be HTTP 200 OK."""
        assert nonexistent_category_response.status_code == 200, (
            f"Expected HTTP 200 for non-existent category, "
            f"got {nonexistent_category_response.status_code}. "
            f"Response body: {nonexistent_category_response.raw_body}"
        )

    def test_response_body_is_empty_array(
        self, nonexistent_category_response: object
    ) -> None:
        """The response body must be an empty JSON array []."""
        assert nonexistent_category_response.videos == [], (
            f"Expected empty array for non-existent category_id={_NONEXISTENT_CATEGORY_ID}, "
            f"got {len(nonexistent_category_response.videos)} videos: "
            f"{nonexistent_category_response.raw_body}"
        )

    def test_no_error_message(self, nonexistent_category_response: object) -> None:
        """The response should not contain an error message."""
        assert nonexistent_category_response.error_message is None, (
            f"Expected no error for non-existent category, "
            f"got: {nonexistent_category_response.error_message}"
        )
