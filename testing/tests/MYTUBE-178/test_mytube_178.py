"""
MYTUBE-178: Homepage discovery sections — Recently Uploaded and Most Viewed displayed.

Verifies that the homepage correctly displays two discovery sections with video card
components, each containing up to 20 cards. Each card must show a thumbnail link,
title, uploader username, and view count.

Preconditions
-------------
- At least one video with "ready" status must exist in the deployed application.
- The web application is deployed and reachable at WEB_BASE_URL.

Test steps
----------
1. Navigate to the homepage (/).
2. Wait for the page to finish loading (loading indicator disappears).
3. Assert the "Recently Uploaded" section is visible.
4. Assert the "Most Viewed" section is visible.
5. Assert each section contains at least 1 and no more than 20 video cards.
6. For each card in both sections, assert:
   a. A thumbnail element (link with aria-label) is present.
   b. A title link pointing to /v/<id> is present.
   c. An uploader username link pointing to /u/<username> is present.
   d. A view count text is present.

Environment variables
---------------------
WEB_BASE_URL        : Base URL of the deployed web app.
                      Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO  : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses HomePage (Page Object) from testing/components/pages/home_page/.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest fixtures (module-scoped browser, fresh page).
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.home_page.home_page import HomePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_MAX_CARDS_PER_SECTION = 20


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
def home_page(page: Page) -> HomePage:
    return HomePage(page)


@pytest.fixture(scope="module")
def loaded_home(web_config: WebConfig, home_page: HomePage):
    """
    Navigate to the homepage once; all tests in this module reuse
    the resulting page state.
    """
    home_page.navigate(web_config.base_url)
    assert not home_page.is_error_displayed(), (
        "Homepage is showing an error — all discovery section tests would be invalid."
    )
    yield home_page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHomepageDiscoverySections:
    """MYTUBE-178: Homepage discovery sections — Recently Uploaded and Most Viewed."""

    def test_recently_uploaded_section_is_visible(self, loaded_home: HomePage):
        """The 'Recently Uploaded' section must be visible on the homepage."""
        loaded_home.assert_recently_uploaded_section_visible()

    def test_most_viewed_section_is_visible(self, loaded_home: HomePage):
        """The 'Most Viewed' section must be visible on the homepage."""
        loaded_home.assert_most_viewed_section_visible()

    def test_recently_uploaded_heading_text(self, loaded_home: HomePage):
        """The 'Recently Uploaded' section heading must show the correct text."""
        heading = loaded_home.get_recently_uploaded_heading()
        assert heading == "Recently Uploaded", (
            f"Expected section heading 'Recently Uploaded', got '{heading}'."
        )

    def test_most_viewed_heading_text(self, loaded_home: HomePage):
        """The 'Most Viewed' section heading must show the correct text."""
        heading = loaded_home.get_most_viewed_heading()
        assert heading == "Most Viewed", (
            f"Expected section heading 'Most Viewed', got '{heading}'."
        )

    def test_recently_uploaded_has_cards(self, loaded_home: HomePage):
        """The 'Recently Uploaded' section must contain at least 1 video card."""
        count = loaded_home.get_recently_uploaded_card_count()
        assert count >= 1, (
            f"Expected at least 1 video card in 'Recently Uploaded', but found {count}."
        )

    def test_recently_uploaded_card_count_at_most_20(self, loaded_home: HomePage):
        """The 'Recently Uploaded' section must not contain more than 20 video cards."""
        count = loaded_home.get_recently_uploaded_card_count()
        assert count <= _MAX_CARDS_PER_SECTION, (
            f"Expected at most {_MAX_CARDS_PER_SECTION} cards in 'Recently Uploaded', "
            f"but found {count}."
        )

    def test_most_viewed_has_cards(self, loaded_home: HomePage):
        """The 'Most Viewed' section must contain at least 1 video card."""
        count = loaded_home.get_most_viewed_card_count()
        assert count >= 1, (
            f"Expected at least 1 video card in 'Most Viewed', but found {count}."
        )

    def test_most_viewed_card_count_at_most_20(self, loaded_home: HomePage):
        """The 'Most Viewed' section must not contain more than 20 video cards."""
        count = loaded_home.get_most_viewed_card_count()
        assert count <= _MAX_CARDS_PER_SECTION, (
            f"Expected at most {_MAX_CARDS_PER_SECTION} cards in 'Most Viewed', "
            f"but found {count}."
        )

    def test_recently_uploaded_cards_link_to_video_pages(self, loaded_home: HomePage):
        """Every video card in 'Recently Uploaded' must link to a /v/<id> URL."""
        assert loaded_home.recently_uploaded_cards_have_valid_hrefs(), (
            "Expected all video cards in 'Recently Uploaded' to link to /v/<id>, "
            "but some hrefs did not match the pattern."
        )

    def test_most_viewed_cards_link_to_video_pages(self, loaded_home: HomePage):
        """Every video card in 'Most Viewed' must link to a /v/<id> URL."""
        assert loaded_home.most_viewed_cards_have_valid_hrefs(), (
            "Expected all video cards in 'Most Viewed' to link to /v/<id>, "
            "but some hrefs did not match the pattern."
        )

    def test_recently_uploaded_cards_have_thumbnail(self, loaded_home: HomePage):
        """Every card in 'Recently Uploaded' must have a thumbnail anchor element."""
        missing = loaded_home.get_section_thumbnail_missing_indexes(
            loaded_home._RECENTLY_UPLOADED_SECTION
        )
        assert not missing, (
            f"Cards at indexes {missing} in 'Recently Uploaded' are missing a thumbnail."
        )

    def test_most_viewed_cards_have_thumbnail(self, loaded_home: HomePage):
        """Every card in 'Most Viewed' must have a thumbnail anchor element."""
        missing = loaded_home.get_section_thumbnail_missing_indexes(
            loaded_home._MOST_VIEWED_SECTION
        )
        assert not missing, (
            f"Cards at indexes {missing} in 'Most Viewed' are missing a thumbnail."
        )

    def test_recently_uploaded_cards_have_uploader_username(self, loaded_home: HomePage):
        """Every video card in 'Recently Uploaded' must display an uploader username."""
        info = loaded_home.get_recently_uploaded_section_info()
        assert info.card_count >= 1, "No cards found in 'Recently Uploaded' section."
        missing = [i for i, u in enumerate(info.card_uploaders) if not u.strip()]
        assert not missing, (
            f"Cards at indexes {missing} in 'Recently Uploaded' are missing an uploader username."
        )

    def test_most_viewed_cards_have_uploader_username(self, loaded_home: HomePage):
        """Every video card in 'Most Viewed' must display an uploader username."""
        info = loaded_home.get_most_viewed_section_info()
        assert info.card_count >= 1, "No cards found in 'Most Viewed' section."
        missing = [i for i, u in enumerate(info.card_uploaders) if not u.strip()]
        assert not missing, (
            f"Cards at indexes {missing} in 'Most Viewed' are missing an uploader username."
        )

    def test_recently_uploaded_cards_have_view_count(self, loaded_home: HomePage):
        """Every video card in 'Recently Uploaded' must display a view count."""
        info = loaded_home.get_recently_uploaded_section_info()
        assert info.card_count >= 1, "No cards found in 'Recently Uploaded' section."
        missing = [i for i, v in enumerate(info.card_view_counts) if not v.strip()]
        assert not missing, (
            f"Cards at indexes {missing} in 'Recently Uploaded' are missing a view count."
        )

    def test_most_viewed_cards_have_view_count(self, loaded_home: HomePage):
        """Every video card in 'Most Viewed' must display a view count."""
        info = loaded_home.get_most_viewed_section_info()
        assert info.card_count >= 1, "No cards found in 'Most Viewed' section."
        missing = [i for i, v in enumerate(info.card_view_counts) if not v.strip()]
        assert not missing, (
            f"Cards at indexes {missing} in 'Most Viewed' are missing a view count."
        )
