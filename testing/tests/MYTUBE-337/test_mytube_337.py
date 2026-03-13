"""
MYTUBE-337: Load watch page for ready video — Video.js player mounts and the
"Video not available yet" message is hidden.

Objective
---------
Verify that the watch page mounts the Video.js player for videos with status
"ready" and does not show the fallback "Video not available yet." message.

Preconditions
-------------
- The deployed web app is reachable via APP_URL / WEB_BASE_URL (WebConfig)
- Tests use the placeholder watch page ID "_" and Playwright route interception
  to inject deterministic video detail data.

"""
from __future__ import annotations

import json
import os
import sys

import pytest
from playwright.sync_api import Browser, Page, Request, Route, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.watch_page.watch_page import WatchPage


# ---------------------------------------------------------------------------
# Constants / Mock data
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000
_PLAYER_INIT_TIMEOUT = 20_000

_PLACEHOLDER_VIDEO_ID = "_"

_MOCK_VIDEO_DETAIL = {
    "id": _PLACEHOLDER_VIDEO_ID,
    "title": "MYTUBE-337 Ready Video",
    "description": "Automated test video for MYTUBE-337.",
    "thumbnail_url": None,
    "hls_manifest_url": "https://example.com/ready.m3u8",
    "view_count": 42,
    "status": "ready",
    "tags": ["test", "ready"],
    "uploader": {"username": "ci-test", "avatar_url": None},
    "created_at": "2026-01-01T00:00:00.000Z",
}


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _handle_video_route(route: Route, request: Request) -> None:
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(_MOCK_VIDEO_DETAIL),
    )

# Minimal valid HLS playlist returned for any .m3u8 request so Video.js can initialise
_MINIMAL_M3U8 = (
    "#EXTM3U\n"
    "#EXT-X-VERSION:3\n"
    "#EXT-X-TARGETDURATION:0\n"
    "#EXT-X-MEDIA-SEQUENCE:0\n"
    "#EXT-X-ENDLIST\n"
)


def _handle_m3u8_route(route: Route, request: Request) -> None:
    route.fulfill(
        status=200,
        content_type="application/vnd.apple.mpegurl",
        body=_MINIMAL_M3U8,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def watch_page_loaded(browser: Browser, web_config: WebConfig) -> dict:
    ctx = browser.new_context()
    page: Page = ctx.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Register route interceptors to return deterministic video detail
    page.route("**/api/videos/_", _handle_video_route)
    page.route("**/api/videos/_/", _handle_video_route)
    # Intercept any HLS manifest requests and return a minimal playlist so Video.js doesn't enter error state
    page.route("**/*.m3u8", _handle_m3u8_route)

    watch_pg = WatchPage(page)
    # Navigate and capture network requests (HLS manifest requests may be fired)
    state = watch_pg.navigate_and_capture_network(web_config.base_url, _PLACEHOLDER_VIDEO_ID)

    # Wait for video metadata/title to render
    try:
        page.wait_for_selector("h1", state="visible", timeout=5000)
    except Exception:
        pass

    # Wait for Video.js player to appear / initialise so assertions don't race
    try:
        page.wait_for_selector(".video-js, [data-vjs-player], .vjs-control-bar", timeout=_PLAYER_INIT_TIMEOUT)
    except Exception:
        pass

    yield {"page": page, "watch_page": watch_pg, "state": state}

    ctx.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWatchPageReadyVideo:
    """Verify player mounts and "Video not available yet." is hidden for ready videos."""

    def test_player_initialises_and_no_unavailable_message(
        self, watch_page_loaded: dict, web_config: WebConfig
    ):
        page: Page = watch_page_loaded["page"]
        watch_pg: WatchPage = watch_page_loaded["watch_page"]

        # Ensure the title rendered
        title = watch_pg.get_title_heading()
        assert title is not None and "Ready Video" in title, (
            f"Expected video title to render on the watch page. Current URL: {page.url}"
        )

        # The fallback message 'Video not available yet.' must NOT be present
        unavailable_count = page.get_by_text("Video not available yet.").count()
        assert unavailable_count == 0, (
            "Found the fallback 'Video not available yet.' message for a video in 'ready' status."
        )

        # Player container should be present
        assert watch_pg.is_player_container_visible(), (
            "[data-vjs-player] container not visible — Video.js player did not mount."
        )

        # Underlying <video> element should be present in the DOM
        assert watch_pg.is_video_element_present(), (
            "<video> element with class 'video-js' or 'vjs-tech' not found in the player container."
        )

        # Player initialisation and presence of video element are primary assertions for this test.
        # Detailed playback/HLS assertions are covered by dedicated tests (MYTUBE-146 etc.).
        pass
