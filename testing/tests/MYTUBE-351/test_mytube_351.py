"""
MYTUBE-351: Firebase auth initialization error — error state displayed.

Objective
---------
Verify that the application displays an error state if the Firebase SDK
fails to resolve the authentication status.

Steps
-----
1. Simulate a Firebase SDK initialization failure by injecting a script
   via context.add_init_script that overrides the onAuthStateChanged export
   (webpack module 9997, export key "hg") to call the error callback after
   a 100 ms delay instead of the success callback.
2. Load the application (navigate to the home page /).

Expected Result
---------------
The application displays a clear error message indicating that
authentication services are currently unavailable, instead of remaining in
a permanent loading state or allowing access.

Test approach
-------------
Uses Playwright's context.add_init_script to inject a script before any
page scripts run.  The script intercepts Object.defineProperty calls and,
when webpack tries to define the "hg" export (onAuthStateChanged) on a
module exports object, replaces the getter with a factory that returns a
fake onAuthStateChanged that always calls the error callback after 100 ms.
This directly triggers authError = true in AuthContext without relying on
any network calls.

Why not network blocking?
Network blocking (context.route()) was tried in previous runs and always
failed: for unauthenticated users with no cached session the Firebase SDK
resolves onAuthStateChanged with null synchronously from localStorage /
IndexedDB without making any network requests, so the error callback is
never triggered.

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
  fresh browser context with the init script already injected).
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Init script injected before any page scripts run.
# Intercepts Object.defineProperty to detect when webpack module 9997 exports
# "hg" (onAuthStateChanged) and replaces it with a fake that always calls the
# error callback after 100 ms, directly triggering authError = true in
# AuthContext without relying on any network calls.
#
# IMPORTANT — minification-dependent export key "hg":
# The key "hg" is assigned by webpack's minifier at build time and will change
# with any webpack config change, Firebase JS SDK version bump, or minification
# seed change.  If the intercept silently stops working (tests timeout with
# "element not found" instead of asserting the auth-error alert), re-discover
# the current key by running the following in DevTools after loading the app:
#
#   Object.entries(window.__webpack_modules__ ?? {})
#     .find(([, m]) => m?.toString().includes('onAuthStateChanged'))
#
# Update the prop === 'hg' check below with the new key.
#
# The script sets window.__authInterceptActivated = true when it matches the
# property.  The blocked_page fixture asserts this flag after page load to
# detect silently-broken intercepts early.
_FIREBASE_INTERCEPT_SCRIPT = """
(function () {
    var _origDefProp = Object.defineProperty;
    Object.defineProperty = function (target, prop, descriptor) {
        if (
            prop === 'hg' &&
            descriptor &&
            typeof descriptor.get === 'function'
        ) {
            window.__authInterceptActivated = true;
            return _origDefProp(target, prop, {
                enumerable: descriptor.enumerable,
                configurable: true,
                get: function () {
                    return function fakeOnAuthStateChanged(auth, nextOrObserver, error) {
                        var errorCb;
                        if (
                            nextOrObserver !== null &&
                            typeof nextOrObserver === 'object' &&
                            typeof nextOrObserver.error === 'function'
                        ) {
                            errorCb = nextOrObserver.error;
                        } else {
                            errorCb = error;
                        }
                        setTimeout(function () {
                            if (typeof errorCb === 'function') {
                                errorCb(
                                    new Error(
                                        'Firebase: Error (auth/network-request-failed).' +
                                        ' A network AuthError has occurred (simulated).'
                                    )
                                );
                            }
                        }, 100);
                        return function () {}; // unsubscribe no-op
                    };
                }
            });
        }
        return _origDefProp.apply(Object, arguments);
    };
})();
"""

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


@pytest.fixture(scope="function")
def blocked_page(browser: Browser, web_config: WebConfig) -> Page:
    """Yield a Page already navigated to home_url with the Firebase intercept active.

    The init script overrides Object.defineProperty to replace the webpack
    'hg' export (onAuthStateChanged) with a fake that always calls the error
    callback after 100 ms, directly triggering authError = true in AuthContext.

    Each test function gets its own context so the init script injection does
    not bleed between tests.

    NOTE: The page is pre-navigated to home_url before it is yielded.
    Tests MUST NOT call ``pg.goto()`` again — doing so causes a redundant
    double-navigation (the intercept does re-activate, but it doubles wall-clock
    time for every test in this suite).
    """
    context = browser.new_context()
    context.set_default_timeout(30_000)

    # Inject the Firebase interception script before any page scripts run.
    context.add_init_script(script=_FIREBASE_INTERCEPT_SCRIPT)

    pg = context.new_page()
    pg.set_default_timeout(30_000)

    # Navigate and assert that the intercept actually activated.
    # window.__authInterceptActivated is set by the script when it matches the
    # 'hg' property.  If False, the minified export key has changed and the
    # script needs updating — see the comment above _FIREBASE_INTERCEPT_SCRIPT.
    pg.goto(web_config.home_url())
    activated = pg.evaluate("typeof window.__authInterceptActivated !== 'undefined' && window.__authInterceptActivated === true")
    assert activated, (
        "Firebase intercept script did NOT activate (window.__authInterceptActivated is not true). "
        "The minified webpack export key 'hg' may have changed. "
        "Re-discover the current key with: "
        "Object.entries(window.__webpack_modules__ ?? {}).find(([, m]) => m?.toString().includes('onAuthStateChanged'))"
    )

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

        Note: blocked_page is pre-navigated to home_url by the fixture.
        """
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

        Note: blocked_page is pre-navigated to home_url by the fixture.
        """
        # Wait for any loading state to clear first.
        loading = blocked_page.locator(_LOADING_TEXT_SELECTOR)
        try:
            loading.wait_for(state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS)
        except Exception:
            pass

        # Poll until an error alert with non-empty text appears, or timeout elapses.
        try:
            blocked_page.wait_for_function(
                """() => {
                    const alerts = document.querySelectorAll('[role="alert"]');
                    return Array.from(alerts).some(el => el.innerText.trim().length > 0);
                }""",
                timeout=_ERROR_VISIBILITY_TIMEOUT_MS,
            )
        except Exception:
            pass

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
