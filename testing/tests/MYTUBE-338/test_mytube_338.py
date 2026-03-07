"""
MYTUBE-338: Video metadata API — 'ready' status videos must contain a non-null hls_manifest_url.

Objective
---------
Verify the data integrity of the video metadata API: no video with status 'ready'
should have a null or empty hls_manifest_url.

Preconditions
-------------
- At least one video with status 'ready' exists in the deployed application.
- The backend API is reachable at API_BASE_URL.

Test steps
----------
1. Send GET /api/videos/:id for a video that has recently finished processing
   (status == 'ready').
2. Inspect the JSON response body.
3. Verify that the ``status`` field is ``ready`` and the ``hls_manifest_url``
   field is not null and contains a non-empty string.
4. Query the recent-videos list endpoint (GET /api/videos/recent) and verify
   this condition for all videos with status 'ready' in the response.

Expected Result
---------------
The API maintains a strict contract where 'ready' status is synonymous with the
availability of the HLS manifest.  No video in 'ready' status returns a null or
empty manifest URL.

Environment variables
---------------------
API_BASE_URL : Base URL of the deployed backend API.
               Default: http://localhost:8080

Architecture notes
------------------
- VideoApiService (testing/components/services/video_api_service.py) is used for
  all HTTP calls: no local API subprocess is started.
- Tests skip gracefully when no ready video exists (CI environments without
  processed video data).
- Module scope is used for the expensive video-discovery step so it runs once
  across all test cases.
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
    return APIConfig()


@pytest.fixture(scope="module")
def video_api_service(api_config: APIConfig) -> VideoApiService:
    return VideoApiService(api_config)


@pytest.fixture(scope="module")
def ready_video(video_api_service: VideoApiService) -> dict:
    """Discover a ready video via the API and return its full detail dict.

    Strategy:
    1. Try VideoApiService.find_ready_video() (scans known CI usernames).
    2. Fall back to GET /api/videos/recent and take the first 'ready' video.

    Skips the module when no ready video is found so the test suite stays green
    on environments without processed video data.
    """
    video_id = None

    # Primary: scan well-known CI usernames
    result = video_api_service.find_ready_video()
    if result is not None:
        video_id, _ = result

    # Fallback: use the recent-videos list endpoint
    if video_id is None:
        _sc, recent = video_api_service.get_recent_videos(limit=20)
        for item in recent or []:
            cand_id = item.get("id") or item.get("video_id")
            if cand_id and item.get("status") == "ready":
                video_id = cand_id
                break

    if video_id is None:
        pytest.skip(
            "No 'ready' video found via the API — skipping MYTUBE-338 tests. "
            "Ensure at least one processed video exists at the target API_BASE_URL."
        )

    detail = video_api_service.get_video(video_id)
    if detail is None:
        pytest.skip(
            f"Could not fetch full video detail for video_id={video_id!r}. "
            "The API may be unreachable."
        )
    return detail


@pytest.fixture(scope="module")
def recent_ready_videos(video_api_service: VideoApiService) -> list[dict]:
    """Return all ready videos from the recent-videos list endpoint.

    Returns an empty list (not skip) when the list endpoint is unavailable or
    returns no ready videos — the dedicated single-video tests already cover
    the contract.
    """
    status_code, videos = video_api_service.get_recent_videos(limit=50)
    if status_code == 0 or videos is None:
        return []
    ready = []
    for v in videos:
        vid_id = v.get("id") or v.get("video_id")
        if not vid_id:
            continue
        _sc, detail = video_api_service.get_video_detail(vid_id)
        if detail and detail.get("status") == "ready":
            ready.append(detail)
    return ready


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestReadyVideoHlsManifestUrl:
    """MYTUBE-338: Every 'ready' video returned by the API must have a non-null hls_manifest_url."""

    # ---- Single-video assertions (GET /api/videos/:id) -------------------

    def test_ready_video_status_field_is_ready(self, ready_video: dict) -> None:
        """The discovered video's status must equal 'ready'."""
        status = ready_video.get("status")
        assert status == "ready", (
            f"Expected video status to be 'ready', got {status!r}. "
            f"Full response: {ready_video}"
        )

    def test_ready_video_has_hls_manifest_url_key(self, ready_video: dict) -> None:
        """The API response for a 'ready' video must include the 'hls_manifest_url' key."""
        assert "hls_manifest_url" in ready_video, (
            f"Expected 'hls_manifest_url' key to be present in the API response, "
            f"but it was absent. Full response: {ready_video}"
        )

    def test_ready_video_hls_manifest_url_is_not_null(self, ready_video: dict) -> None:
        """The 'hls_manifest_url' field must not be null for a 'ready' video."""
        hls_url = ready_video.get("hls_manifest_url")
        assert hls_url is not None, (
            f"Expected 'hls_manifest_url' to be non-null for video in 'ready' status, "
            f"but it was null. Video ID: {ready_video.get('id')!r}. "
            f"Full response: {ready_video}"
        )

    def test_ready_video_hls_manifest_url_is_non_empty_string(self, ready_video: dict) -> None:
        """The 'hls_manifest_url' must be a non-empty string for a 'ready' video."""
        hls_url = ready_video.get("hls_manifest_url")
        assert isinstance(hls_url, str) and hls_url.strip() != "", (
            f"Expected 'hls_manifest_url' to be a non-empty string, "
            f"but got {hls_url!r}. Video ID: {ready_video.get('id')!r}."
        )

    def test_ready_video_hls_manifest_url_looks_like_url(self, ready_video: dict) -> None:
        """The 'hls_manifest_url' must look like a URL (starts with http:// or https://)."""
        hls_url = ready_video.get("hls_manifest_url", "")
        assert isinstance(hls_url, str) and (
            hls_url.startswith("http://") or hls_url.startswith("https://")
        ), (
            f"Expected 'hls_manifest_url' to be an absolute HTTP/HTTPS URL, "
            f"but got {hls_url!r}. Video ID: {ready_video.get('id')!r}."
        )

    # ---- List-level assertions (GET /api/videos/recent) ------------------

    def test_all_recent_ready_videos_have_non_null_hls_manifest_url(
        self, recent_ready_videos: list[dict]
    ) -> None:
        """Every 'ready' video in the recent-videos list must have a non-null hls_manifest_url.

        If no ready videos are in the recent list the test passes vacuously —
        the single-video tests above already validate the contract.
        """
        violations = [
            {
                "id": v.get("id"),
                "hls_manifest_url": v.get("hls_manifest_url"),
            }
            for v in recent_ready_videos
            if not v.get("hls_manifest_url")
        ]
        assert not violations, (
            f"Found {len(violations)} 'ready' video(s) with null/empty hls_manifest_url "
            f"in the recent-videos list. Violating entries:\n"
            + "\n".join(
                f"  video_id={e['id']!r}, hls_manifest_url={e['hls_manifest_url']!r}"
                for e in violations
            )
        )

    def test_all_recent_ready_videos_hls_url_starts_with_http(
        self, recent_ready_videos: list[dict]
    ) -> None:
        """Every 'ready' video in the recent list must have an absolute HTTP/HTTPS hls_manifest_url."""
        violations = [
            {
                "id": v.get("id"),
                "hls_manifest_url": v.get("hls_manifest_url"),
            }
            for v in recent_ready_videos
            if v.get("hls_manifest_url") and not (
                str(v["hls_manifest_url"]).startswith("http://")
                or str(v["hls_manifest_url"]).startswith("https://")
            )
        ]
        assert not violations, (
            f"Found {len(violations)} 'ready' video(s) with a relative or invalid "
            f"hls_manifest_url in the recent-videos list. Violating entries:\n"
            + "\n".join(
                f"  video_id={e['id']!r}, hls_manifest_url={e['hls_manifest_url']!r}"
                for e in violations
            )
        )
