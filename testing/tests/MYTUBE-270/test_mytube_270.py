"""
MYTUBE-270: Category page with API failure — error message displayed to user.

Objective
---------
Verify that the UI handles API communication failures gracefully on the
category browse page.

Preconditions
-------------
- A valid category ID exists in the API
- The web application is deployed and accessible

Steps
-----
1. Intercept/mock the API call to /api/videos?category_id=[ID] to return
   a 500 Internal Server Error.
2. Navigate to /category/[ID] in the browser.

Expected Result
---------------
The UI displays a clear error notification or alert informing the user
that the video content could not be retrieved, rather than showing a
broken layout or empty screen.

Test Approach
-------------
This test uses Playwright's route interception to mock the videos API endpoint
with a 500 error, then navigates to a category page and verifies that:
1. An error alert/notification is visible
2. The error text indicates a loading or retrieval failure
3. The page is not in a broken or empty state

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the web application.
                         Default: https://ai-teammate.github.io/mytube
API_BASE_URL             Backend API base URL (used to determine mock endpoint).
                         Default: http://localhost:8081
PLAYWRIGHT_HEADLESS      Run browser in headless mode (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, Route

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.api_config import APIConfig
from testing.components.pages.category_page.category_page import CategoryPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_CATEGORY_ID_FOR_TEST = 1  # Use a common category ID


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
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless, slow_mo=web_config.slow_mo
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def category_id() -> int:
    """Return the default category ID for testing.
    
    In a live environment, this would be fetched from the API.
    For isolated testing, we use a fixed category ID.
    """
    return _CATEGORY_ID_FOR_TEST


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCategoryPageApiFailure:
    """MYTUBE-270: Category page handles API failures gracefully."""

    def test_category_page_displays_error_on_api_500(
        self,
        page: Page,
        web_config: WebConfig,
        api_config: APIConfig,
        category_id: int,
    ) -> None:
        """
        When the videos API returns a 500 error, the category page should
        display a clear error message instead of a broken or empty layout.
        
        Test steps:
        1. Set up route interception to mock /api/videos?category_id=[ID]
           as returning HTTP 500.
        2. Navigate to /category/[ID].
        3. Verify that:
           - An error alert/notification is visible
           - The error text indicates a problem retrieving content
           - The page is not empty or broken
        """
        api_base = api_config.base_url.rstrip("/")
        
        # Track whether the mocked route was intercepted
        route_called = []
        
        def handle_videos_request(route: Route) -> None:
            """Intercept /api/videos requests and respond with 500."""
            route_called.append(True)
            route.abort(error_code="failed")
        
        # Set up route interception for the videos API endpoint
        # Match both with and without query parameters
        page.route(
            f"{api_base}/api/videos**",
            handle_videos_request,
        )
        
        # Also try a more generic pattern to catch all videos requests
        page.route(
            "**/api/videos**",
            handle_videos_request,
        )
        
        try:
            # Navigate to the category page
            category_page = CategoryPage(page)
            category_page.navigate(web_config.base_url, category_id)
            
            # Capture the page state
            state = category_page.get_state()
            
            # Assert: An error is displayed
            assert (
                state.has_error
            ), f"Expected an error alert to be visible, but none was found. Page state: {state}"
            
            # Assert: Error text is not empty and contains meaningful message
            assert (
                state.error_text
            ), f"Error alert is visible but has no text. Page state: {state}"
            
            # Assert: Error text indicates a problem (not just empty)
            error_text_lower = state.error_text.lower()
            expected_keywords = [
                "error",
                "failed",
                "could not",
                "unable",
                "problem",
                "unable to load",
                "retrieve",
            ]
            
            has_error_keyword = any(
                keyword in error_text_lower for keyword in expected_keywords
            )
            assert (
                has_error_keyword
            ), (
                f"Error text does not indicate a failure. "
                f"Got: '{state.error_text}'. "
                f"Expected error text to contain at least one of: {expected_keywords}"
            )
            
            # Assert: Page is not showing a normal successful state
            # (if it has an error, it should NOT have video cards)
            assert (
                state.video_card_count == 0
            ), (
                f"Page shows both error AND video cards, which is inconsistent. "
                f"Error: '{state.error_text}', Video cards: {state.video_card_count}"
            )
            
        finally:
            # Clean up routes
            page.unroute("**/api/videos**")
