"""
MYTUBE-246: Load public video watch page with unreachable HLS manifest — Video.js player displays media error.

Objective
---------
Verify that the Video.js player correctly identifies and reports a network failure when the HLS manifest
cannot be retrieved from the CDN. The player must display a visible error overlay to prevent silent failure.

Preconditions
-------------
- The web application is deployed and reachable at WEB_BASE_URL.
- Playwright can intercept and mock API responses.

Test Steps
----------
1. Navigate to the video watch page.
2. Mock the API to return a video with an unreachable manifest URL.
3. Wait for the Video.js player to attempt initialization and source loading.
4. Verify the player displays an error overlay.

Expected Result
---------------
The Video.js player initializes but displays a visible error overlay indicating that the media could
not be loaded due to a network or server failure, preventing a silent failure.

Architecture Notes
------------------
- Uses WatchPage (Page Object) from testing/components/pages/watch_page/.
- Uses Playwright route interception to mock API responses (no API server required).
- Tests against the static placeholder watch page (/v/_/) with mocked data.
- Playwright sync API with pytest fixtures.
- No hardcoded URLs, API servers, or database access required.

Environment Variables
---------------------
- APP_URL / WEB_BASE_URL: Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
- PLAYWRIGHT_HEADLESS  : Run browser headless (default: true).
- PLAYWRIGHT_SLOW_MO   : Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from playwright.sync_api import Browser, Page, Route, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.watch_page.watch_page import WatchPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000    # ms
_PLAYER_INIT_TIMEOUT = 20_000  # ms

# Placeholder video ID — the only pre-generated watch page in the static export
_PLACEHOLDER_VIDEO_ID = "_"

# Unreachable manifest URL — guaranteed to fail
_UNREACHABLE_MANIFEST_URL = "https://storage.googleapis.com/non-existent-bucket-12345/manifest.m3u8"

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_VIDEO_DETAIL = {
    "id": _PLACEHOLDER_VIDEO_ID,
    "title": "Video with Unreachable Manifest MYTUBE-246",
    "description": "Test video for MYTUBE-246 with unreachable HLS manifest.",
    "thumbnail_url": None,
    "hls_manifest_url": _UNREACHABLE_MANIFEST_URL,
    "status": "ready",
    "uploader": {
        "id": "00000000-0000-0000-0000-000000000000",
        "username": "tester",
    },
    "category": None,
    "tags": [],
    "view_count": 0,
    "rating": {"my_rating": None, "average": 0},
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-01T00:00:00Z",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


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
    """Open a fresh browser context and page."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def watch_page(page: Page) -> WatchPage:
    """Create a WatchPage page object."""
    return WatchPage(page)


@pytest.fixture(scope="module")
def mocked_watch_page(page: Page, web_config: WebConfig):
    """
    Register route mocking and set up the watch page with mocked data.

    Intercepts API calls and returns mock responses so the watch page renders
    deterministic data regardless of backend state.
    """
    # Define the route handler for the video detail API
    def handle_video_request(route: Route):
        if route.request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_MOCK_VIDEO_DETAIL),
            )
        else:
            route.continue_()

    # Register the route handler BEFORE navigating
    page.route("**/api/videos/_", handle_video_request)
    page.route("**/api/videos/_/", handle_video_request)

    # Create the watch page object
    watch_page = WatchPage(page)

    yield watch_page

    # Cleanup
    page.unroute("**/api/videos/_")
    page.unroute("**/api/videos/_/")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUnreachableHLSManifest:
    """Test suite for verifying player error handling with unreachable HLS manifest."""

    @pytest.mark.xfail(
        reason="Feature not yet implemented: VideoPlayer does not initialize or display error alert "
               "when HLS manifest URL is unreachable. Expected behavior per MYTUBE-246 spec: "
               "player should initialize even when manifest fails, and display error alert to user."
    )
    def test_video_player_displays_error_on_unreachable_manifest(
        self, web_config: WebConfig, mocked_watch_page: WatchPage
    ):
        """
        Verify that the Video.js player displays an error overlay when the HLS
        manifest URL is unreachable.

        This test navigates to the placeholder watch page (/v/_/) with mocked
        API responses. The mocked video has an unreachable manifest URL, which
        should cause the player to display an error.

        Steps:
        1. Navigate to the placeholder watch page with mocked video data.
        2. Wait for the page to load and the player to initialize.
        3. Verify the player container is visible.
        4. Verify the Video.js player has initialized.
        5. Verify an error is displayed (error alert visible and message present).
        """
        watch_page = mocked_watch_page

        # Step 1: Navigate to the placeholder watch page
        # The static export only pre-generates /v/_/, use this with mocked data
        watch_page.navigate_to_video(web_config.base_url, _PLACEHOLDER_VIDEO_ID)

        # Step 2: Wait for metadata to load (page fully loaded)
        try:
            watch_page.wait_for_metadata(timeout=_PAGE_LOAD_TIMEOUT)
        except Exception:
            # Metadata loading may fail if player fails early, which is expected
            # when the manifest is unreachable
            pass

        # Step 3: Verify the player container is visible
        assert watch_page.is_player_container_visible(), (
            "Player container is not visible. "
            "Expected [data-vjs-player] to be present and visible on the page."
        )

        # Step 4: Verify the Video.js player has initialized
        # The player should initialize even if the manifest is unreachable
        assert watch_page.is_player_initialised(), (
            "Video.js player did not initialize. "
            "Expected the player to attach vjs-paused or vjs-playing class to video element."
        )

        # Step 5: Verify an error is displayed
        # The player should show a visible error because the manifest is unreachable
        assert watch_page.is_error_displayed(), (
            "Player did not display an error. "
            "Expected an error alert [role='alert'] to be visible when manifest is unreachable."
        )

        # Get the error message text for additional verification
        error_message = watch_page.get_error_message()
        assert error_message, (
            "Error alert is visible but contains no text. "
            "Expected a descriptive error message in the alert."
        )

        # The error message should indicate a media or network error
        # (exact message depends on player configuration, but should be user-friendly)
        assert "error" in error_message.lower() or "failed" in error_message.lower() or "network" in error_message.lower(), (
            f"Error message does not indicate a media/network error. Got: {error_message!r}"
        )
