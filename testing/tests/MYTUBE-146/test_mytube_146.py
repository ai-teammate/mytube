"""
MYTUBE-146: Load public video watch page — Video.js player initializes and HLS stream plays.

Verifies that the public video page at /v/[id] correctly initializes the Video.js
player and requests the HLS manifest URL for a video with status 'ready'.

Preconditions
-------------
- A video exists in the database with status 'ready'.
- A valid HLS manifest is accessible via the CDN URL.

Test steps
----------
1. Query the API (/api/users/:username) or use a known ready video ID via the
   /api/videos/:id endpoint to locate a video with status='ready' and a non-null
   hls_manifest_url.
2. Navigate to /v/<id> in the browser.
3. Wait for the Video.js player container to be present in the DOM.
4. Assert that the Video.js player has initialised (vjs-paused or vjs-playing class applied).
5. Capture network requests and assert that a request matching the hls_manifest_url
   was fired.

Environment variables
---------------------
- APP_URL / WEB_BASE_URL  : Base URL of the deployed web app.
                            Default: https://ai-teammate.github.io/mytube
- API_BASE_URL            : Base URL of the backend API.
                            Default: http://localhost:8080
- MYTUBE_146_VIDEO_ID     : Optional. Override video ID to use for the test.
                            If set, the test skips the API discovery step.
- PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
- PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses WatchPage (Page Object) from testing/components/pages/watch_page/.
- WebConfig from testing/core/config/web_config.py centralises all env var access.
- APIConfig from testing/core/config/api_config.py for backend URL.
- Playwright sync API with pytest fixtures.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.api_config import APIConfig
from testing.components.pages.watch_page.watch_page import WatchPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLAYER_WAIT_TIMEOUT = 20_000    # ms — wait for Video.js to initialise
_PAGE_LOAD_TIMEOUT = 30_000      # ms — max time for initial page load
_NETWORK_CAPTURE_WAIT = 3_000    # ms — wait for manifest request after load


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fetch_json(url: str) -> dict | None:
    """Perform a simple HTTP GET and return parsed JSON, or None on error."""
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _discover_ready_video(api_config: APIConfig) -> tuple[str, str | None]:
    """Return (video_id, hls_manifest_url) for the first ready video found via the API.

    Strategy:
    1. Check MYTUBE_146_VIDEO_ID env override first.
    2. Try to GET /api/videos/<id> for the override ID.
    3. If no override, try a known test approach: query the API users endpoint
       for a user named 'tester' (common in CI) and pick the first video.
    4. Return (video_id, hls_manifest_url) — hls_manifest_url may be None if
       the CDN is not configured (e.g. local dev).

    Raises pytest.skip if no ready video can be located.
    """
    # ── Override via environment variable ──────────────────────────────────
    override_id = os.getenv("MYTUBE_146_VIDEO_ID", "").strip()
    if override_id:
        url = f"{api_config.base_url}/api/videos/{override_id}"
        data = _fetch_json(url)
        if data and data.get("status") == "ready":
            return data["id"], data.get("hls_manifest_url")
        pytest.skip(
            f"MYTUBE_146_VIDEO_ID={override_id!r} set but video not found or not ready. "
            f"Response: {data}"
        )

    # ── Auto-discover: try known usernames used in CI environments ─────────
    candidate_usernames = ["tester", "testuser", "alice", "admin"]
    for username in candidate_usernames:
        url = f"{api_config.base_url}/api/users/{username}"
        data = _fetch_json(url)
        if not data:
            continue
        videos = data.get("videos", [])
        for v in videos:
            vid_id = v.get("id") or v.get("video_id")
            if not vid_id:
                continue
            # Fetch full video detail to get hls_manifest_url and status
            detail_url = f"{api_config.base_url}/api/videos/{vid_id}"
            detail = _fetch_json(detail_url)
            if detail and detail.get("status") == "ready":
                return detail["id"], detail.get("hls_manifest_url")

    pytest.skip(
        "No ready video found via API. "
        "Set MYTUBE_146_VIDEO_ID env var to a valid video UUID with status='ready', "
        "or ensure a ready video exists for a known test user."
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def ready_video(api_config: APIConfig) -> tuple[str, str | None]:
    """Return (video_id, hls_manifest_url) for a ready video."""
    return _discover_ready_video(api_config)


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    """Open a fresh browser context with no stored auth state."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def watch_page_obj(page: Page) -> WatchPage:
    return WatchPage(page)


@pytest.fixture(scope="module")
def watch_page_loaded(
    web_config: WebConfig,
    watch_page_obj: WatchPage,
    ready_video: tuple[str, str | None],
):
    """Navigate to the watch page for the ready video and yield the WatchPage object.

    Network requests for HLS manifests are also captured.
    """
    video_id, hls_manifest_url = ready_video
    captured_requests: list[str] = []

    def on_request(request):
        url = request.url
        if ".m3u8" in url or "hls" in url.lower():
            captured_requests.append(url)

    watch_page_obj._page.on("request", on_request)
    watch_page_obj.navigate(web_config.base_url, video_id)

    # Give the player time to fire the manifest request
    watch_page_obj._page.wait_for_timeout(_NETWORK_CAPTURE_WAIT)
    watch_page_obj._page.remove_listener("request", on_request)

    # Attach captured data to the page object for use in tests
    watch_page_obj._captured_hls_urls = captured_requests
    watch_page_obj._expected_hls_url = hls_manifest_url

    yield watch_page_obj


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVideoWatchPagePlayerInit:
    """MYTUBE-146: Video.js player initializes on the public watch page."""

    def test_player_container_visible(self, watch_page_loaded: WatchPage):
        """The [data-vjs-player] wrapper div must be present and visible in the DOM."""
        assert watch_page_loaded.is_player_container_visible(), (
            "Expected [data-vjs-player] container to be visible, but it was not found. "
            "The Video.js player wrapper is missing from the page."
        )

    def test_video_element_present(self, watch_page_loaded: WatchPage):
        """A <video class='video-js'> element must exist in the DOM."""
        assert watch_page_loaded.is_video_element_present(), (
            "Expected a <video class='video-js'> element in the DOM, but none was found. "
            "Video.js may not have rendered its player element."
        )

    def test_player_initialised(self, watch_page_loaded: WatchPage):
        """Video.js must have fully initialized — vjs-paused or vjs-playing class must be present."""
        assert watch_page_loaded.is_player_initialised(), (
            "Expected Video.js to be fully initialised (vjs-paused or vjs-playing class present), "
            "but neither class was found within the timeout. "
            "The player may have failed to initialise or the HLS source was not set."
        )

    def test_control_bar_visible(self, watch_page_loaded: WatchPage):
        """The Video.js control bar must be visible after player initialization."""
        assert watch_page_loaded.is_controls_visible(), (
            "Expected the Video.js .vjs-control-bar to be visible, but it was not. "
            "The player controls may not have rendered correctly."
        )

    def test_hls_manifest_requested(self, watch_page_loaded: WatchPage):
        """The browser must have issued a request for the HLS manifest (.m3u8).

        Checks two things:
        1. If the expected hls_manifest_url is known, verify it was requested.
        2. Otherwise, verify at least one .m3u8 request was made.
        """
        expected_url = watch_page_loaded._expected_hls_url
        captured = watch_page_loaded._captured_hls_urls

        if expected_url:
            assert any(expected_url in req for req in captured), (
                f"Expected HLS manifest request to '{expected_url}', "
                f"but it was not found in captured network requests: {captured!r}. "
                "The Video.js player may not have loaded the HLS source."
            )
        else:
            assert len(captured) > 0, (
                "Expected at least one .m3u8 network request to be made by the player, "
                f"but no HLS requests were captured. Captured URLs: {captured!r}"
            )

    def test_video_not_found_message_absent(self, watch_page_loaded: WatchPage):
        """The 'Video not found.' error message must NOT be shown for a ready video."""
        assert not watch_page_loaded.is_not_found(), (
            "The page shows 'Video not found.' for a video with status='ready'. "
            "The watch page may not be fetching or rendering the video correctly."
        )

    def test_video_title_displayed(self, watch_page_loaded: WatchPage):
        """The video title <h1> must be visible with non-empty text."""
        title = watch_page_loaded.get_video_title()
        assert title, (
            f"Expected a non-empty <h1> title on the watch page, but got: {title!r}"
        )
