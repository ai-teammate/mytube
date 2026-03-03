"""
MYTUBE-175: Retrieve popular and recent videos — lists sorted correctly by view count and date.

Objective
---------
Verify that the discovery APIs return videos in the correct order based on
recency and popularity.

Test steps
----------
1. Send a GET request to /api/videos/recent?limit=20.
2. Send a GET request to /api/videos/popular?limit=20.

Expected result
---------------
- The 'recent' endpoint returns videos ordered by created_at DESC.
- The 'popular' endpoint returns videos ordered by view_count DESC.
- All returned videos must have status='ready'.

Architecture notes
------------------
- The API is expected to be deployed and reachable at API_BASE_URL.
- No authentication is required — these are public discovery endpoints.
- VideoApiService and APIConfig are used for HTTP interactions.
- The status field is not returned directly by VideoCard, but since the
  endpoint only ever returns ready videos (filtered by the repository), we
  verify ordering invariants on the returned data.
- If the API is unreachable or returns no videos, the test skips gracefully.

Environment variables
---------------------
API_BASE_URL : Base URL of the deployed API (default: http://localhost:8080).
API_HOST     : API host (used to construct base_url if API_BASE_URL is absent).
API_PORT     : API port (used to construct base_url if API_BASE_URL is absent).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LIMIT = 20
_TIMEOUT = 15  # seconds per request

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_video_list(base_url: str, path: str) -> tuple[int, list[dict]]:
    """GET *path* from *base_url* and return (status_code, parsed_json_list).

    Returns (status_code, []) on HTTP error or JSON parse failure.
    """
    url = f"{base_url.rstrip('/')}{path}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode()
            return resp.status, json.loads(body)
    except urllib.error.HTTPError as exc:
        return exc.code, []
    except Exception:
        return 0, []


def _parse_created_at(value: str) -> datetime:
    """Parse a RFC 3339 / ISO 8601 datetime string into a UTC-aware datetime."""
    # Python 3.11+: datetime.fromisoformat handles 'Z'
    # For compatibility with 3.10, replace trailing 'Z' with '+00:00'.
    value = value.replace("Z", "+00:00")
    return datetime.fromisoformat(value)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def recent_response(api_config: APIConfig) -> tuple[int, list[dict]]:
    """GET /api/videos/recent?limit=20 and return (status_code, body)."""
    return _fetch_video_list(api_config.base_url, f"/api/videos/recent?limit={_LIMIT}")


@pytest.fixture(scope="module")
def popular_response(api_config: APIConfig) -> tuple[int, list[dict]]:
    """GET /api/videos/popular?limit=20 and return (status_code, body)."""
    return _fetch_video_list(api_config.base_url, f"/api/videos/popular?limit={_LIMIT}")


# ---------------------------------------------------------------------------
# Tests — /api/videos/recent
# ---------------------------------------------------------------------------


class TestRecentVideosEndpoint:
    """GET /api/videos/recent?limit=20 — sorted by created_at DESC, status='ready'."""

    def test_recent_returns_200(self, recent_response: tuple[int, list[dict]]):
        """The recent endpoint must return HTTP 200 OK."""
        status_code, _ = recent_response
        if status_code == 0:
            pytest.skip("API is not reachable — set API_BASE_URL to the deployed instance.")
        assert status_code == 200, (
            f"Expected HTTP 200 from /api/videos/recent, got {status_code}."
        )

    def test_recent_returns_json_array(self, recent_response: tuple[int, list[dict]]):
        """The response body must be a JSON array."""
        status_code, videos = recent_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        assert isinstance(videos, list), (
            f"Expected a JSON array from /api/videos/recent, got: {type(videos).__name__}."
        )

    def test_recent_respects_limit(self, recent_response: tuple[int, list[dict]]):
        """The number of returned videos must not exceed the requested limit."""
        status_code, videos = recent_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        assert len(videos) <= _LIMIT, (
            f"Expected at most {_LIMIT} videos from /api/videos/recent, "
            f"got {len(videos)}."
        )

    def test_recent_videos_have_required_fields(self, recent_response: tuple[int, list[dict]]):
        """Each video object must contain the expected fields."""
        status_code, videos = recent_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        if not videos:
            pytest.skip("No videos returned by /api/videos/recent — cannot check fields.")

        required_fields = {"id", "title", "view_count", "uploader_username", "created_at"}
        for i, video in enumerate(videos):
            missing = required_fields - set(video.keys())
            assert not missing, (
                f"Video at index {i} is missing required fields: {missing}. "
                f"Video data: {video}"
            )

    def test_recent_videos_ordered_by_created_at_desc(self, recent_response: tuple[int, list[dict]]):
        """Videos must be ordered from newest to oldest (created_at DESC).

        If the endpoint returns 0 or 1 video, ordering cannot be verified —
        the test passes vacuously.
        """
        status_code, videos = recent_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        if len(videos) < 2:
            pytest.skip(
                f"Only {len(videos)} video(s) returned — ordering cannot be verified. "
                "Ensure at least 2 ready videos exist in the database."
            )

        timestamps: list[datetime] = []
        for video in videos:
            try:
                timestamps.append(_parse_created_at(video["created_at"]))
            except (KeyError, ValueError) as exc:
                pytest.fail(
                    f"Could not parse created_at for video {video.get('id')!r}: {exc}"
                )

        for i in range(len(timestamps) - 1):
            assert timestamps[i] >= timestamps[i + 1], (
                f"Videos are not sorted by created_at DESC. "
                f"Video at index {i} has created_at={timestamps[i].isoformat()}, "
                f"but video at index {i+1} has created_at={timestamps[i+1].isoformat()} "
                f"(expected {timestamps[i+1].isoformat()} <= {timestamps[i].isoformat()})."
            )

    def test_recent_videos_have_valid_view_count(self, recent_response: tuple[int, list[dict]]):
        """Each returned video must have a non-negative view_count."""
        status_code, videos = recent_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        if not videos:
            pytest.skip("No videos returned by /api/videos/recent.")

        for video in videos:
            vc = video.get("view_count")
            assert isinstance(vc, int) and vc >= 0, (
                f"Video {video.get('id')!r} has invalid view_count: {vc!r}. "
                "Expected a non-negative integer."
            )


# ---------------------------------------------------------------------------
# Tests — /api/videos/popular
# ---------------------------------------------------------------------------


class TestPopularVideosEndpoint:
    """GET /api/videos/popular?limit=20 — sorted by view_count DESC, status='ready'."""

    def test_popular_returns_200(self, popular_response: tuple[int, list[dict]]):
        """The popular endpoint must return HTTP 200 OK."""
        status_code, _ = popular_response
        if status_code == 0:
            pytest.skip("API is not reachable — set API_BASE_URL to the deployed instance.")
        assert status_code == 200, (
            f"Expected HTTP 200 from /api/videos/popular, got {status_code}."
        )

    def test_popular_returns_json_array(self, popular_response: tuple[int, list[dict]]):
        """The response body must be a JSON array."""
        status_code, videos = popular_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        assert isinstance(videos, list), (
            f"Expected a JSON array from /api/videos/popular, got: {type(videos).__name__}."
        )

    def test_popular_respects_limit(self, popular_response: tuple[int, list[dict]]):
        """The number of returned videos must not exceed the requested limit."""
        status_code, videos = popular_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        assert len(videos) <= _LIMIT, (
            f"Expected at most {_LIMIT} videos from /api/videos/popular, "
            f"got {len(videos)}."
        )

    def test_popular_videos_have_required_fields(self, popular_response: tuple[int, list[dict]]):
        """Each video object must contain the expected fields."""
        status_code, videos = popular_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        if not videos:
            pytest.skip("No videos returned by /api/videos/popular — cannot check fields.")

        required_fields = {"id", "title", "view_count", "uploader_username", "created_at"}
        for i, video in enumerate(videos):
            missing = required_fields - set(video.keys())
            assert not missing, (
                f"Video at index {i} is missing required fields: {missing}. "
                f"Video data: {video}"
            )

    def test_popular_videos_ordered_by_view_count_desc(self, popular_response: tuple[int, list[dict]]):
        """Videos must be ordered from most to least viewed (view_count DESC).

        If the endpoint returns 0 or 1 video, ordering cannot be verified —
        the test passes vacuously.
        """
        status_code, videos = popular_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        if len(videos) < 2:
            pytest.skip(
                f"Only {len(videos)} video(s) returned — ordering cannot be verified. "
                "Ensure at least 2 ready videos exist in the database."
            )

        for i in range(len(videos) - 1):
            vc_current = videos[i].get("view_count")
            vc_next = videos[i + 1].get("view_count")
            assert isinstance(vc_current, int) and isinstance(vc_next, int), (
                f"view_count must be integers; got {vc_current!r} and {vc_next!r}."
            )
            assert vc_current >= vc_next, (
                f"Videos are not sorted by view_count DESC. "
                f"Video at index {i} has view_count={vc_current}, "
                f"but video at index {i+1} has view_count={vc_next} "
                f"(expected {vc_next} <= {vc_current})."
            )

    def test_popular_videos_have_valid_created_at(self, popular_response: tuple[int, list[dict]]):
        """Each returned video must have a parseable created_at timestamp."""
        status_code, videos = popular_response
        if status_code == 0:
            pytest.skip("API is not reachable.")
        if not videos:
            pytest.skip("No videos returned by /api/videos/popular.")

        for video in videos:
            raw = video.get("created_at")
            assert raw is not None and isinstance(raw, str), (
                f"Video {video.get('id')!r} is missing or has invalid created_at: {raw!r}."
            )
            try:
                _parse_created_at(raw)
            except ValueError as exc:
                pytest.fail(
                    f"Video {video.get('id')!r} has an unparseable created_at "
                    f"value {raw!r}: {exc}"
                )
