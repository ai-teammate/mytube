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
- VideoApiService from testing/components/services/video_api_service.py for video discovery.
- Playwright sync API with pytest fixtures.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.api_config import APIConfig
from testing.components.pages.watch_page.watch_page import WatchPage, WatchPageState
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000      # ms — max time for initial page load


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
def video_api_service(api_config: APIConfig) -> VideoApiService:
    return VideoApiService(api_config)


@pytest.fixture(scope="module")
def ready_video(video_api_service: VideoApiService) -> tuple[str, str | None]:
    """Return (video_id, hls_manifest_url) for a ready video."""
    override_id = os.getenv("MYTUBE_146_VIDEO_ID", "").strip()
    return video_api_service.find_ready_video(override_id=override_id)


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
) -> tuple[WatchPage, WatchPageState, str | None]:
    """Navigate to the watch page for the ready video.

    Uses WatchPage.navigate_and_capture_network() so network capture is fully
    encapsulated within the page object.  Yields (watch_page, state, hls_manifest_url).
    """
    video_id, hls_manifest_url = ready_video
    state: WatchPageState = watch_page_obj.navigate_and_capture_network(
        web_config.base_url, video_id
    )
    yield watch_page_obj, state, hls_manifest_url


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVideoWatchPagePlayerInit:
    """MYTUBE-146: Video.js player initializes on the public watch page."""

    def test_player_container_visible(
        self, watch_page_loaded: tuple[WatchPage, WatchPageState, str | None]
    ):
        """The [data-vjs-player] wrapper div must be present and visible in the DOM."""
        watch_page, _state, _expected_url = watch_page_loaded
        assert watch_page.is_player_container_visible(), (
            "Expected [data-vjs-player] container to be visible, but it was not found. "
            "The Video.js player wrapper is missing from the page."
        )

    def test_video_element_present(
        self, watch_page_loaded: tuple[WatchPage, WatchPageState, str | None]
    ):
        """A <video class='video-js'> element must exist in the DOM."""
        watch_page, _state, _expected_url = watch_page_loaded
        assert watch_page.is_video_element_present(), (
            "Expected a <video class='video-js'> element in the DOM, but none was found. "
            "Video.js may not have rendered its player element."
        )

    def test_player_initialised(
        self, watch_page_loaded: tuple[WatchPage, WatchPageState, str | None]
    ):
        """Video.js must have fully initialized — vjs-paused or vjs-playing class must be present."""
        watch_page, _state, _expected_url = watch_page_loaded
        assert watch_page.is_player_initialised(), (
            "Expected Video.js to be fully initialised (vjs-paused or vjs-playing class present), "
            "but neither class was found within the timeout. "
            "The player may have failed to initialise or the HLS source was not set."
        )

    def test_control_bar_visible(
        self, watch_page_loaded: tuple[WatchPage, WatchPageState, str | None]
    ):
        """The Video.js control bar must be visible after player initialization."""
        watch_page, _state, _expected_url = watch_page_loaded
        assert watch_page.is_controls_visible(), (
            "Expected the Video.js .vjs-control-bar to be visible, but it was not. "
            "The player controls may not have rendered correctly."
        )

    def test_hls_manifest_requested(
        self, watch_page_loaded: tuple[WatchPage, WatchPageState, str | None]
    ):
        """The browser must have issued a request for the HLS manifest (.m3u8).

        Checks two things:
        1. If the expected hls_manifest_url is known, verify it was requested.
        2. Otherwise, verify at least one .m3u8 request was made.
        """
        _watch_page, state, expected_url = watch_page_loaded
        captured = state.hls_requests

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

    def test_video_not_found_message_absent(
        self, watch_page_loaded: tuple[WatchPage, WatchPageState, str | None]
    ):
        """The 'Video not found.' error message must NOT be shown for a ready video."""
        watch_page, _state, _expected_url = watch_page_loaded
        assert not watch_page.is_not_found(), (
            "The page shows 'Video not found.' for a video with status='ready'. "
            "The watch page may not be fetching or rendering the video correctly."
        )

    def test_video_title_displayed(
        self, watch_page_loaded: tuple[WatchPage, WatchPageState, str | None]
    ):
        """The video title <h1> must be visible with non-empty text."""
        watch_page, _state, _expected_url = watch_page_loaded
        title = watch_page.get_video_title()
        assert title, (
            f"Expected a non-empty <h1> title on the watch page, but got: {title!r}"
        )
