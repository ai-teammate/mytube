"""
MYTUBE-344: Verify footer content — site links and copyright present.

Objective
---------
Ensure the global footer contains required legal links and copyright information.

Test Steps
----------
1. Navigate to the homepage (/).
2. Scroll to the bottom of the page (footer).
3. Verify the footer is visible.
4. Verify the "Terms" link is present and points to /terms.
5. Verify the "Privacy" link is present and points to /privacy.
6. Verify the copyright text is present and contains "mytube" and "All rights reserved".

Expected Result
---------------
The footer is visible and contains working links to the Terms and Privacy pages,
along with a standard copyright statement.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web application.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser in headless mode (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms for debugging (default: 0).

Architecture
------------
- Uses FooterComponent (Page Object) from testing/components/pages/footer_component/.
- Uses HomePage (Page Object) from testing/components/pages/home_page/ for navigation.
- WebConfig from testing/core/config/web_config.py centralises all env var access.
- Playwright sync API with pytest fixtures.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.home_page.home_page import HomePage
from testing.components.pages.footer_component.footer_component import FooterComponent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms


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
def footer(page: Page) -> FooterComponent:
    return FooterComponent(page)


@pytest.fixture(scope="module")
def navigated_homepage(web_config: WebConfig, home_page: HomePage, page: Page):
    """Navigate to the homepage once and yield the page for all tests."""
    home_page.navigate(web_config.base_url)
    yield page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFooterContent:
    """MYTUBE-344: Verify footer content — site links and copyright present."""

    def test_footer_is_visible(self, navigated_homepage, footer: FooterComponent) -> None:
        """Step 1-3: The footer element must be visible on the homepage."""
        footer.scroll_into_view()
        footer.assert_footer_visible()

    def test_terms_link_is_visible(self, navigated_homepage, footer: FooterComponent) -> None:
        """Step 4: The 'Terms' link must be visible in the footer navigation."""
        footer.scroll_into_view()
        footer.assert_terms_link_visible()

    def test_terms_link_text(self, navigated_homepage, footer: FooterComponent) -> None:
        """Step 4: The Terms link text must read 'Terms'."""
        text = footer.get_terms_link_text()
        assert text == "Terms", (
            f"Expected Terms link text to be 'Terms', but got {text!r}"
        )

    def test_terms_link_href(self, navigated_homepage, footer: FooterComponent) -> None:
        """Step 4: The Terms link must contain '/terms' in its href."""
        href = footer.get_terms_link_href()
        assert "/terms" in href, (
            f"Expected Terms link href to contain '/terms', but got {href!r}"
        )

    def test_privacy_link_is_visible(self, navigated_homepage, footer: FooterComponent) -> None:
        """Step 5: The 'Privacy' link must be visible in the footer navigation."""
        footer.scroll_into_view()
        footer.assert_privacy_link_visible()

    def test_privacy_link_text(self, navigated_homepage, footer: FooterComponent) -> None:
        """Step 5: The Privacy link text must read 'Privacy'."""
        text = footer.get_privacy_link_text()
        assert text == "Privacy", (
            f"Expected Privacy link text to be 'Privacy', but got {text!r}"
        )

    def test_privacy_link_href(self, navigated_homepage, footer: FooterComponent) -> None:
        """Step 5: The Privacy link must contain '/privacy' in its href."""
        href = footer.get_privacy_link_href()
        assert "/privacy" in href, (
            f"Expected Privacy link href to contain '/privacy', but got {href!r}"
        )

    def test_copyright_text_is_visible(self, navigated_homepage, footer: FooterComponent) -> None:
        """Step 6: The copyright paragraph must be visible in the footer."""
        footer.assert_copyright_visible()

    def test_copyright_text_contains_mytube(self, navigated_homepage, footer: FooterComponent) -> None:
        """Step 6: The copyright text must mention 'mytube'."""
        text = footer.get_copyright_text()
        assert "mytube" in text.lower(), (
            f"Expected copyright text to contain 'mytube', but got {text!r}"
        )

    def test_copyright_text_contains_all_rights_reserved(
        self, navigated_homepage, footer: FooterComponent
    ) -> None:
        """Step 6: The copyright text must contain 'All rights reserved'."""
        text = footer.get_copyright_text()
        assert "all rights reserved" in text.lower(), (
            f"Expected copyright text to contain 'All rights reserved', but got {text!r}"
        )

    def test_copyright_text_contains_copyright_symbol(
        self, navigated_homepage, footer: FooterComponent
    ) -> None:
        """Step 6: The copyright text must contain the © symbol."""
        text = footer.get_copyright_text()
        assert "©" in text, (
            f"Expected copyright text to contain '©', but got {text!r}"
        )
