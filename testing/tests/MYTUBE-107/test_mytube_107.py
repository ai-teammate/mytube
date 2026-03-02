"""
MYTUBE-107: Login with email and password — user authenticated and redirected to home.

Verifies that a registered user can sign in on the /login page using a valid
email and password, and is subsequently redirected to the home page (/).

Preconditions
-------------
- A user account is already registered in Firebase.
- The web application is deployed and reachable at WEB_BASE_URL.

Test steps
----------
1. Navigate to the /login page.
2. Enter a valid email address and password into the form.
3. Click the "Sign In" button.
4. Assert the browser redirects to the home page (/).
5. Assert the Firebase ID token has been persisted in localStorage.

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
- Playwright sync API with pytest-playwright style fixtures.
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
            "FIREBASE_TEST_EMAIL not set — skipping web login test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping web login test. "
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
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)


@pytest.fixture(scope="module")
def after_login(web_config: WebConfig, login_page: LoginPage, page: Page):
    """
    Perform the full login flow once and yield the page after the redirect.

    All tests in this module share this fixture — the login is executed
    exactly once per test run.
    """
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    # Wait for post-login redirect (Firebase auth + router.replace('/'))
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)
    yield page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoginFlow:
    """MYTUBE-107: Login with email and password redirects to home page."""

    def test_redirected_to_home_page(self, after_login, web_config: WebConfig):
        """After sign-in, the browser URL must equal the home page URL."""
        current_url = after_login.url.rstrip("/")
        expected_url = web_config.home_url().rstrip("/")
        assert current_url == expected_url, (
            f"Expected redirect to home page '{expected_url}', "
            f"but current URL is '{current_url}'"
        )

    def test_firebase_token_in_local_storage(self, after_login):
        """Firebase persists the ID token in localStorage after successful sign-in.

        Firebase SDK stores auth state under keys matching the pattern
        ``firebase:authUser:<apiKey>:<appName>`` or stores a token directly
        under ``firebase:token:<apiKey>``.  We check that at least one
        localStorage key contains the string 'firebase' to confirm the SDK
        has written its auth state.
        """
        keys: list = after_login.evaluate("() => Object.keys(localStorage)")
        firebase_keys = [k for k in keys if "firebase" in k.lower()]
        assert firebase_keys, (
            "Expected Firebase auth state in localStorage after login, "
            f"but found no firebase-related keys. All keys: {keys}"
        )

    def test_no_error_message_displayed(self, after_login, login_page: LoginPage):
        """No error alert should be visible after a successful login."""
        error = login_page.get_error_message()
        assert error is None, (
            f"Unexpected error message displayed after login: {error!r}"
        )
