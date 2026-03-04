"""
MYTUBE-241: Refresh registration page — page content persists and no 404 error is returned.

Objective:
    Ensure that direct navigation and browser refreshes on sub-routes do not
    trigger 404 errors from the static hosting configuration (GitHub Pages).

Steps:
    1. Navigate to https://ai-teammate.github.io/mytube/register/
    2. Once the page has loaded, perform a hard refresh (page.reload() simulates Ctrl+R).

Expected Result:
    The application reloads correctly. The server (GitHub Pages) does not return
    a "File not found" error, and the registration form heading remains visible.

Test approach:
    Playwright is used to simulate a hard browser refresh on the /register/ sub-route.

    On a hard refresh the browser sends the full URL directly to the server.
    Without a proper GitHub Pages SPA fallback (e.g. 404.html that redirects to
    index.html), the server returns a raw "File not found" response and the React
    app never loads.

    This test verifies:
      1. Direct navigation to /register/ renders the "Create an account" h1.
      2. After page.reload() (hard-refresh simulation), the heading remains visible.
      3. No "File not found" text is present on the page after reload.

Environment variables:
    APP_URL / WEB_BASE_URL : Base URL of the deployed web app.
                             Default: https://ai-teammate.github.io/mytube
    PLAYWRIGHT_HEADLESS    : Run browser headless (default: true).
    PLAYWRIGHT_SLOW_MO     : Slow-motion delay in ms (default: 0).

Architecture:
    - Uses RegisterPage (Page Object) from testing/components/pages/register_page/.
    - WebConfig from testing/core/config/web_config.py centralises env var access.
    - Playwright sync API with pytest module-scoped browser and function-scoped page.
    - No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.register_page.register_page import RegisterPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms — maximum time for the page to load
_AUTH_SETTLE_TIMEOUT = 20_000  # ms — time for Firebase auth state to resolve


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser instance shared across all tests in the module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture
def page(browser: Browser) -> Page:
    """Open a fresh browser context and page for each test."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegisterPageRefresh:
    """MYTUBE-241: Hard refresh on /register/ must not produce a 404 error."""

    def test_register_page_loads_on_direct_navigation(
        self, page: Page, web_config: WebConfig
    ) -> None:
        """Direct navigation to /register/ must display the registration form.

        Verifies that the GitHub Pages static hosting configuration correctly
        serves the SPA for the /register/ sub-route (not a raw 404 page).

        The RegisterPage.navigate() method navigates to /register/ and waits
        for the <h1> heading to appear, confirming the SPA loaded.
        """
        register_page = RegisterPage(page)
        register_page.navigate(web_config.base_url)

        assert register_page.is_on_register_page(), (
            f"Direct navigation to {web_config.register_url()} did not show the "
            "'Create an account' heading. "
            "GitHub Pages may have returned a 404 for the /register/ sub-route. "
            f"Current URL: {page.url}"
        )

    def test_no_file_not_found_on_direct_navigation(
        self, page: Page, web_config: WebConfig
    ) -> None:
        """The page body must not contain 'File not found' on direct navigation.

        A raw GitHub Pages 404 response includes 'File not found' in the body.
        If this text appears it confirms the server-side routing fallback is absent.
        """
        register_page = RegisterPage(page)
        register_page.navigate(web_config.base_url)

        assert not register_page.has_file_not_found_error(), (
            f"Direct navigation to {web_config.register_url()} produced a "
            "'File not found' error in the page body. "
            "GitHub Pages is not configured to serve the SPA for sub-routes. "
            f"Current URL: {page.url}"
        )

    def test_register_page_heading_visible_after_hard_refresh(
        self, page: Page, web_config: WebConfig
    ) -> None:
        """The registration form heading must remain visible after a hard refresh.

        After page.reload() (simulating Ctrl+R / Cmd+R), the browser sends the
        full /register/ URL directly to the GitHub Pages server.  Without a
        proper 404.html SPA redirect, the server returns a raw 'File not found'
        response and the React app never loads.

        This is the core assertion of the test case:
          - Navigate to /register/
          - Reload via page.reload()
          - 'Create an account' h1 must still be visible
        """
        register_page = RegisterPage(page)
        register_page.navigate(web_config.base_url)

        # Simulate a hard browser refresh (Ctrl+R / Cmd+R)
        register_page.hard_refresh()

        assert register_page.is_on_register_page(), (
            "After hard refresh (page.reload()) on /register/, the "
            "'Create an account' heading was NOT visible. "
            "The GitHub Pages static hosting configuration does not correctly "
            "handle browser refreshes on sub-routes — a 404 error is likely "
            "being returned by the server. "
            f"Current URL: {page.url}"
        )

    def test_no_file_not_found_after_hard_refresh(
        self, page: Page, web_config: WebConfig
    ) -> None:
        """The body must not contain 'File not found' text after a hard refresh.

        This is the definitive DOM-level check: if the page body contains
        'File not found' after reload, GitHub Pages served a raw 404 response
        for /register/, confirming the SPA routing fallback is missing or broken.
        """
        register_page = RegisterPage(page)
        register_page.navigate(web_config.base_url)

        # Simulate hard refresh
        register_page.hard_refresh()

        assert not register_page.has_file_not_found_error(), (
            "After hard refresh on /register/, the page shows 'File not found'. "
            "This confirms GitHub Pages returned HTTP 404 for the /register/ "
            "sub-route on a direct server request. "
            "The static hosting configuration must be updated to redirect all "
            "sub-routes to index.html so the SPA can handle routing client-side. "
            f"Current URL: {page.url}"
        )
