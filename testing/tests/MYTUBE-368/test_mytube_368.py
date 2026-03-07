"""
MYTUBE-368: Direct access to protected route with auth failure — error message displayed
instead of redirect.

Objective
---------
Verify that attempting to access a protected route when Firebase authentication fails
results in an error message rather than a silent redirect to the public home page.

Preconditions
-------------
Firebase authentication domains (identitytoolkit.googleapis.com,
securetoken.googleapis.com) are blocked prior to page load.

Steps
-----
1. Navigate directly to a protected route URL (e.g., /upload).
2. Observe the page behaviour after the loading indicator disappears.

Expected Result
---------------
The application displays a clear error message:
"Authentication services are currently unavailable."
The application does not redirect the user to the home page or render
guest-only navigation links (e.g., "Sign in").

Test approach
-------------
Uses Playwright's context.route() to intercept and abort all HTTP(S) requests to
Firebase authentication endpoints before navigating to /upload, simulating an SDK
initialisation failure.  The test then asserts:

  1. The loading spinner disappears within a reasonable timeout (the app is not stuck).
  2. The SiteHeader renders the role="alert" span containing
     "Authentication services are currently unavailable" — NOT a "Sign in" link.
  3. The browser URL is NOT the application home page (/).

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- RequireAuthComponent page object from
  testing/components/pages/require_auth_component/require_auth_component.py is
  reused for loading-spinner selectors.
- Playwright sync API with pytest function-scoped fixtures so each test gets a
  fresh browser context with Firebase routes already blocked.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, expect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.require_auth_component.require_auth_component import (
    RequireAuthComponent,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Firebase auth-related domains to block, simulating an SDK failure / outage.
_FIREBASE_AUTH_PATTERNS = [
    "**/identitytoolkit.googleapis.com/**",
    "**/securetoken.googleapis.com/**",
    "**/*.firebaseapp.com/**",
    "**/firebase.googleapis.com/**",
    "**/googleapis.com/identitytoolkit/**",
]

# Maximum time (ms) to wait for the loading spinner to disappear.
_LOADING_DISMISS_TIMEOUT_MS = 20_000

# Maximum time (ms) to wait for the auth-error alert to appear.
_ERROR_VISIBILITY_TIMEOUT_MS = 15_000

# Exact text the SiteHeader renders in its role="alert" span when authError=true.
_EXPECTED_ERROR_TEXT = "Authentication services are currently unavailable"

# Selector for the SiteHeader auth-error alert element.
_AUTH_ERROR_ALERT_SELECTOR = "[role='alert']"

# Selectors / text patterns that indicate a "Sign in" guest link is present.
# The test must assert NONE of these are visible when authError=true.
_SIGN_IN_SELECTORS = [
    "a:has-text('Sign in')",
    "text=Sign in",
    "a[href*='/login']:has-text('Sign in')",
]

# Loading text rendered by RequireAuth.tsx while Firebase resolves.
_LOADING_TEXT_SELECTOR = "text=Loading\u2026"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="function")
def blocked_page(browser: Browser) -> Page:
    """Open a fresh browser context with Firebase auth domains blocked.

    Each test function gets its own context so route intercepts do not bleed
    between tests.
    """
    context = browser.new_context()
    context.set_default_timeout(30_000)

    for pattern in _FIREBASE_AUTH_PATTERNS:
        context.route(pattern, lambda route, **_: route.abort())

    pg = context.new_page()
    pg.set_default_timeout(30_000)
    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProtectedRouteAuthFailureError:
    """MYTUBE-368: Protected route (/upload) must show auth-error, not home redirect."""

    def test_loading_state_resolves_after_firebase_failure(
        self, blocked_page: Page, web_config: WebConfig
    ) -> None:
        """The app must not remain stuck in a permanent loading state on /upload.

        After blocking Firebase auth requests and navigating directly to the
        protected /upload route, the RequireAuth loading spinner must disappear
        within _LOADING_DISMISS_TIMEOUT_MS milliseconds.

        A permanent loading state would leave the user with no indication of
        what went wrong, which is a failure condition in itself.
        """
        blocked_page.goto(web_config.upload_url(), wait_until="domcontentloaded")

        loading = blocked_page.locator(_LOADING_TEXT_SELECTOR)
        try:
            loading.wait_for(state="visible", timeout=5_000)
            loading.wait_for(state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS)
        except Exception:
            # Loading text may never appear if auth resolves/errors very fast.
            pass

        assert not blocked_page.locator(_LOADING_TEXT_SELECTOR).is_visible(), (
            "The application is stuck in a permanent loading state after "
            "Firebase auth domains were blocked and the user navigated to "
            f"'{web_config.upload_url()}'.\n"
            f"Expected the loading spinner to disappear within "
            f"{_LOADING_DISMISS_TIMEOUT_MS} ms, but it is still visible."
        )

    def test_auth_error_message_displayed_on_protected_route(
        self, blocked_page: Page, web_config: WebConfig
    ) -> None:
        """The SiteHeader must display the auth-error message on /upload.

        With Firebase blocked, AuthContext sets authError=true, and SiteHeader
        renders a role="alert" span with:
          "Authentication services are currently unavailable"
        instead of the normal "Sign in" navigation link.

        Acceptance criteria
        -------------------
        A visible element with role="alert" must contain the exact phrase
        "Authentication services are currently unavailable".
        """
        blocked_page.goto(web_config.upload_url(), wait_until="domcontentloaded")

        # Wait for loading to clear before asserting the error state.
        loading = blocked_page.locator(_LOADING_TEXT_SELECTOR)
        try:
            loading.wait_for(state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS)
        except Exception:
            pass

        # Allow the auth-error alert a moment to become visible.
        try:
            blocked_page.wait_for_function(
                """(text) => {
                    const alerts = document.querySelectorAll('[role="alert"]');
                    return Array.from(alerts).some(
                        el => el.innerText && el.innerText.includes(text)
                    );
                }""",
                arg=_EXPECTED_ERROR_TEXT,
                timeout=_ERROR_VISIBILITY_TIMEOUT_MS,
            )
        except Exception:
            pass

        alert_locator = blocked_page.locator(_AUTH_ERROR_ALERT_SELECTOR)
        found_error = False
        for i in range(alert_locator.count()):
            el = alert_locator.nth(i)
            if not el.is_visible():
                continue
            text = (el.text_content() or "").strip()
            if _EXPECTED_ERROR_TEXT in text:
                found_error = True
                break

        if not found_error:
            page_url = blocked_page.url
            visible_body = blocked_page.locator("body").inner_text()[:600].replace("\n", " ")
            assert False, (
                f"Expected the application to display the error message "
                f"'{_EXPECTED_ERROR_TEXT}' in a visible role='alert' element "
                f"after blocking Firebase auth domains and navigating to "
                f"'{web_config.upload_url()}'.\n\n"
                f"Current URL: {page_url}\n"
                f"Visible body text (first 600 chars): {visible_body!r}\n\n"
                "Check that AuthContext.tsx sets authError=true when Firebase "
                "auth fails, and that SiteHeader.tsx renders the role='alert' "
                "span with the expected text when authError=true."
            )

    def test_no_redirect_to_home_page(
        self, blocked_page: Page, web_config: WebConfig
    ) -> None:
        """After Firebase failure, the app must NOT silently redirect to the home page.

        A silent redirect to the home page would hide the auth error from the
        user and incorrectly suggest the application is working normally.

        The browser URL after auth resolution must not equal the home URL.
        Redirecting to /login (with the auth-error banner still visible) is
        acceptable; returning to / is not.
        """
        blocked_page.goto(web_config.upload_url(), wait_until="domcontentloaded")

        # Wait for auth state to resolve (loading disappears or URL changes).
        loading = blocked_page.locator(_LOADING_TEXT_SELECTOR)
        try:
            loading.wait_for(state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS)
        except Exception:
            pass

        # Give client-side routing a moment to settle.
        blocked_page.wait_for_timeout(2_000)

        current_url = blocked_page.url
        home_url = web_config.home_url()

        # Normalise for trailing-slash variance.
        normalised_current = current_url.rstrip("/")
        normalised_home = home_url.rstrip("/")

        assert normalised_current != normalised_home, (
            f"Expected the application NOT to redirect to the home page after "
            f"Firebase auth failure on a protected route.\n\n"
            f"Started at: '{web_config.upload_url()}'\n"
            f"Ended at:   '{current_url}'\n"
            f"Home URL:   '{home_url}'\n\n"
            "The RequireAuth guard or AuthContext should not silently redirect "
            "the user to the home page when authentication services are "
            "unavailable. Display an error message instead."
        )

    def test_no_sign_in_link_visible(
        self, blocked_page: Page, web_config: WebConfig
    ) -> None:
        """No 'Sign in' guest link must be visible when authError=true.

        When Firebase auth fails, SiteHeader.tsx renders the auth-error span
        instead of the 'Sign in' navigation link.  Rendering a 'Sign in' link
        would misleadingly suggest users can authenticate, when in fact auth
        services are down.
        """
        blocked_page.goto(web_config.upload_url(), wait_until="domcontentloaded")

        # Wait for auth state to resolve.
        loading = blocked_page.locator(_LOADING_TEXT_SELECTOR)
        try:
            loading.wait_for(state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS)
        except Exception:
            pass

        # Allow the error state to settle.
        try:
            blocked_page.wait_for_function(
                """(text) => {
                    const alerts = document.querySelectorAll('[role="alert"]');
                    return Array.from(alerts).some(
                        el => el.innerText && el.innerText.includes(text)
                    );
                }""",
                arg=_EXPECTED_ERROR_TEXT,
                timeout=_ERROR_VISIBILITY_TIMEOUT_MS,
            )
        except Exception:
            pass

        for selector in _SIGN_IN_SELECTORS:
            sign_in_locator = blocked_page.locator(selector)
            if sign_in_locator.count() > 0 and sign_in_locator.first.is_visible():
                page_url = blocked_page.url
                assert False, (
                    f"A 'Sign in' navigation link is visible after Firebase auth "
                    f"failure on the protected /upload route.\n\n"
                    f"Matched selector: {selector!r}\n"
                    f"Current URL: {page_url}\n\n"
                    "When authError=true, SiteHeader.tsx must render the "
                    "role='alert' auth-error span INSTEAD of the 'Sign in' link. "
                    "Displaying 'Sign in' when auth services are down is "
                    "misleading and violates the expected behaviour."
                )
