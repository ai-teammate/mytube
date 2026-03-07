"""
MYTUBE-352: Access My Videos page while unauthenticated — user redirected to login.

Objective
---------
Ensure the 'My Videos' page is protected by route guards and requires authentication.

Preconditions
-------------
User is not logged in (no active Firebase session in the browser).

Steps
-----
1. Attempt to navigate directly to the /my-videos URL.

Expected Result
---------------
The client-side route guard detects the unauthenticated state and automatically
redirects the user to the login page.

Architecture
------------
- Uses LoginPage page object from testing/components/pages/login_page/login_page.py
  to assert the final landing page is the login form.
- WebConfig from testing/core/config/web_config.py centralises all env var access.
- Playwright sync API with pytest module-scoped browser fixture.
- No hardcoded URLs or credentials.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  : Base URL of the deployed web application.
                          Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     : Run browser in headless mode (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms for debugging (default: 0).
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 20_000  # ms — maximum time to wait for the redirect
_REDIRECT_TIMEOUT = 15_000   # ms — time to wait for URL to change to /login

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser():
    config = WebConfig()
    with sync_playwright() as pw:
        b = pw.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo,
        )
        yield b
        b.close()


@pytest.fixture(scope="module")
def context(browser: Browser) -> BrowserContext:
    """A fresh browser context with no stored auth state."""
    ctx = browser.new_context()
    yield ctx
    ctx.close()


@pytest.fixture(scope="module")
def page(context: BrowserContext) -> Page:
    p = context.new_page()
    yield p
    p.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMyVideosUnauthenticatedRedirect:
    """The /my-videos route must redirect unauthenticated users to /login."""

    def test_unauthenticated_redirect_to_login(
        self, page: Page, web_config: WebConfig
    ) -> None:
        """Navigate to /my-videos as an unauthenticated user and assert redirect.

        Steps
        -----
        1. Open a fresh browser context (no cookies / stored auth).
        2. Navigate to {base_url}/my-videos/.
        3. Wait up to 15 s for the URL to contain '/login'.
        4. Assert that the login form is rendered on the page.
        """
        my_videos_url = web_config.my_videos_url()
        login_url = web_config.login_url()

        # Navigate to the protected /my-videos page
        page.goto(my_videos_url, wait_until="domcontentloaded")

        # The client-side RequireAuth guard fires after hydration.
        # Wait for the URL to include '/login' (with or without query params).
        try:
            page.wait_for_url(
                lambda url: "/login" in url,
                timeout=_REDIRECT_TIMEOUT,
            )
        except Exception as exc:
            current_url = page.url
            raise AssertionError(
                f"Expected to be redirected to the login page after navigating "
                f"to '{my_videos_url}' as an unauthenticated user, but the URL "
                f"did not change to contain '/login' within "
                f"{_REDIRECT_TIMEOUT / 1000:.0f} s.\n"
                f"Actual URL at time of failure: '{current_url}'"
            ) from exc

        final_url = page.url
        assert "/login" in final_url, (
            f"URL after redirect does not contain '/login': '{final_url}'"
        )

        # Additionally confirm the login form itself is visible
        login_page = LoginPage(page)
        assert login_page.is_form_visible(), (
            f"Navigated to '{final_url}' but the login form (email input) is "
            f"not visible. The redirect may have landed on an unexpected page."
        )
