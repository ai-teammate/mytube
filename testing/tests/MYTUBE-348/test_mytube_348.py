"""
MYTUBE-348: Authenticate after redirect — original URL and query parameters preserved.

Objective
---------
Verify that after a successful login, the user is redirected back to the URL
they originally attempted to access, including all query parameters.

Preconditions
-------------
User is not authenticated.

Steps
-----
1. Attempt to navigate directly to /upload?category=gaming&priority=high.
2. Verify the application redirects to the /login page.
3. Complete the login process with valid credentials.

Expected Result
---------------
The application successfully authenticates the user and redirects them back to
/upload?category=gaming&priority=high, ensuring the query parameters are fully
preserved.

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
- Uses LoginPage (Page Object) to authenticate.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest-style fixtures.
"""
import os
import sys
from urllib.parse import urlparse, parse_qs, urlencode

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, expect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000    # ms
_REDIRECT_TIMEOUT  = 15_000    # ms — max time to wait for auth redirect

# The protected URL we try to access before authenticating.
_PROTECTED_PATH         = "/upload"
_EXPECTED_QUERY_PARAMS  = {"category": "gaming", "priority": "high"}
_EXPECTED_QUERY_STRING  = "category=gaming&priority=high"


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
            "FIREBASE_TEST_EMAIL not set — skipping redirect-preservation test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping redirect-preservation test. "
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
def fresh_page(browser: Browser) -> Page:
    """Open a fresh (unauthenticated) browser context and yield a page."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _protected_url_with_params(base_url: str) -> str:
    """Return the full protected URL including query parameters."""
    return f"{base_url.rstrip('/')}{_PROTECTED_PATH}?{_EXPECTED_QUERY_STRING}"


def _url_contains_query_params(url: str, expected: dict) -> bool:
    """Return True if *url* contains all *expected* query parameters."""
    parsed = urlparse(url)
    actual_params = parse_qs(parsed.query)
    for key, value in expected.items():
        if key not in actual_params:
            return False
        if actual_params[key][0] != value:
            return False
    return True


def _url_path_matches(url: str, expected_path: str) -> bool:
    """Return True if the path component of *url* ends with *expected_path*."""
    parsed = urlparse(url)
    # GitHub Pages adds a /mytube prefix; strip it for the check.
    path = parsed.path.rstrip("/")
    return path.endswith(expected_path.rstrip("/"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthRedirectPreservesQueryParams:
    """MYTUBE-348: Login redirect must preserve the original URL with query params."""

    def test_unauthenticated_access_redirects_to_login(
        self, fresh_page: Page, web_config: WebConfig
    ):
        """Step 1 & 2: Navigating to the protected URL while unauthenticated must
        redirect to the /login page."""
        target_url = _protected_url_with_params(web_config.base_url)
        fresh_page.goto(target_url, wait_until="networkidle", timeout=_PAGE_LOAD_TIMEOUT)

        current_url = fresh_page.url
        assert "/login" in current_url, (
            f"Expected to be redirected to /login after accessing protected URL "
            f"'{target_url}' while unauthenticated, but current URL is: {current_url!r}"
        )

    def test_login_page_shows_sign_in_form(
        self, fresh_page: Page, web_config: WebConfig
    ):
        """The /login page must render a sign-in form after the redirect."""
        login_page = LoginPage(fresh_page)
        assert login_page.is_form_visible(), (
            "The login form (email input) is not visible on the /login page. "
            f"Current URL: {fresh_page.url!r}"
        )

    def test_after_login_redirects_back_with_query_params(
        self, fresh_page: Page, web_config: WebConfig
    ):
        """Step 3 & Expected Result: After successful login, the browser must be
        redirected back to the original URL including all query parameters.

        This test verifies both:
        - The path is /upload (not the home page or dashboard).
        - The query parameters category=gaming&priority=high are preserved.
        """
        login_page = LoginPage(fresh_page)

        # Complete login with valid credentials.
        login_page.login_as(web_config.test_email, web_config.test_password)

        # Wait until the browser navigates away from /login.
        fresh_page.wait_for_url(
            lambda u: "/login" not in u,
            timeout=_REDIRECT_TIMEOUT,
        )

        final_url = fresh_page.url

        # Assert the path is the original protected path (/upload).
        assert _url_path_matches(final_url, _PROTECTED_PATH), (
            f"After login, expected redirect to path '{_PROTECTED_PATH}' but got: "
            f"{final_url!r}. The app did not redirect back to the originally "
            f"requested page."
        )

        # Assert both query parameters are preserved.
        assert _url_contains_query_params(final_url, _EXPECTED_QUERY_PARAMS), (
            f"After login, the URL '{final_url}' is missing one or more expected "
            f"query parameters. Expected: {_EXPECTED_QUERY_PARAMS}. "
            f"The auth redirect mechanism does not preserve query parameters from "
            f"the original URL."
        )
