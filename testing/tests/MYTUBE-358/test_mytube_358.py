"""
MYTUBE-358: Access My Videos page while authenticated — page content loads successfully.

Objective
---------
Verify that the '/my-videos' route is correctly implemented and accessible to
authenticated users.

Preconditions
-------------
User is logged in with a valid session token.

Steps
-----
1. Navigate directly to the /my-videos URL in the browser.

Expected Result
---------------
The application successfully loads the My Videos page.  The URL remains
/my-videos and the user's video content is displayed without any redirection
to the home page or login page.

Environment variables
---------------------
- FIREBASE_TEST_EMAIL    : Email of the registered Firebase test user (required).
- FIREBASE_TEST_PASSWORD : Password for the test Firebase user (required).
- APP_URL / WEB_BASE_URL : Base URL of the deployed web app.
                           Default: https://ai-teammate.github.io/mytube
- PLAYWRIGHT_HEADLESS    : Run browser headless (default: true).
- PLAYWRIGHT_SLOW_MO     : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses LoginPage to authenticate first, then navigates to /my-videos.
- Uses DashboardPage to verify content on the /my-videos page (which renders
  the same DashboardContent component as /dashboard).
- WebConfig centralises all env-var access.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_AUTH_TIMEOUT      = 20_000   # ms — max time to wait for login to complete
_CONTENT_TIMEOUT   = 20_000   # ms — max time to wait for page content


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are absent."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-358. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-358. "
            "Set FIREBASE_TEST_PASSWORD to run this test."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def authenticated_page(browser: Browser, web_config: WebConfig) -> Page:
    """Open a browser context, log in, and yield an authenticated page.

    The login step navigates to /login, fills the form, and waits until
    the browser leaves the /login URL before yielding, guaranteeing that
    subsequent tests start from an authenticated session.
    """
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Navigate to login page and authenticate.
    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)

    # Wait for the browser to leave /login (successful auth).
    page.wait_for_url(
        lambda u: "/login" not in u,
        timeout=_AUTH_TIMEOUT,
    )

    yield page
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMyVideosPageAuthenticatedAccess:
    """MYTUBE-358: /my-videos must load without redirect for authenticated users."""

    def test_my_videos_page_loads_without_redirect(
        self,
        authenticated_page: Page,
        web_config: WebConfig,
    ) -> None:
        """Step 1 & Expected Result: Navigate to /my-videos while authenticated.

        Asserts that:
        - The URL stays on /my-videos (no redirect to / or /login).
        - The page does not visibly show a 404 error to the user.
        """
        my_videos_url = web_config.my_videos_url()
        dashboard_page = DashboardPage(authenticated_page)
        dashboard_page.navigate(my_videos_url)

        current_url = authenticated_page.url

        # The URL must remain on /my-videos.
        assert "/my-videos" in current_url, (
            f"Expected to stay on /my-videos after navigation but was redirected. "
            f"Current URL: {current_url!r}. "
            f"The /my-videos route may not be implemented or may be redirecting "
            f"authenticated users to the home page or login page."
        )

        # Must not be redirected to the login page.
        assert "/login" not in current_url, (
            f"Authenticated user was redirected to the login page when accessing "
            f"/my-videos. Current URL: {current_url!r}. "
            f"RequireAuth should not redirect authenticated users to /login."
        )

        # Must not be redirected to the home page root.
        assert not _is_home_page(current_url, web_config.base_url), (
            f"Authenticated user was redirected to the home page when accessing "
            f"/my-videos. Current URL: {current_url!r}. "
            f"The /my-videos route may be missing from the Next.js app router."
        )

        # Must not visibly render a 404 error page — check via DashboardPage which
        # uses DOM-based locators to avoid Next.js RSC JSON false positives.
        assert not dashboard_page.is_404_page(), (
            f"The /my-videos page visibly displays a 404 not-found error to the user. "
            f"Current URL: {current_url!r}. "
            f"Ensure the route 'web/src/app/my-videos/page.tsx' is deployed and "
            f"accessible."
        )

    def test_my_videos_page_renders_content(
        self,
        authenticated_page: Page,
        web_config: WebConfig,
    ) -> None:
        """Expected Result: The My Videos page renders user video content.

        Asserts that the DashboardContent component (reused by /my-videos) is
        present — either a video table or an upload CTA is visible once the
        page has settled.
        """
        dashboard_page = DashboardPage(authenticated_page)

        # At minimum, verify the page settled on /my-videos and has rendered
        # some meaningful content (table or upload CTA).
        has_table = dashboard_page.is_table_visible()
        has_upload_cta = dashboard_page.is_upload_cta_visible(timeout=5_000)

        assert has_table or has_upload_cta, (
            f"After navigating to /my-videos, neither the video table nor the "
            f"'Upload new video' CTA was visible. The page may not have rendered "
            f"the DashboardContent component. Current URL: {authenticated_page.url!r}."
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_home_page(current_url: str, base_url: str) -> bool:
    """Return True if *current_url* is the application root / home page."""
    stripped_current = current_url.rstrip("/")
    stripped_base = base_url.rstrip("/")
    return stripped_current == stripped_base
