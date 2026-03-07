"""
MYTUBE-342: View navigation as authenticated user — Upload link is visible.

Verifies that the "Upload" link appears in the primary navigation menu of the
site header once the user is authenticated via Firebase.

Preconditions
-------------
- A user account is already registered in Firebase.
- The web application is deployed and reachable at WEB_BASE_URL.

Test steps
----------
1. Log in at /login with valid Firebase credentials.
2. Wait for the post-login redirect to the home page (/).
3. Inspect the primary navigation menu in the header.
4. Assert that the "Upload" link (href="/upload") is visible.

Environment variables
---------------------
- FIREBASE_TEST_EMAIL    : Email of the registered Firebase test user (required).
- FIREBASE_TEST_PASSWORD : Password of the registered Firebase test user (required).
- WEB_BASE_URL           : Base URL of the deployed web app.
                           Default: https://ai-teammate.github.io/mytube
- PLAYWRIGHT_HEADLESS    : Run browser headless (default: true).
- PLAYWRIGHT_SLOW_MO     : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses LoginPage (Page Object) from testing/components/pages/login_page/.
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
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NAVIGATION_TIMEOUT = 20_000   # ms — max time to wait for post-login redirect
_PAGE_LOAD_TIMEOUT = 30_000    # ms — max time for initial page load

# Selector for the primary navigation in SiteHeader.tsx
_PRIMARY_NAV = "nav[aria-label='Primary navigation']"
# Upload link within the primary nav
_UPLOAD_LINK = f"{_PRIMARY_NAV} a[href*='/upload']"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are not provided."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping navigation upload link test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping navigation upload link test. "
            "Set FIREBASE_TEST_PASSWORD to run this test."
        )


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
def after_login(web_config: WebConfig, page: Page):
    """
    Perform the full login flow once and yield the page on the home page.

    All tests in this module share this fixture — the login is executed
    exactly once per test run.
    """
    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)
    yield page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadLinkVisibleAfterLogin:
    """MYTUBE-342: Upload link is visible in primary navigation for authenticated users."""

    def test_primary_nav_is_present(self, after_login: Page):
        """The primary navigation element should exist in the page header."""
        nav = after_login.locator(_PRIMARY_NAV)
        assert nav.count() > 0, (
            "Primary navigation element (nav[aria-label='Primary navigation']) "
            "was not found in the header. Ensure the SiteHeader is rendered."
        )

    def test_upload_link_is_visible(self, after_login: Page):
        """The Upload link must be visible in the primary navigation after authentication.

        According to SiteHeader.tsx, the Upload link is only rendered when the
        Firebase 'user' object is present.  If this assertion fails it means
        either authentication did not complete or the conditional rendering is
        broken.
        """
        upload_link = after_login.locator(_UPLOAD_LINK)
        assert upload_link.count() > 0, (
            "Upload link (a[href*='/upload']) was not found inside the primary "
            "navigation. The link is only rendered when user is authenticated. "
            "Verify Firebase auth completed and the 'user' context is populated."
        )
        assert upload_link.first.is_visible(), (
            "Upload link exists in the DOM but is not visible. "
            "Check that the nav element and its children are not hidden."
        )

    def test_upload_link_text(self, after_login: Page):
        """The Upload link should display the text 'Upload'."""
        upload_link = after_login.locator(_UPLOAD_LINK).first
        link_text = upload_link.inner_text().strip()
        assert link_text == "Upload", (
            f"Expected Upload link text to be 'Upload', got '{link_text}'"
        )

    def test_upload_link_href(self, after_login: Page, web_config: WebConfig):
        """The Upload link href should point to the /upload path."""
        upload_link = after_login.locator(_UPLOAD_LINK).first
        href = upload_link.get_attribute("href") or ""
        assert "/upload" in href, (
            f"Expected Upload link href to contain '/upload', got '{href}'"
        )
