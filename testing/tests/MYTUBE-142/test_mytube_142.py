"""
MYTUBE-142: Access /upload page while unauthenticated — user redirected to login.

Verifies that the video upload page is inaccessible to unauthenticated users.
When a user who is not logged in navigates directly to /upload, the application
must automatically redirect them to the /login page.

Preconditions
-------------
- User is not authenticated (fresh browser context with no session/token).
- The web application is deployed and reachable at WEB_BASE_URL.

Test steps
----------
1. Open a fresh browser context (no stored auth state).
2. Navigate directly to the /upload URL.
3. Wait for any client-side auth check and redirect to complete.
4. Assert the browser URL contains /login.

Environment variables
---------------------
- WEB_BASE_URL  : Base URL of the deployed web app.
                  Default: https://ai-teammate.github.io/mytube
- APP_URL       : Alternative env var for the base URL (takes precedence).
- PLAYWRIGHT_HEADLESS : Run browser headless (default: true).
- PLAYWRIGHT_SLOW_MO  : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses UploadPage (Page Object) from testing/components/pages/upload_page/.
- WebConfig from testing/core/config/web_config.py centralises all env var access.
- Playwright sync API with pytest fixtures.
- No hardcoded URLs or credentials.
"""
import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.upload_page.upload_page import UploadPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms — max time for page load and redirect


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
    """Open a fresh browser context with no stored auth state."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def upload_page(page: Page) -> UploadPage:
    return UploadPage(page)


@pytest.fixture(scope="module")
def after_navigate_to_upload(web_config: WebConfig, upload_page: UploadPage):
    """Navigate to /upload once and yield the UploadPage for all tests to inspect."""
    upload_page.navigate(web_config.base_url)
    yield upload_page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadPageUnauthenticated:
    """MYTUBE-142: Unauthenticated access to /upload is redirected to /login."""

    def test_redirected_to_login_page(
        self, after_navigate_to_upload: UploadPage, web_config: WebConfig
    ):
        """Navigating to /upload without auth must redirect to the /login page."""
        current_url = after_navigate_to_upload.get_current_url()
        expected_fragment = "/login"
        assert expected_fragment in current_url, (
            f"Expected redirect to a URL containing '{expected_fragment}', "
            f"but current URL is '{current_url}'"
        )

    def test_not_remaining_on_upload_page(
        self, after_navigate_to_upload: UploadPage
    ):
        """The browser must not remain on the /upload page after navigation."""
        current_url = after_navigate_to_upload.get_current_url()
        assert "/upload" not in current_url, (
            f"Expected to be redirected away from /upload, "
            f"but current URL is still '{current_url}'"
        )
