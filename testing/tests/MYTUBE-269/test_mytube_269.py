"""
MYTUBE-269: Browse category with no assigned videos — empty state message displayed.

Objective
---------
Verify the frontend correctly renders an empty state when a category exists
but contains no videos.

Preconditions
-------------
- A category exists with a valid ID but has no videos assigned to it.
- The backend API is deployed and reachable at API_BASE_URL.
- The web frontend is deployed and reachable at APP_URL / WEB_BASE_URL.

Test Steps
----------
1. Query the API to discover a category with no assigned videos.
2. Navigate to the category page (/category/<id>/) in the browser.
3. Assert the page loads without errors.
4. Assert a user-friendly empty state message is displayed
   (e.g. "No videos in this category yet.").
5. Assert no video grid is present when no videos exist.

Environment Variables
---------------------
API_BASE_URL        Backend API base URL.
                    Default: https://mytube-api-80693608388.us-central1.run.app
APP_URL / WEB_BASE_URL  Frontend base URL.
                    Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO  Slow-motion delay in ms (default: 0).

Architecture
------------
- CategoryBrowseService (API service component) — discovers empty categories via API.
- CategoryPage (Page Object) — encapsulates Playwright interactions.
- APIConfig / WebConfig from testing/core/config/.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.web_config import WebConfig
from testing.components.services.category_browse_service import (
    CategoryBrowseService,
)
from testing.components.pages.category_page.category_page import CategoryPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT_MS = 30_000
_EXPECTED_LIMIT = 20

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def category_service(api_config: APIConfig) -> CategoryBrowseService:
    return CategoryBrowseService(api_config)


@pytest.fixture(scope="module")
def empty_category_id(category_service: CategoryBrowseService) -> int:
    """Discover a category with no assigned videos from the API at runtime."""
    try:
        categories = category_service.get_all_categories()
    except Exception as e:
        pytest.skip(
            f"GET /api/categories failed (API unreachable?): {e}. "
            f"Ensure the API is reachable at API_BASE_URL."
        )

    if not categories:
        pytest.skip(
            "GET /api/categories returned no categories — "
            "ensure the API is reachable at API_BASE_URL and has categories seeded."
        )

    # Find a category with no videos
    empty_found = None
    for cat in categories:
        try:
            result = category_service.get_videos_by_category(category_id=cat.id, limit=1)
            if result.status_code == 200 and len(result.videos) == 0:
                empty_found = cat.id
                break
        except Exception as e:
            # Continue to next category if one request fails
            continue

    if empty_found is not None:
        return empty_found

    # If no empty category found in the existing ones, use a non-existent ID
    # to demonstrate the empty state behavior
    pytest.skip(
        "No category with zero videos found in the test data. "
        "Skipping the empty state test — "
        "ensure at least one category exists with no assigned videos."
    )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    """Open a fresh browser context."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT_MS)
    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEmptyCategoryState:
    """MYTUBE-269: Category with no videos displays user-friendly empty state."""

    def test_empty_category_page_loads_without_error(
        self,
        page: Page,
        web_config: WebConfig,
        empty_category_id: int,
    ) -> None:
        """Navigate to /category/<empty_id>/ and verify no error alert is shown."""
        cat_page = CategoryPage(page)
        cat_page.navigate(web_config.base_url, empty_category_id)

        assert not cat_page.has_error(), (
            f"Expected the empty category page to load without errors, "
            f"but an error was shown: {cat_page.get_error_text()}"
        )

    def test_empty_category_page_shows_heading(
        self,
        page: Page,
        web_config: WebConfig,
        empty_category_id: int,
    ) -> None:
        """Empty category page renders a visible <h1> heading after loading."""
        cat_page = CategoryPage(page)
        cat_page.navigate(web_config.base_url, empty_category_id)

        heading = cat_page.get_category_name()
        assert heading is not None, (
            "Expected an <h1> heading on the empty category page, but none was found."
        )
        assert heading.strip() != "", (
            "Expected the <h1> heading to have non-empty text."
        )

    def test_empty_category_page_is_not_loading(
        self,
        page: Page,
        web_config: WebConfig,
        empty_category_id: int,
    ) -> None:
        """Page must not remain stuck in loading state after navigation."""
        cat_page = CategoryPage(page)
        cat_page.navigate(web_config.base_url, empty_category_id)

        assert not cat_page.is_loading(), (
            "Empty category page appears to still be in loading state — "
            "content did not render within the timeout."
        )

    def test_empty_category_has_no_video_cards(
        self,
        page: Page,
        web_config: WebConfig,
        empty_category_id: int,
    ) -> None:
        """No video card elements are present when the category has no videos."""
        cat_page = CategoryPage(page)
        cat_page.navigate(web_config.base_url, empty_category_id)

        video_count = cat_page.get_video_card_count()
        assert video_count == 0, (
            f"Expected no video cards in an empty category, "
            f"but found {video_count} card(s)."
        )

    def test_empty_category_displays_empty_state_message(
        self,
        page: Page,
        web_config: WebConfig,
        empty_category_id: int,
    ) -> None:
        """The page displays a user-friendly message when no videos are found.

        Per the CategoryPageClient.tsx implementation, the expected message is:
        "No videos in this category yet."
        """
        cat_page = CategoryPage(page)
        cat_page.navigate(web_config.base_url, empty_category_id)

        # Check the page content contains the expected empty state message
        page_content = page.content()
        assert "No videos in this category yet" in page_content or "No videos" in page_content, (
            f"Expected an empty state message such as 'No videos in this category yet', "
            f"but the page content does not contain this text. "
            f"Page content snippet: {page_content[500:1000]}"
        )
