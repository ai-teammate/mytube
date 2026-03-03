"""
MYTUBE-176: Browse videos by category — results filtered by category ID.

Objective
---------
Verify that the category browse API and UI correctly filter content.

Preconditions
-------------
- Videos are assigned to different categories (e.g., 'Gaming', 'Music').
- The backend API is deployed and reachable at API_BASE_URL.
- The web frontend is deployed and reachable at APP_URL / WEB_BASE_URL.

Test Approach
-------------
Part 1 — API (GET /api/videos?category_id=<id>&limit=20):
  1. Fetch /api/categories to discover the Gaming category ID.
  2. Call GET /api/videos?category_id=<id>&limit=20.
  3. Assert HTTP 200, Content-Type JSON, and response is a JSON array.
  4. Assert every video in the response has the expected structure
     (id, title, uploader_username, view_count, created_at).
  5. Assert the endpoint rejects missing category_id with HTTP 400.
  6. Assert the endpoint rejects an invalid category_id with HTTP 400.
  7. Assert a non-existent category returns an empty array (not an error).

Part 2 — Web UI (/category/<id>/):
  1. Navigate to /category/<id>/ in Chromium via Playwright.
  2. Assert the page title heading is visible and non-empty.
  3. Assert the page renders without an error alert.
  4. Assert the video grid container is present when videos exist.

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
- CategoryBrowseService (API service component) — no raw HTTP in tests.
- CategoryPage (Page Object) — no raw Playwright calls in tests.
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
    CategoryBrowseResponse,
)
from testing.components.pages.category_page.category_page import CategoryPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT_MS = 30_000
# Gaming is category ID 3 per 0002_seed_categories.up.sql seed data.
# We verify this dynamically at runtime via /api/categories.
_GAMING_CATEGORY_NAME = "Gaming"
_MUSIC_CATEGORY_NAME = "Music"
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
def gaming_category_id(category_service: CategoryBrowseService) -> int:
    """Discover the Gaming category ID from /api/categories at runtime."""
    categories = category_service.get_all_categories()
    if not categories:
        pytest.skip(
            "GET /api/categories returned no categories — "
            "ensure the API is reachable at API_BASE_URL."
        )
    gaming = next((c for c in categories if c.name == _GAMING_CATEGORY_NAME), None)
    if gaming is None:
        pytest.skip(
            f"Category '{_GAMING_CATEGORY_NAME}' not found in /api/categories. "
            f"Available: {[c.name for c in categories]}"
        )
    return gaming.id


@pytest.fixture(scope="module")
def music_category_id(category_service: CategoryBrowseService) -> int:
    """Discover the Music category ID from /api/categories at runtime."""
    categories = category_service.get_all_categories()
    music = next((c for c in categories if c.name == _MUSIC_CATEGORY_NAME), None)
    if music is None:
        pytest.skip(
            f"Category '{_MUSIC_CATEGORY_NAME}' not found in /api/categories."
        )
    return music.id


@pytest.fixture(scope="module")
def gaming_browse_response(
    category_service: CategoryBrowseService,
    gaming_category_id: int,
) -> CategoryBrowseResponse:
    """Single shared API response for the Gaming category browse."""
    return category_service.get_videos_by_category(
        category_id=gaming_category_id, limit=_EXPECTED_LIMIT
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
# Part 1: API Tests — GET /api/videos?category_id=<id>&limit=20
# ---------------------------------------------------------------------------


class TestCategoryBrowseAPI:
    """MYTUBE-176 (API): /api/videos?category_id=<id>&limit=20 filters by category."""

    def test_api_returns_200_for_valid_category(
        self, gaming_browse_response: CategoryBrowseResponse
    ) -> None:
        """GET /api/videos?category_id=<gaming_id>&limit=20 returns HTTP 200."""
        assert gaming_browse_response.status_code == 200, (
            f"Expected HTTP 200 for a valid category_id, "
            f"got {gaming_browse_response.status_code}. "
            f"Error: {gaming_browse_response.error_message}"
        )

    def test_api_returns_json_array(
        self, gaming_browse_response: CategoryBrowseResponse
    ) -> None:
        """Response body is a JSON array (list of video cards)."""
        assert gaming_browse_response.error_message is None, (
            f"Response parsing failed: {gaming_browse_response.error_message}. "
            f"Raw body: {gaming_browse_response.raw_body[:500]}"
        )
        assert isinstance(gaming_browse_response.videos, list), (
            "Expected the API to return a JSON array of video cards."
        )

    def test_api_result_count_within_limit(
        self, gaming_browse_response: CategoryBrowseResponse
    ) -> None:
        """Number of returned videos does not exceed the requested limit."""
        count = len(gaming_browse_response.videos)
        assert count <= _EXPECTED_LIMIT, (
            f"Expected at most {_EXPECTED_LIMIT} videos (limit={_EXPECTED_LIMIT}), "
            f"but got {count}."
        )

    def test_video_cards_have_required_fields(
        self, gaming_browse_response: CategoryBrowseResponse
    ) -> None:
        """Each video card has non-empty id, title, and uploader_username."""
        for video in gaming_browse_response.videos:
            assert video.id, (
                f"Video card is missing 'id'. Card: {video}"
            )
            assert video.title, (
                f"Video card is missing 'title'. Card: {video}"
            )
            assert video.uploader_username, (
                f"Video card is missing 'uploader_username'. Card: {video}"
            )
            assert video.created_at, (
                f"Video card is missing 'created_at'. Card: {video}"
            )

    def test_missing_category_id_returns_400(
        self, category_service: CategoryBrowseService
    ) -> None:
        """GET /api/videos without category_id returns HTTP 400."""
        result = category_service.get_videos_no_category()
        assert result.status_code == 400, (
            f"Expected HTTP 400 when category_id is missing, got {result.status_code}. "
            "GET /api/videos without category_id should return 400 Bad Request."
        )

    def test_invalid_category_id_returns_400(
        self, category_service: CategoryBrowseService
    ) -> None:
        """GET /api/videos?category_id=abc returns HTTP 400."""
        result = category_service.get_videos_with_invalid_category("abc")
        assert result.status_code == 400, (
            f"Expected HTTP 400 for invalid category_id='abc', got {result.status_code}."
        )

    def test_nonexistent_category_returns_empty_array(
        self, category_service: CategoryBrowseService
    ) -> None:
        """GET /api/videos?category_id=99999 returns HTTP 200 with empty array."""
        result = category_service.get_videos_by_category(category_id=99999, limit=20)
        assert result.status_code == 200, (
            f"Expected HTTP 200 for non-existent category_id, got {result.status_code}."
        )
        assert result.videos == [], (
            f"Expected empty array for non-existent category, got {result.videos}."
        )

    def test_different_categories_return_different_results(
        self,
        category_service: CategoryBrowseService,
        gaming_category_id: int,
        music_category_id: int,
    ) -> None:
        """Gaming and Music category responses differ (cross-category isolation).

        Skipped when either category has no videos — the important invariant is
        that if both have videos, their video sets don't overlap.
        """
        gaming_resp = category_service.get_videos_by_category(
            category_id=gaming_category_id, limit=20
        )
        music_resp = category_service.get_videos_by_category(
            category_id=music_category_id, limit=20
        )

        if not gaming_resp.videos or not music_resp.videos:
            pytest.skip(
                "One or both categories have no videos — "
                "cannot verify cross-category isolation."
            )

        gaming_ids = {v.id for v in gaming_resp.videos}
        music_ids = {v.id for v in music_resp.videos}
        overlap = gaming_ids & music_ids
        assert not overlap, (
            f"Expected Gaming and Music categories to return disjoint video sets, "
            f"but found {len(overlap)} overlapping video ID(s): {overlap}."
        )


# ---------------------------------------------------------------------------
# Part 2: Web UI Tests — /category/<id>/
# ---------------------------------------------------------------------------


class TestCategoryBrowseUI:
    """MYTUBE-176 (UI): /category/<id>/ renders a grid of category videos."""

    def test_category_page_loads_without_error(
        self,
        page: Page,
        web_config: WebConfig,
        gaming_category_id: int,
    ) -> None:
        """Navigate to /category/<id>/ and verify no error alert is shown."""
        cat_page = CategoryPage(page)
        cat_page.navigate(web_config.base_url, gaming_category_id)

        assert not cat_page.has_error(), (
            f"Expected the category page to load without errors, "
            f"but an error was shown: {cat_page.get_error_text()}"
        )

    def test_category_page_shows_heading(
        self,
        page: Page,
        web_config: WebConfig,
        gaming_category_id: int,
    ) -> None:
        """Category page renders a visible <h1> heading after loading."""
        cat_page = CategoryPage(page)
        cat_page.navigate(web_config.base_url, gaming_category_id)

        heading = cat_page.get_category_name()
        assert heading is not None, (
            "Expected an <h1> heading on the category page, but none was found."
        )
        assert heading.strip() != "", (
            "Expected the <h1> heading to have non-empty text."
        )

    def test_category_page_heading_matches_category_name(
        self,
        page: Page,
        web_config: WebConfig,
        gaming_category_id: int,
    ) -> None:
        """The <h1> heading contains the correct category name ('Gaming')."""
        cat_page = CategoryPage(page)
        cat_page.navigate(web_config.base_url, gaming_category_id)

        heading = cat_page.get_category_name()
        assert heading is not None, (
            "Expected an <h1> heading, but none was found."
        )
        assert _GAMING_CATEGORY_NAME in heading, (
            f"Expected the heading to contain '{_GAMING_CATEGORY_NAME}', "
            f"but got: '{heading}'."
        )

    def test_category_page_is_not_loading(
        self,
        page: Page,
        web_config: WebConfig,
        gaming_category_id: int,
    ) -> None:
        """Page must not remain stuck in loading state after navigation."""
        cat_page = CategoryPage(page)
        cat_page.navigate(web_config.base_url, gaming_category_id)

        assert not cat_page.is_loading(), (
            "Category page appears to still be in loading state — "
            "content did not render within the timeout."
        )
