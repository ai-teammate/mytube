"""
MYTUBE-289: Retrieve video metadata with no category — category_id is null in response.

Objective
---------
Verify that the GET /api/videos/:id endpoint correctly returns a null value for
category_id when no category is assigned to the video.

Preconditions
-------------
A video exists in the database with the category_id field set to null.

Steps
-----
1. Send a GET request to /api/videos/:id for a video with no category.
2. Inspect the JSON response body.

Expected Result
---------------
The API returns a 200 OK status. The response body includes the category_id
field with a value of null.

Architecture notes
------------------
- VideoApiService is used to discover a video ID with category_id = null from
  /api/videos/recent and, as a fallback, from the known CI usernames.
- A raw HTTP request is made to GET /api/videos/:id to capture both the HTTP
  status code and the full JSON response body.
- APIConfig from testing/core/config/ supplies the base URL via environment
  variables; no hardcoded URLs.
- If no suitable video exists in the deployed environment, the test skips
  gracefully.

Environment variables
---------------------
API_BASE_URL  Base URL of the deployed API.
              Default: http://localhost:8080 (via APIConfig).
API_HOST      API host (used to construct base_url if API_BASE_URL is absent).
API_PORT      API port (used to construct base_url if API_BASE_URL is absent).
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    """Return APIConfig loaded from environment variables."""
    return APIConfig()


@pytest.fixture(scope="module")
def video_service(api_config: APIConfig) -> VideoApiService:
    """Return a VideoApiService instance."""
    return VideoApiService(api_config)


@pytest.fixture(scope="module")
def no_category_video_id(video_service: VideoApiService) -> str:
    """Return the ID of a video with category_id = null.

    Skips the test module if no such video is found in the deployed environment.
    """
    video_id = video_service.find_video_without_category()
    if video_id is None:
        pytest.skip(
            "No video with category_id = null found in the deployed environment. "
            "Ensure at least one video without a category exists. "
            "Set API_BASE_URL to the deployed instance if not already set."
        )
    return video_id


@pytest.fixture(scope="module")
def video_detail_response(
    video_service: VideoApiService, no_category_video_id: str
) -> tuple[int, dict | None]:
    """Return (status_code, body) from GET /api/videos/:id for the no-category video."""
    return video_service.get_video_detail(no_category_video_id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVideoMetadataNullCategory:
    """MYTUBE-289: GET /api/videos/:id returns null category_id for uncategorised video."""

    def test_status_code_is_200(
        self,
        video_detail_response: tuple[int, dict | None],
        no_category_video_id: str,
    ) -> None:
        """GET /api/videos/:id must return HTTP 200 OK."""
        status_code, body = video_detail_response
        assert status_code == 200, (
            f"Expected HTTP 200 for GET /api/videos/{no_category_video_id}, "
            f"but received HTTP {status_code}. "
            f"Response body: {body!r}"
        )

    def test_response_body_contains_category_id_field(
        self,
        video_detail_response: tuple[int, dict | None],
        no_category_video_id: str,
    ) -> None:
        """The response body must be a JSON object that includes the category_id field."""
        status_code, body = video_detail_response
        assert body is not None, (
            f"Expected a JSON object in the response for "
            f"GET /api/videos/{no_category_video_id}, but the response body was null "
            f"or could not be parsed. HTTP status: {status_code}."
        )
        assert "category_id" in body, (
            f"Expected the response body for GET /api/videos/{no_category_video_id} "
            f"to contain the 'category_id' field, but it was absent. "
            f"Response keys: {list(body.keys())}"
        )

    def test_category_id_is_null(
        self,
        video_detail_response: tuple[int, dict | None],
        no_category_video_id: str,
    ) -> None:
        """The category_id field must be null (JSON null / Python None)."""
        _status, body = video_detail_response
        assert body is not None, (
            "Response body is unexpectedly None — see test_response_body_contains_category_id_field."
        )
        category_id = body.get("category_id")
        assert category_id is None, (
            f"Expected category_id to be null for video '{no_category_video_id}' "
            f"(which has no category assigned), but got category_id = {category_id!r}. "
            f"Full response: {body!r}"
        )
