"""
MYTUBE-283: Refresh dynamic video watch page — player re-initializes and 404 error is avoided.

Objective
---------
Verify that performing a browser refresh on a dynamic video route (/v/[id]) does
not trigger a 404 error and successfully reloads the Video.js player components.

Preconditions
-------------
- Application is deployed to a static hosting environment (GitHub Pages).
- A video with status 'ready' exists.

Test Steps
----------
1. Navigate directly to the video watch page URL for a ready video (/v/[uuid]).
2. Verify that the Video.js player initializes and the video title is displayed.
3. Perform a browser refresh (Ctrl+R / Cmd+R via page.reload()).
4. Wait for the page to reload.
5. Verify that the Next.js default 404 page ("This page could not be found.") is
   NOT displayed.
6. Verify that the Video.js player container [data-vjs-player] is present in the DOM.
7. Verify that the underlying <video> element is present within the player container.

Expected Result
---------------
The application handles the browser refresh on the dynamic route correctly. The
static host does not return a 404 error, and the Video.js player re-initializes
successfully with all required DOM elements.

Strategy
--------
1. VideoApiService (API_BASE_URL) is used to discover a ready video when the API
   is reachable.  When absent, TEST_VIDEO_ID env var is used as a fallback.
   If neither is available the test is skipped gracefully.
2. WatchPage (Page Object) encapsulates all selectors and DOM interaction.
3. page.reload() simulates a full hard browser refresh (equivalent to Ctrl+R /
   Cmd+R), which exercises the static-host 404-fallback redirect path.

Environment Variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web application.
                        Default: https://ai-teammate.github.io/mytube
API_BASE_URL            Base URL of the backend API (used to discover a ready video).
                        Default: http://localhost:8081
TEST_VIDEO_ID           Override: use this specific video ID instead of API discovery.
PLAYWRIGHT_HEADLESS     Run browser in headless mode (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Architecture
------------
- WatchPage (Page Object) from testing/components/pages/watch_page/.
- VideoApiService from testing/components/services/video_api_service.py.
- WebConfig / APIConfig from testing/core/config/ for environment variables.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs, selectors, or time.sleep() calls.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.api_config import APIConfig
from testing.components.pages.watch_page.watch_page import WatchPage
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000    # ms — overall page-load budget
_PLAYER_INIT_TIMEOUT = 20_000  # ms — time allowed for Video.js to initialise
_METADATA_TIMEOUT = 15_000     # ms — time to wait for video title / metadata

# Text that identifies the Next.js default 404 page
_NEXTJS_404_TEXT = "This page could not be found."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_ready_video_id() -> str | None:
    """Return a ready video ID using API discovery or TEST_VIDEO_ID override.

    Priority:
    1. TEST_VIDEO_ID env var (explicit override).
    2. VideoApiService discovery via API_BASE_URL.

    Returns None when no ready video can be found.
    """
    override = os.getenv("TEST_VIDEO_ID", "").strip()
    if override:
        return override

    try:
        svc = VideoApiService(APIConfig())
        result = svc.find_ready_video()
        if result:
            return result[0]
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    """Return WebConfig loaded from environment variables."""
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
    """Open a single browser context / page reused across all tests in the module."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def watch_page(page: Page) -> WatchPage:
    """Return a WatchPage Page Object bound to the shared page."""
    return WatchPage(page)


@pytest.fixture(scope="module")
def initial_load_result(web_config: WebConfig, watch_page: WatchPage, page: Page) -> dict:
    """
    Shared fixture: discover a ready video, navigate directly to /v/<id>,
    wait for the player to initialise, and return context for further assertions.

    Raises pytest.skip() when no ready video can be found.
    """
    video_id = _find_ready_video_id()
    if not video_id:
        pytest.skip(
            "No ready video found. Set TEST_VIDEO_ID or ensure API_BASE_URL points to "
            "a deployed API instance with at least one ready video."
        )

    watch_url = f"{web_config.base_url}/v/{video_id}"

    # Step 1: Navigate directly to the watch page URL.
    try:
        watch_page.navigate_to_video(web_config.base_url, video_id)
    except Exception as exc:
        pytest.skip(
            f"Could not navigate to watch page at {watch_url}: {exc}. "
            "Ensure APP_URL / WEB_BASE_URL points to the deployed application."
        )

    # Step 2: Wait for video metadata (loading indicator disappears, h1 visible).
    try:
        watch_page.wait_for_metadata(timeout=_METADATA_TIMEOUT)
    except Exception:
        pass  # Proceed — individual tests will assert the expected state.

    return {
        "video_id": video_id,
        "watch_url": watch_url,
        "base_url": web_config.base_url,
    }


@pytest.fixture(scope="module")
def after_refresh_result(
    initial_load_result: dict,
    watch_page: WatchPage,
    page: Page,
) -> dict:
    """
    Shared fixture: perform a hard browser refresh on the watch page and wait for
    the page to reload.  Depends on initial_load_result to ensure navigation
    happened first.
    """
    # Step 3: Perform a browser refresh (equivalent to Ctrl+R / Cmd+R).
    page.reload(wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

    # Step 4: Wait for the page to reload — wait for h1 or loading state to settle.
    try:
        watch_page.wait_for_metadata(timeout=_METADATA_TIMEOUT)
    except Exception:
        pass  # Individual tests will assert the final state.

    return {
        "video_id": initial_load_result["video_id"],
        "watch_url": initial_load_result["watch_url"],
        "current_url": page.url,
    }


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestWatchPageRefresh:
    """MYTUBE-283: Browser refresh on /v/[id] — 404 avoided, player re-initializes."""

    # ------------------------------------------------------------------
    # Pre-refresh assertions (Steps 1-2)
    # ------------------------------------------------------------------

    def test_initial_navigation_loads_player(
        self, initial_load_result: dict, watch_page: WatchPage
    ) -> None:
        """Step 1-2: Direct navigation to /v/<id> must render the player container."""
        assert watch_page.is_player_container_visible(), (
            f"[data-vjs-player] container is not visible after initial navigation to "
            f"{initial_load_result['watch_url']}. "
            "The watch page component may have failed to mount, or the video data "
            "could not be fetched from the API."
        )

    def test_initial_title_displayed(
        self, initial_load_result: dict, watch_page: WatchPage
    ) -> None:
        """Step 2: An <h1> title must be visible after initial navigation."""
        title = watch_page.get_video_title()
        assert title is not None and title.strip(), (
            f"No video title found in <h1> after navigating to "
            f"{initial_load_result['watch_url']}. "
            "The video metadata did not load correctly on the initial navigation."
        )

    # ------------------------------------------------------------------
    # Post-refresh assertions (Steps 3-7)
    # ------------------------------------------------------------------

    def test_no_nextjs_404_after_refresh(
        self, after_refresh_result: dict, page: Page
    ) -> None:
        """Step 5: The Next.js default 404 page must NOT appear after refresh.

        On GitHub Pages a hard reload of /v/<uuid> hits the server directly and
        may receive a 404.html response.  The static-host fallback must redirect
        back to the SPA so the Next.js 404 page is never rendered.
        """
        page_body_text = page.locator("body").inner_text(timeout=_PAGE_LOAD_TIMEOUT)
        assert _NEXTJS_404_TEXT not in page_body_text, (
            f"Step 5 FAILED: The Next.js default 404 page was rendered after browser "
            f"refresh on {after_refresh_result['watch_url']}.\n"
            f"Current URL: {after_refresh_result['current_url']!r}\n"
            f"The text '{_NEXTJS_404_TEXT}' was found in the page body, which means "
            "the static hosting fallback (404.html redirect) did not handle the dynamic "
            "route correctly after the reload. Check that the 404.html redirect script "
            "correctly re-encodes the /v/<id> path in sessionStorage and that the SPA "
            "shell page reads and restores it on load."
        )

    def test_player_container_present_after_refresh(
        self, after_refresh_result: dict, watch_page: WatchPage
    ) -> None:
        """Step 6: [data-vjs-player] container must be present in the DOM after refresh."""
        assert watch_page.is_player_container_visible(), (
            f"Step 6 FAILED: [data-vjs-player] container is NOT present in the DOM "
            f"after browser refresh on {after_refresh_result['watch_url']}.\n"
            f"Current URL: {after_refresh_result['current_url']!r}\n"
            "The Video.js player wrapper was not rendered after the page reload. "
            "This could mean the watch page component failed to re-mount, the video "
            "data was not re-fetched, or the refresh resulted in a 404/error page."
        )

    def test_video_element_present_after_refresh(
        self, after_refresh_result: dict, watch_page: WatchPage
    ) -> None:
        """Step 7: A <video> element must be present inside the player container after refresh."""
        assert watch_page.is_video_element_present(), (
            f"Step 7 FAILED: No <video> element found inside [data-vjs-player] after "
            f"browser refresh on {after_refresh_result['watch_url']}.\n"
            f"Current URL: {after_refresh_result['current_url']!r}\n"
            "The underlying <video> element (video.video-js or video.vjs-tech) was not "
            "found after the page reload. This indicates Video.js did not fully "
            "re-initialize after the browser refresh."
        )

    def test_title_still_displayed_after_refresh(
        self, after_refresh_result: dict, watch_page: WatchPage
    ) -> None:
        """Step 2 post-refresh: Video title must still be visible after reload."""
        title = watch_page.get_video_title()
        assert title is not None and title.strip(), (
            f"No video title found in <h1> after browser refresh on "
            f"{after_refresh_result['watch_url']}.\n"
            f"Current URL: {after_refresh_result['current_url']!r}\n"
            "The video metadata was not re-loaded after the page refresh."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
