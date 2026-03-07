"""
MYTUBE-351: Firebase auth initialization error — error state displayed.

Objective
---------
Verify that the application displays an error state if the Firebase SDK
fails to resolve the authentication status.

Steps
-----
1. Simulate a Firebase SDK initialization failure by blocking all requests
   to Firebase auth domains (identitytoolkit.googleapis.com,
   securetoken.googleapis.com, *.firebaseapp.com, firebase.googleapis.com).
2. Load the application (navigate to the home page /).

Expected Result
---------------
The application displays a clear error message indicating that
authentication services are currently unavailable, instead of remaining in
a permanent loading state or allowing access.

Test approach
-------------
Uses Playwright's page.route() to intercept and abort all HTTP(S) requests
to Firebase authentication endpoints, simulating an SDK initialisation
failure.  The test then navigates to the deployed home page and asserts that:

  1. The application does NOT remain stuck in a permanent loading state
     (the "Loading…" spinner must disappear within a reasonable timeout).
  2. An error element visible to the user that communicates authentication
     unavailability is present in the DOM (e.g. role="alert", or text
     matching "unavailable", "authentication", "error").

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest function-scoped fixtures (each test gets a
  fresh browser context with the route intercepts already in place).
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import re
import sys
import time

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Firebase auth-related domains to block.
# Blocking these simulates an SDK initialisation failure / network outage.
_FIREBASE_AUTH_PATTERNS = [
    "**/identitytoolkit.googleapis.com/**",
    "**/securetoken.googleapis.com/**",
    "**/*.firebaseapp.com/**",
    "**/firebase.googleapis.com/**",
    # Firebase also uses this URL pattern for auth REST calls
    "**/googleapis.com/identitytoolkit/**",
]

# How long (ms) to wait for the loading indicator to disappear.
# If it does not disappear within this time we treat it as a "permanent
# loading state" — which is also a failure condition.
_LOADING_DISMISS_TIMEOUT_MS = 15_000

# How long (ms) to wait for an error element to become visible.
_ERROR_VISIBILITY_TIMEOUT_MS = 10_000

# CSS selectors / text patterns that indicate an auth-unavailability error.
# The app should render at least one of these when Firebase fails.
_AUTH_ERROR_SELECTORS = [
    # Standard ARIA alert role
    "[role='alert']",
    # Common plain-language phrases
    "text=unavailable",
    "text=authentication",
    "text=auth",
    "text=error",
]

# Keyword patterns (case-insensitive) that indicate an auth error message.
_AUTH_ERROR_KEYWORDS = re.compile(
    r"unavailable|authentication.*(error|fail|unavail)|"
    r"(error|fail).*authentication|firebase.*error|"
    r"sign.in.*unavail|services.*unavail",
    re.IGNORECASE,
)

# The loading text rendered by RequireAuth.tsx / AuthContext consumers.
_LOADING_TEXT_SELECTOR = "text=Loading…"


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


def _make_blocked_context(browser: Browser, web_config: WebConfig) -> BrowserContext:
    """Create a new browser context with all Firebase auth requests aborted."""
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(30_000)

    # Abort every request matching a Firebase auth pattern.
    for pattern in _FIREBASE_AUTH_PATTERNS:
        context.route(pattern, lambda route, _p=pattern: route.abort())

    context.close()  # close the probe page; the context itself stays open
    return context


@pytest.fixture(scope="function")
def blocked_page(browser: Browser, web_config: WebConfig) -> Page:
    """Open a fresh browser context with Firebase auth domains blocked.

    Each test function gets its own context so route registrations do not
    bleed between tests.
    """
    context = browser.new_context()
    context.set_default_timeout(30_000)

    # Register abort handlers for all Firebase auth patterns.
    for pattern in _FIREBASE_AUTH_PATTERNS:
        context.route(pattern, lambda route, **_: route.abort())

    pg = context.new_page()
    pg.set_default_timeout(30_000)
    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFirebaseAuthErrorState:
    """MYTUBE-351: Application must display an auth-error state when Firebase fails."""

    def test_loading_state_resolves(
        self, blocked_page: Page, web_config: WebConfig
    ) -> None:
        """The app must not remain in a permanent loading state.

        After blocking Firebase auth requests and navigating to the home page,
        the "Loading…" spinner must disappear within _LOADING_DISMISS_TIMEOUT_MS.
        A permanent loading state would prevent users from receiving any
        feedback.
        """
        blocked_page.goto(web_config.home_url())

        loading = blocked_page.locator(_LOADING_TEXT_SELECTOR)
        try:
            loading.wait_for(state="visible", timeout=5_000)
            # Loading indicator appeared — wait for it to go away.
            loading.wait_for(state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS)
        except Exception:
            # If loading text was never visible the page either loaded fast or
            # already shows an error.  Check it is not still present.
            pass

        # Final assertion: "Loading…" must not be in the DOM.
        assert not blocked_page.locator(_LOADING_TEXT_SELECTOR).is_visible(), (
            "The application is stuck in a permanent loading state after "
            "Firebase auth domains were blocked. "
            "Expected the loading indicator to disappear within "
            f"{_LOADING_DISMISS_TIMEOUT_MS} ms."
        )

    def test_auth_error_message_is_displayed(
        self, blocked_page: Page, web_config: WebConfig
    ) -> None:
        """An auth-error message must be visible after Firebase is blocked.

        The app must communicate to the user that authentication services are
        unavailable rather than silently falling back to an unauthenticated
        state (which would be misleading — users might not know why they cannot
        sign in).

        Acceptance criteria
        -------------------
        At least one element with *non-empty* text content must be visible
        in the page that matches the _AUTH_ERROR_KEYWORDS pattern
        (e.g. "Authentication services are currently unavailable").

        A role="alert" element with empty text (e.g. the Next.js
        RouteAnnouncer) does NOT satisfy this requirement.
        """
        blocked_page.goto(web_config.home_url())

        # Wait for any loading state to clear first.
        loading = blocked_page.locator(_LOADING_TEXT_SELECTOR)
        try:
            loading.wait_for(state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS)
        except Exception:
            pass

        # Give the app a moment to render any error state.
        time.sleep(2)

        # Check all role="alert" elements for non-empty auth-related content.
        alert_locator = blocked_page.locator("[role='alert']")
        for i in range(alert_locator.count()):
            el = alert_locator.nth(i)
            if not el.is_visible():
                continue
            alert_text = (el.text_content() or "").strip()
            if alert_text and _AUTH_ERROR_KEYWORDS.search(alert_text):
                return  # PASS — visible alert with auth-error content

        # Broader text-based search: only inspect visible rendered text.
        # Use inner_text() which respects CSS visibility and skips <script>
        # and hidden elements — prevents false positives on inline JS.
        specific_patterns = [
            re.compile(r"authentication.*unavail", re.IGNORECASE),
            re.compile(r"auth.*services.*unavail", re.IGNORECASE),
            re.compile(r"services.*unavail", re.IGNORECASE),
            re.compile(r"firebase.*unavail", re.IGNORECASE),
            re.compile(r"sign.in.*unavail", re.IGNORECASE),
            re.compile(r"unavailable.*authentication", re.IGNORECASE),
            re.compile(r"authentication.*error", re.IGNORECASE),
            re.compile(r"auth.*error", re.IGNORECASE),
        ]

        visible_text = blocked_page.locator("body").inner_text()
        for pattern in specific_patterns:
            if pattern.search(visible_text):
                return  # PASS — auth-error text visible to the user

        # No auth error message found.  Capture full page state for reporting.
        page_url = blocked_page.url
        page_title = blocked_page.title()
        visible_text_snippet = visible_text[:600].replace("\n", " ")

        # Detect whether the app silently fell back to unauthenticated state.
        sign_in_visible = (
            blocked_page.locator("a[href*='/login']").count() > 0
            or blocked_page.get_by_text("Sign in").count() > 0
        )
        fallback_note = (
            " The app appears to have silently treated the Firebase failure as an "
            "unauthenticated session and rendered the normal home page with a "
            "'Sign in' link, without informing the user that authentication "
            "services are unavailable."
            if sign_in_visible
            else ""
        )

        assert False, (
            "Expected the application to display a clear error message about "
            "authentication services being unavailable after blocking Firebase "
            "auth domains, but no such message was found.\n\n"
            f"URL: {page_url}\n"
            f"Page title: {page_title!r}\n"
            f"Page body text (first 600 chars): {visible_text_snippet!r}\n"
            f"Sign-in link visible (unauthenticated fallback): {sign_in_visible}\n\n"
            "The app should render an element with role='alert' containing "
            "auth-error text, or visible text matching patterns such as "
            "'Authentication services are currently unavailable'."
            + fallback_note
        )
