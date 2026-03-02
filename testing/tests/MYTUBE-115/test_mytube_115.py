"""
MYTUBE-115: View public user profile — page displays user info and ready videos.

Verifies that a visitor can navigate to /u/tester and see:
  - The user's avatar (image or initials fallback).
  - The username "tester" in the page heading.
  - A grid of video thumbnails each linking to /v/<id>.

Preconditions
-------------
- A user with username "tester" exists and has at least one video with "ready" status.
- The web application is deployed and reachable at WEB_BASE_URL.

Test steps
----------
1. Navigate to /u/tester.
2. Wait for the page to finish loading.
3. Assert the avatar element is visible.
4. Assert the <h1> heading shows "tester".
5. Assert at least one video card is visible.
6. Assert every video card href matches the /v/<id> pattern.

Environment variables
---------------------
WEB_BASE_URL        : Base URL of the deployed web app.
                      Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO  : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses ProfilePage (Page Object) from testing/components/pages/profile_page/.
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
from testing.components.pages.profile_page.profile_page import ProfilePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEST_USERNAME = "tester"
_PAGE_LOAD_TIMEOUT = 30_000  # ms


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
def profile_page(page: Page) -> ProfilePage:
    return ProfilePage(page)


@pytest.fixture(scope="module")
def loaded_profile(web_config: WebConfig, profile_page: ProfilePage):
    """
    Navigate to the user profile page once; all tests in this module reuse
    the resulting page state.
    """
    profile_page.navigate(web_config.base_url, _TEST_USERNAME)
    yield profile_page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPublicUserProfile:
    """MYTUBE-115: View public user profile — page displays user info and ready videos."""

    def test_avatar_is_visible(self, loaded_profile: ProfilePage):
        """The user's avatar (image or initials fallback) must be visible."""
        assert loaded_profile.is_avatar_visible(), (
            "Expected the user's avatar to be visible on the profile page, "
            "but no avatar element was found or visible."
        )

    def test_username_heading_displays_tester(self, loaded_profile: ProfilePage):
        """The <h1> heading must display the username 'tester'."""
        heading = loaded_profile.get_username_heading()
        assert heading == _TEST_USERNAME, (
            f"Expected the username heading to be '{_TEST_USERNAME}', "
            f"but got '{heading}'."
        )

    def test_video_grid_has_at_least_one_card(self, loaded_profile: ProfilePage):
        """At least one video card must be visible in the grid."""
        count = loaded_profile.get_video_card_count()
        assert count >= 1, (
            f"Expected at least one video card on the profile page, "
            f"but found {count}."
        )

    def test_video_cards_link_to_video_pages(self, loaded_profile: ProfilePage):
        """Every video card href must match the /v/<id> pattern."""
        assert loaded_profile.all_video_hrefs_match_pattern(), (
            "Expected all video card links to match the /v/<id> pattern, "
            f"but some did not. Found hrefs: {loaded_profile.get_video_hrefs()}"
        )
