"""
MYTUBE-340: Click logo in header — user redirected to homepage.

Objective
---------
Verify that clicking the site logo in the header always redirects the user
to the root homepage, regardless of which sub-page they are currently on.

Steps
-----
1. Navigate to a sub-page (e.g., /search).
2. Click on the site logo located in the header.

Expected Result
---------------
The application navigates to the homepage (/) and the root content is rendered.

Test approach
-------------
Two sub-pages are tested to confirm the logo redirect is consistent:
  - /search    — a page accessible without authentication
  - /register  — another unauthenticated page

For each sub-page:
  1. Navigate to the sub-page and confirm the URL is not the homepage.
  2. Locate the logo link in SiteHeader (``header a.text-red-600``).
  3. Click the logo.
  4. Wait for navigation to settle and assert the URL ends with ``/``.
  5. Optionally assert homepage content (recently-uploaded/most-viewed heading) is visible.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web application.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser in headless mode (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms for debugging (default: 0).

Architecture
------------
- Uses SiteHeader (Page Object) from testing/components/pages/site_header/.
- Uses HomePage (Page Object) from testing/components/pages/home_page/.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import logging
import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, expect

_logger = logging.getLogger(__name__)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.site_header.site_header import SiteHeader
from testing.components.pages.home_page.home_page import HomePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_NAVIGATION_TIMEOUT = 15_000  # ms — wait for URL to change after logo click


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _url_is_homepage(url: str, base_url: str) -> bool:
    """Return True if *url* represents the root homepage of the app."""
    base = base_url.rstrip("/")
    # Strip query string and fragment
    clean = url.split("?")[0].split("#")[0].rstrip("/")
    return clean == base or clean == base + "/"


def _navigate_and_wait(page: Page, url: str) -> None:
    """Go to *url* and wait for the DOM to settle."""
    page.goto(url)
    try:
        page.wait_for_load_state("domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)
    except Exception as exc:
        _logger.warning("wait_for_load_state timed out (%s); continuing anyway.", exc)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLogoRedirectToHomepage:
    """MYTUBE-340: Clicking the header logo redirects to the homepage (/)."""

    @pytest.mark.parametrize(
        "subpage_path",
        [
            "/search",
            "/register",
        ],
        ids=["search-page", "register-page"],
    )
    def test_logo_click_redirects_to_homepage(
        self,
        page: Page,
        web_config: WebConfig,
        subpage_path: str,
    ) -> None:
        """Logo click from a sub-page must navigate to the root homepage.

        Steps
        -----
        1. Navigate to the sub-page.
        2. Assert the current URL is NOT the homepage.
        3. Click the site logo in the header.
        4. Assert the URL has changed to the root homepage.
        """
        base_url = web_config.base_url
        subpage_url = base_url.rstrip("/") + subpage_path

        # Step 1 — navigate to the sub-page
        _navigate_and_wait(page, subpage_url)

        # Step 2 — confirm we are NOT already on the homepage
        current = page.url
        assert not _url_is_homepage(current, base_url), (
            f"Expected to start on a sub-page ({subpage_url!r}), but the "
            f"browser is already on the homepage: {current!r}. "
            "Check that the sub-page URL is valid and that routing is working."
        )

        # Step 3 — click the logo
        header = SiteHeader(page)
        assert header.logo_is_visible(), (
            f"The site logo is not visible on {subpage_url!r}. "
            "Ensure the SiteHeader is rendered on all pages."
        )
        header.click_logo()

        # Step 4 — wait for navigation and assert we landed on the homepage
        try:
            page.wait_for_url(
                re.compile(re.escape(base_url.rstrip("/")) + r"/?$"),
                timeout=_NAVIGATION_TIMEOUT,
            )
        except Exception as exc:
            _logger.warning("wait_for_url timed out (%s); checking URL directly.", exc)

        final_url = page.url
        assert _url_is_homepage(final_url, base_url), (
            f"Expected the site logo to navigate to the homepage ({base_url}/), "
            f"but landed on: {final_url!r}. "
            f"Started from sub-page: {subpage_url!r}."
        )

    def test_homepage_content_rendered_after_logo_click(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """After logo click the homepage content sections must be rendered.

        This test continues from the state left by the parametrized test above
        (browser already on the homepage after clicking the logo from /register).

        It navigates fresh to /search and clicks the logo again, then asserts
        that the homepage discovery sections are visible.
        """
        base_url = web_config.base_url
        subpage_url = base_url.rstrip("/") + "/search"

        # Navigate to search and click logo
        _navigate_and_wait(page, subpage_url)

        header = SiteHeader(page)
        assert header.logo_is_visible(), (
            f"The site logo is not visible on {subpage_url!r}."
        )
        header.click_logo()

        # Wait for homepage to load
        try:
            page.wait_for_url(
                re.compile(re.escape(base_url.rstrip("/")) + r"/?$"),
                timeout=_NAVIGATION_TIMEOUT,
            )
        except Exception as exc:
            _logger.warning("wait_for_url timed out (%s); checking URL directly.", exc)

        # Assert URL
        assert _url_is_homepage(page.url, base_url), (
            f"Logo click did not navigate to the homepage; landed on: {page.url!r}."
        )

        # Assert homepage content — at least one discovery section must be visible.
        # Use HomePage's public assertion API; it encapsulates the loading wait.
        home = HomePage(page)
        try:
            home.assert_recently_uploaded_section_visible()
        except AssertionError:
            home.assert_most_viewed_section_visible()
