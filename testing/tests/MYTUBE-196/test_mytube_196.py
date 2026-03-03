"""
MYTUBE-196: Access dashboard while unauthenticated — user redirected to login.

Objective:
    Ensure the /dashboard route is protected and requires authentication.
    When an unauthenticated user navigates directly to /dashboard, the application
    must redirect them to the login page.

Preconditions
-------------
- User is not logged in (fresh browser context with no cookies or stored auth).
- The web application is deployed and reachable.

Test steps
----------
1. Launch a fresh browser context (no stored authentication).
2. Navigate directly to {base_url}/dashboard/.
3. Wait for the client-side auth guard to redirect to /login.
4. Assert the current URL contains /login (not /dashboard).
5. Assert the login sign-in form is visible on the redirected page.

Environment variables
---------------------
WEB_BASE_URL / APP_URL  : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses LoginPage (Page Object pattern) for login-page assertions.
- WebConfig from testing/core/config/web_config.py centralises all env var access.
- No Firebase credentials required — verifies the unauthenticated redirect only.
- No time.sleep() — explicit Playwright wait_for_url for the auth redirect.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REDIRECT_TIMEOUT = 20_000   # ms — time allowed for client-side auth redirect
_PAGE_LOAD_TIMEOUT = 15_000  # ms — default Playwright page action timeout


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
    """Open a fresh browser context with no stored authentication state."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def after_redirect(web_config: WebConfig, page: Page) -> Page:
    """Navigate to /dashboard unauthenticated and wait for the page to settle.

    Navigates directly to the protected /dashboard route without any credentials
    or session cookies, then gives the client-side auth guard time to redirect.
    If the redirect does not happen within the timeout, the fixture still returns
    so that the test assertions can fail with a clear message.
    All tests in this module share this fixture — the navigation is performed
    exactly once.
    """
    dashboard_url = f"{web_config.base_url}/dashboard/"
    page.goto(dashboard_url, wait_until="domcontentloaded")
    # Allow up to _REDIRECT_TIMEOUT for the auth guard to redirect to /login.
    # If it doesn't redirect, continue — the test assertions will fail clearly.
    try:
        page.wait_for_url(
            lambda u: "/login" in u,
            timeout=_REDIRECT_TIMEOUT,
        )
    except Exception:
        # Redirect did not happen within the timeout; assertions below capture the bug.
        pass
    return page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUnauthenticatedDashboardRedirect:
    """MYTUBE-196: Accessing /dashboard while unauthenticated redirects to /login."""

    def test_redirected_away_from_dashboard(self, after_redirect: Page) -> None:
        """The browser must NOT remain on the /dashboard URL after the redirect.

        If the app fails to protect the route, the URL will still contain
        /dashboard after navigation settles.
        """
        assert "/dashboard" not in after_redirect.url, (
            f"Expected the app to redirect away from /dashboard, "
            f"but the current URL still contains '/dashboard': {after_redirect.url!r}"
        )

    def test_redirected_to_login_url(self, after_redirect: Page) -> None:
        """The browser URL must contain /login after the unauthenticated access attempt."""
        assert "/login" in after_redirect.url, (
            f"Expected the app to redirect to a URL containing '/login', "
            f"but the current URL is: {after_redirect.url!r}"
        )

    def test_login_form_is_visible(self, after_redirect: Page) -> None:
        """The login page must render the email/password sign-in form.

        Verifies that the user landed on a functional login page, not just
        any page whose URL happens to contain '/login'.
        """
        login_page = LoginPage(after_redirect)
        assert login_page.is_form_visible(), (
            f"Expected the login form (email input) to be visible after the "
            f"redirect, but it was not found. Current URL: {after_redirect.url!r}"
        )
