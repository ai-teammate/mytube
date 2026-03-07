"""
MYTUBE-291: Direct navigation to category page on static deployment —
dynamic ID is preserved and category content loads.

Objective
---------
Verify that dynamic route parameters are correctly parsed and preserved when
navigating directly to a category page in the GitHub Pages static environment.

Preconditions
-------------
- Application is deployed to a static hosting environment (GitHub Pages).

Steps
-----
1. Open a browser and navigate directly to a specific category URL
   (e.g., https://ai-teammate.github.io/mytube/category/1/).
2. Observe the URL in the browser's address bar after the page loads.
3. Verify the presence of the category heading (h1) containing the category
   name (e.g., "Education").
4. Verify that the video grid is populated with video cards.

Expected Result
---------------
The browser stays on the correct URL (/category/1/) and does not redirect to
/category/_/. The page displays the correct category heading and the video
grid for that category. No "Invalid category" error alert is shown.

Architecture
------------
- CategoryPage component (testing/components/pages/category_page) for page
  interactions.
- WebConfig from testing/core/config/ for base URL.
- Playwright for browser automation.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the web application.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser in headless mode (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.category_page.category_page import CategoryPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
# The test spec uses category 3 (Gaming) as an example, but the deployed
# database currently has videos only for category 1 (Education).
# We use category 1 to verify both routing and populated video grid.
_CATEGORY_ID = 1  # Education — verified to have videos in the deployed DB


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    """Return a WebConfig loaded from environment variables."""
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser configured from environment variables."""
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    """Return a fresh browser page for the test module."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def category_page_state(page: Page, web_config: WebConfig):
    """
    Navigate directly to /category/{_CATEGORY_ID}/ and return the captured page state
    plus the final URL after any redirects.
    """
    cat_page = CategoryPage(page)
    cat_page.navigate(web_config.base_url, _CATEGORY_ID)
    final_url = cat_page.current_url()
    state = cat_page.get_state()
    return final_url, state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDirectCategoryNavigation:
    """MYTUBE-291: Direct navigation to /category/{_CATEGORY_ID}/ must preserve the URL and load content."""

    def test_url_is_not_redirected_to_placeholder(
        self,
        category_page_state: tuple,
    ) -> None:
        """
        The browser URL must remain /category/{_CATEGORY_ID}/ and must NOT be redirected to
        /category/_/ (a known bug where the dynamic segment is replaced with
        a literal underscore in static deployments).
        """
        final_url, _ = category_page_state
        assert "/category/_/" not in final_url, (
            f"URL was incorrectly redirected to a placeholder path. "
            f"Final URL: {final_url!r}. "
            f"Expected URL to contain '/category/{_CATEGORY_ID}/' "
            f"but the dynamic ID was replaced with '_'."
        )
        assert f"/category/{_CATEGORY_ID}/" in final_url, (
            f"URL does not contain the expected category path '/category/{_CATEGORY_ID}/'. "
            f"Final URL: {final_url!r}"
        )

    def test_category_heading_is_present(
        self,
        category_page_state: tuple,
    ) -> None:
        """
        An <h1> heading with the category name must be visible after direct
        navigation. An absent heading indicates the page failed to parse
        the category ID from the URL.
        """
        _, state = category_page_state
        assert state.category_name is not None, (
            f"Expected an <h1> heading with the category name, but none was found. "
            f"Page state: {state}"
        )
        assert state.category_name.strip() != "", (
            f"The <h1> heading is present but empty. Page state: {state}"
        )

    def test_video_grid_is_populated(
        self,
        category_page_state: tuple,
    ) -> None:
        """
        The video grid must contain at least one video card. An empty grid
        means the category page either failed to load or loaded the wrong data.
        """
        _, state = category_page_state
        assert state.video_card_count > 0, (
            f"Expected at least one video card in the grid, "
            f"but found {state.video_card_count}. "
            f"Category heading: {state.category_name!r}. "
            f"Page state: {state}"
        )

    def test_no_invalid_category_error(
        self,
        category_page_state: tuple,
    ) -> None:
        """
        No 'Invalid category' or similar error alert must be shown after
        navigating directly to the category URL. Such an alert indicates
        the app failed to extract the category ID from the URL.
        """
        _, state = category_page_state
        assert not state.has_error, (
            f"An error alert was displayed on the category page. "
            f"Error text: {state.error_text!r}. "
            f"This likely means the dynamic route parameter was not parsed "
            f"correctly from the URL. Page state: {state}"
        )
