"""
MYTUBE-281: Navigate to watch page via homepage card — basePath is preserved and
player UI initializes.

Objective:
    Verify that client-side navigation from the homepage to a video watch page
    correctly preserves the application's basePath (e.g. /mytube) and that the
    Video.js player UI components are fully initialized after navigation.

Preconditions:
    - Application is deployed to an environment with a sub-path
      (e.g., GitHub Pages at https://ai-teammate.github.io/mytube).
    - At least one video with 'ready' status is available on the homepage.

Test steps:
    1. Navigate to the application homepage.
    2. Assert that at least one video card is visible.
    3. Click the title link of the first video card.
    4. Assert that the resulting URL contains the basePath and matches
       the pattern <basePath>/v/<uuid>.
    5. Assert that the [data-vjs-player] container is present in the DOM.
    6. Assert that .vjs-control-bar is visible.
    7. Assert that .vjs-big-play-button is visible.
    8. Assert that an <h1> element is present and its text matches the
       title that was clicked on the homepage.
    9. Assert that the homepage grid sections are no longer rendered.

Environment variables:
    APP_URL / WEB_BASE_URL  : Base URL of the deployed web app.
                              Default: https://ai-teammate.github.io/mytube
    PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
    PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture:
    - HomePage and WatchPage (Page Objects) from testing/components/pages/.
    - WebConfig from testing/core/config/web_config.py centralises env vars.
    - Playwright sync API with pytest module-scoped fixtures.
    - No hardcoded URLs, selectors, or time.sleep() calls.
"""
from __future__ import annotations

import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, expect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.home_page.home_page import HomePage
from testing.components.pages.watch_page.watch_page import WatchPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms — overall page-load timeout
_PLAYER_INIT_TIMEOUT = 20_000 # ms — time to wait for Video.js to initialise


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
    """Open a single browser context / page reused across all tests in the module."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def home_page(page: Page) -> HomePage:
    return HomePage(page)


@pytest.fixture(scope="module")
def watch_page(page: Page) -> WatchPage:
    return WatchPage(page)


@pytest.fixture(scope="module")
def navigation_result(
    web_config: WebConfig,
    home_page: HomePage,
    watch_page: WatchPage,
):
    """
    Shared fixture: navigate homepage → click first card → arrive at watch page.

    Returns a dict with:
        clicked_title   : str   – video title text clicked on the homepage
        watch_url       : str   – browser URL after navigation
        base_url        : str   – the configured application base URL
    """
    home_page.navigate(web_config.base_url)

    assert home_page.has_video_cards(), (
        "No video cards found on the homepage. "
        "Ensure at least one video with 'ready' status is deployed."
    )

    clicked_title = home_page.click_first_video_card_title()

    # Wait until we're on a /v/ path (client-side navigation)
    home_page._page.wait_for_url(re.compile(r"/v/[^/]+"), timeout=_PAGE_LOAD_TIMEOUT)

    # Wait for loading indicator to disappear and h1 to appear
    watch_page.wait_for_metadata(timeout=_PAGE_LOAD_TIMEOUT)

    return {
        "clicked_title": clicked_title,
        "watch_url": watch_page.get_current_url(),
        "base_url": web_config.base_url,
    }


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestWatchPageNavigationFromHomepage:
    """MYTUBE-281: Client-side navigation preserves basePath and player initializes."""

    def test_url_contains_base_path(self, navigation_result: dict):
        """Step 3-4: URL after click must contain the basePath and /v/<uuid>."""
        watch_url = navigation_result["watch_url"]
        base_url = navigation_result["base_url"]

        # Extract the path component of the basePath (e.g. /mytube from https://…/mytube)
        base_path = base_url.rstrip("/")
        # We allow the base_url to be a root (no path) deployment as well.
        # The critical check is that /v/ is present and is preceded by the base path.
        expected_pattern = re.compile(r"/v/[0-9a-f-]{36}", re.IGNORECASE)
        assert expected_pattern.search(watch_url), (
            f"URL '{watch_url}' does not contain a /v/<uuid> segment. "
            "The application may have navigated to the wrong page or the basePath "
            "was stripped from the URL during client-side routing."
        )

        # Verify the basePath is preserved in the URL
        if base_path:
            # Extract path from base_url for checking
            from urllib.parse import urlparse
            parsed = urlparse(base_path)
            base_path_only = parsed.path.rstrip("/")
            if base_path_only:  # non-root deployment (e.g. /mytube)
                assert base_path_only in watch_url, (
                    f"basePath '{base_path_only}' is missing from the watch URL '{watch_url}'. "
                    "Client-side navigation lost the basePath — the router is not "
                    "honouring the configured Next.js basePath."
                )

    def test_vjs_player_container_present(self, navigation_result: dict, watch_page: WatchPage):
        """Step 4: [data-vjs-player] wrapper must be present in the DOM."""
        assert watch_page.is_player_container_visible(), (
            "[data-vjs-player] container is not visible on the watch page. "
            "The Video.js player wrapper was not rendered after navigation from "
            "the homepage — this could indicate the watch page component failed "
            "to mount or the video data was not fetched."
        )

    def test_vjs_control_bar_visible(self, navigation_result: dict, watch_page: WatchPage):
        """Step 5a: .vjs-control-bar must be visible after player initialisation."""
        # Wait for Video.js to fully initialise before asserting
        watch_page._page.wait_for_selector(
            ".vjs-control-bar",
            state="visible",
            timeout=_PLAYER_INIT_TIMEOUT,
        )
        assert watch_page.is_controls_visible(), (
            ".vjs-control-bar is not visible. "
            "The Video.js player control bar did not render — the player may "
            "have failed to initialise or the CSS is not loading correctly."
        )

    def test_vjs_big_play_button_visible(self, navigation_result: dict, watch_page: WatchPage):
        """Step 5b: .vjs-big-play-button must be visible (player ready, paused state)."""
        watch_page._page.wait_for_selector(
            ".vjs-big-play-button",
            state="visible",
            timeout=_PLAYER_INIT_TIMEOUT,
        )
        assert watch_page.is_big_play_button_visible(), (
            ".vjs-big-play-button is not visible. "
            "The Video.js big-play-button overlay did not appear — the player "
            "may not have reached the 'ready' state."
        )

    def test_video_title_in_h1(self, navigation_result: dict, watch_page: WatchPage):
        """Step 6: An <h1> element must be present and display the video title."""
        h1_title = watch_page.get_video_title()
        assert h1_title is not None, (
            "No <h1> element found on the watch page. "
            "The video title heading was not rendered."
        )
        assert h1_title.strip(), (
            "<h1> element is present but its text is empty. "
            "The video title was not loaded into the heading."
        )

        clicked = navigation_result["clicked_title"]
        assert h1_title.strip() == clicked, (
            f"<h1> title '{h1_title.strip()}' does not match the clicked card "
            f"title '{clicked}'. "
            "The watch page is showing a different video than was clicked, or "
            "the title data was not fetched correctly."
        )

    def test_homepage_grid_not_rendered(self, navigation_result: dict, watch_page: WatchPage):
        """Step 9: After navigation, the homepage discovery grid must not be visible."""
        recently_uploaded = watch_page._page.locator(
            "section[aria-labelledby='recently-uploaded-heading']"
        )
        most_viewed = watch_page._page.locator(
            "section[aria-labelledby='most-viewed-heading']"
        )
        assert recently_uploaded.count() == 0 or not recently_uploaded.is_visible(), (
            "The 'Recently Uploaded' homepage section is still visible on the watch page. "
            "The client-side router did not unmount the homepage component."
        )
        assert most_viewed.count() == 0 or not most_viewed.is_visible(), (
            "The 'Most Viewed' homepage section is still visible on the watch page. "
            "The client-side router did not unmount the homepage component."
        )
