"""
MYTUBE-341: View navigation as unauthenticated user — Upload link is hidden.

Objective
---------
Verify that the Upload link is not visible in the navigation shell when the
user is not logged in.

Preconditions
-------------
User is not authenticated (unauthenticated state).

Steps
-----
1. Load the application homepage.
2. Inspect the primary navigation menu in the header.

Expected Result
---------------
The "Upload" link is not displayed in the navigation links.

Architecture
------------
- Uses Playwright sync API to navigate to the homepage without any
  authentication.
- Uses WebConfig from testing/core/config/web_config.py for environment
  configuration.
- No Page Object needed: the assertion is a single, focused locator check on
  the primary navigation element defined in SiteHeader.tsx
  (<nav aria-label="Primary navigation">).

Environment Variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, expect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# SiteHeader.tsx: <nav aria-label="Primary navigation"> is the desktop nav.
# It is hidden on mobile (className="hidden md:flex …") — force a desktop
# viewport so the element is in the rendered layout.
_VIEWPORT = {"width": 1280, "height": 800}

# Selectors derived from SiteHeader.tsx
_PRIMARY_NAV = "nav[aria-label='Primary navigation']"
_UPLOAD_LINK = f"{_PRIMARY_NAV} a[href*='/upload']"

_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    """Open a fresh browser context with no stored authentication state."""
    context = browser.new_context(viewport=_VIEWPORT)
    pg = context.new_page()
    yield pg
    pg.close()
    context.close()


@pytest.fixture(scope="module")
def homepage(page: Page, web_config: WebConfig) -> Page:
    """Navigate to the homepage and wait for the header to be rendered.

    Returns the same Page object for use in test assertions.
    """
    page.goto(web_config.home_url(), timeout=_PAGE_LOAD_TIMEOUT)
    # Wait for the primary navigation to be attached to the DOM before asserting.
    page.wait_for_selector(_PRIMARY_NAV, state="attached", timeout=_PAGE_LOAD_TIMEOUT)
    return page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadLinkHiddenForUnauthenticatedUser:
    """The Upload link must not be visible in the primary nav for anonymous visitors."""

    def test_primary_navigation_is_present(self, homepage: Page) -> None:
        """The primary navigation element must exist in the DOM."""
        nav = homepage.locator(_PRIMARY_NAV)
        expect(nav).to_be_attached(), (
            "Expected the primary navigation element "
            f"({_PRIMARY_NAV!r}) to be present in the DOM."
        )

    def test_upload_link_not_in_navigation(self, homepage: Page) -> None:
        """No Upload anchor must appear inside the primary navigation.

        SiteHeader.tsx only renders the Upload link when {user && ...} — the
        element must be completely absent from the DOM for unauthenticated
        visitors.
        """
        upload_locator = homepage.locator(_UPLOAD_LINK)
        assert upload_locator.count() == 0, (
            f"Expected 0 Upload links inside the primary navigation, "
            f"but found {upload_locator.count()}. "
            "This means the Upload link is visible to unauthenticated users, "
            "which violates the auth-gated nav requirement."
        )

    def test_home_link_is_present(self, homepage: Page) -> None:
        """The 'Home' link must still be visible in the primary nav (sanity check).

        This confirms the navigation rendered correctly for unauthenticated
        users — the absence of Upload is intentional, not a rendering failure.
        """
        home_link = homepage.locator(f"{_PRIMARY_NAV} a[href='/']")
        # Also accept href ending with '/' in case base-path is included
        if home_link.count() == 0:
            home_link = homepage.locator(f"{_PRIMARY_NAV} a").filter(has_text="Home")
        assert home_link.count() > 0, (
            "Expected a 'Home' link inside the primary navigation for "
            "unauthenticated users, but found none. The navigation may not "
            "have rendered at all — check that the page loaded correctly."
        )
