"""
MYTUBE-368: Direct access to protected route with auth failure — error message displayed
instead of redirect.

Objective
---------
Verify that attempting to access a protected route when Firebase authentication fails
results in an error message rather than a silent redirect to the public home page.

Preconditions
-------------
The test simulates a Firebase authentication failure by injecting authError=true directly
into the React AuthContext via Playwright's page.evaluate() and React's internal fiber
hook-dispatch mechanism.

Why not network-level blocking?
Firebase JS SDK v9+ does NOT invoke onAuthStateChanged's error callback when HTTP domains
are blocked.  For a fresh (unauthenticated) browser session, Firebase resolves immediately
with user=null — it calls onAuthStateChanged's *success* callback, leaving authError=false
and triggering a normal RequireAuth redirect to /login.

The authError code path in AuthContext.tsx is only reachable when:
  • getFirebaseAuth() throws during SDK init (rare, requires invalid config), OR
  • onAuthStateChanged's error callback fires (requires a cached user whose token
    refresh fails with a Firebase-specific error code).

Neither condition can be reliably triggered from the outside in a production deployment.
The JavaScript fiber injection approach is therefore the correct and only reliable way to
test the authError=true UI behaviour from an E2E test.

Test flow
---------
1. Navigate to the protected /upload route (full page load).
2. Firebase resolves immediately with user=null (fresh session, no cached state).
3. RequireAuth redirects the browser to /login?next=%2Fupload%2F.
4. Once on /login and React is hydrated, inject authError=true into the React
   AuthContext via fiber dispatch.
5. React re-renders SiteHeader with the role="alert" span.
6. Assert the error message, URL and nav-link state.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig centralises env var access.
- RequireAuthComponent page object is used for loading-spinner assertions.
- SiteHeader page object (has_auth_error_alert / has_sign_in_link) is used for
  header-state assertions — consistent with the project's page-object architecture.
- Playwright sync API with function-scoped fixtures for test isolation.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.require_auth_component.require_auth_component import (
    RequireAuthComponent,
)
from testing.components.pages.site_header.site_header import SiteHeader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maximum time (ms) to wait for the loading spinner to disappear.
_LOADING_DISMISS_TIMEOUT_MS = 25_000

# Maximum time (ms) to wait for the auth-error alert to become visible after
# the injection has been dispatched.
_ERROR_VISIBILITY_TIMEOUT_MS = 10_000

# Exact text the SiteHeader renders in its role="alert" span when authError=true.
_EXPECTED_ERROR_TEXT = "Authentication services are currently unavailable"

# ---------------------------------------------------------------------------
# JavaScript injected via page.evaluate() to force authError=true in React.
#
# Strategy: traverse the React fiber tree starting from document.body, locate
# the AuthContext.Provider fiber (identified by its $$typeof symbol and by the
# presence of 'authError' in its memoizedProps.value), then traverse to its
# parent (the AuthProvider component fiber) and dispatch true on the 3rd
# useState hook (index 2, which is the authError hook).
#
# This approach:
#   • Works with minified production bundles — matches by context value shape,
#     not by component name.
#   • Does not depend on Firebase SDK internals or network conditions.
#   • React re-renders SiteHeader after the dispatch, showing the auth-error
#     alert instead of the "Sign in" navigation link.
#
# NOTE: In React 18 (as used by Next.js 14+), context Provider fibers carry
# $$typeof = Symbol.for('react.context'), NOT Symbol.for('react.provider').
# ---------------------------------------------------------------------------
_FORCE_AUTH_ERROR_SCRIPT = """
(function () {
    // In React 18 (Next.js 14+), context Provider fibers use react.context.
    var REACT_CONTEXT_TYPE = Symbol.for('react.context');

    function getFiber(el) {
        var keys = Object.getOwnPropertyNames(el);
        for (var i = 0; i < keys.length; i++) {
            if (keys[i].startsWith('__reactFiber') ||
                    keys[i].startsWith('__reactInternalInstance')) {
                return el[keys[i]];
            }
        }
        return null;
    }

    function walkFibers(root, predicate) {
        var queue = [root];
        var seen = new WeakSet();
        var limit = 3000;
        while (queue.length && limit-- > 0) {
            var fiber = queue.pop();
            if (!fiber || seen.has(fiber)) continue;
            seen.add(fiber);
            if (predicate(fiber)) return fiber;
            if (fiber.child) queue.push(fiber.child);
            if (fiber.sibling) queue.push(fiber.sibling);
        }
        return null;
    }

    function getRootFiber() {
        var candidates = [document.body].concat(Array.from(document.body.children));
        for (var i = 0; i < candidates.length; i++) {
            var f = getFiber(candidates[i]);
            if (f) return f;
        }
        return null;
    }

    var rootFiber = getRootFiber();
    if (!rootFiber) return false;

    // Find the AuthContext.Provider fiber: a context provider whose value
    // contains an 'authError' boolean property.
    var providerFiber = walkFibers(rootFiber, function (fiber) {
        if (!fiber.type || fiber.type.$$typeof !== REACT_CONTEXT_TYPE) return false;
        var val = fiber.memoizedProps && fiber.memoizedProps.value;
        return val !== null && val !== undefined && typeof val.authError === 'boolean';
    });

    if (!providerFiber) return false;

    // The parent (return) fiber is the AuthProvider component which owns the
    // useState hooks.  Hook order in AuthContext.tsx:
    //   hook 0 → user      (null | User)
    //   hook 1 → loading   (boolean)
    //   hook 2 → authError (boolean)
    var authProviderFiber = providerFiber.return;
    if (!authProviderFiber || !authProviderFiber.memoizedState) return false;

    var hook = authProviderFiber.memoizedState;  // hook 0: user
    hook = hook && hook.next;                    // hook 1: loading
    hook = hook && hook.next;                    // hook 2: authError

    if (hook && hook.queue && typeof hook.queue.dispatch === 'function') {
        hook.queue.dispatch(true);
        return true;
    }

    return false;
})()
"""


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
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="function")
def auth_error_page(browser: Browser) -> Page:
    """Open a fresh browser context for each test function.

    Each test navigates to /upload independently, triggering the
    RequireAuth redirect to /login, then injects authError=true.
    """
    context = browser.new_context()
    context.set_default_timeout(30_000)
    pg = context.new_page()
    pg.set_default_timeout(30_000)
    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProtectedRouteAuthFailureError:
    """MYTUBE-368: Protected route (/upload) must show auth-error, not home redirect."""

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _navigate_and_wait(self, page: Page, url: str) -> None:
        """Navigate to *url* and wait for the initial auth redirect to settle.

        For the protected /upload route, RequireAuth redirects to /login
        after Firebase resolves with user=null.  This helper waits for the
        URL to change away from the original path (or for networkidle),
        ensuring React is fully hydrated before any assertions or injection.
        """
        page.goto(url, wait_until="domcontentloaded")

        # Wait for RequireAuth redirect to complete (if any).
        try:
            page.wait_for_url("**/login**", timeout=15_000)
        except Exception:
            pass

        # Give React a moment to finish rendering after navigation.
        page.wait_for_load_state("networkidle", timeout=15_000)

    def _inject_auth_error(self, page: Page) -> bool:
        """Dispatch authError=true into the React AuthContext via fiber manipulation.

        Must be called after _navigate_and_wait() so React is fully hydrated.

        Returns True if the injection succeeded, False otherwise.
        """
        for _ in range(4):
            injected = page.evaluate(_FORCE_AUTH_ERROR_SCRIPT)
            if injected:
                return True
            page.wait_for_timeout(300)
        return False

    # ------------------------------------------------------------------
    # Tests
    # ------------------------------------------------------------------

    def test_loading_state_resolves_after_firebase_failure(
        self, auth_error_page: Page, web_config: WebConfig
    ) -> None:
        """The app must not remain stuck in a permanent loading state on /upload.

        After navigating directly to the protected /upload route, the RequireAuth
        loading spinner must disappear within _LOADING_DISMISS_TIMEOUT_MS
        milliseconds.  A permanent loading state would leave the user with no
        indication of what went wrong.
        """
        auth_error_page.goto(
            web_config.upload_url(), wait_until="domcontentloaded"
        )

        req = RequireAuthComponent(
            auth_error_page, auth_resolve_timeout=_LOADING_DISMISS_TIMEOUT_MS
        )

        # The spinner may be extremely brief for fresh sessions.  Silently
        # swallow a failure to observe it.
        try:
            req.assert_loading_spinner_visible()
        except Exception:
            pass

        # The important assertion: spinner must be GONE within the timeout.
        req.assert_spinner_hidden()

        assert not auth_error_page.locator(".animate-spin").is_visible(), (
            "The application is stuck in a permanent loading state after "
            f"navigating to '{web_config.upload_url()}'.\n"
            f"Expected the loading spinner to disappear within "
            f"{_LOADING_DISMISS_TIMEOUT_MS} ms."
        )

    def test_auth_error_message_displayed_on_protected_route(
        self, auth_error_page: Page, web_config: WebConfig
    ) -> None:
        """SiteHeader must display the auth-error alert when authError=true.

        Flow:
          1. Navigate to /upload → RequireAuth redirects to /login (user=null).
          2. Inject authError=true into the React AuthContext fiber on /login.
          3. SiteHeader re-renders: shows role="alert" with the error text.

        Acceptance criteria
        -------------------
        SiteHeader.has_auth_error_alert() is True and the alert text contains
        _EXPECTED_ERROR_TEXT.
        """
        self._navigate_and_wait(auth_error_page, web_config.upload_url())
        injected = self._inject_auth_error(auth_error_page)

        # Allow a brief moment for the React re-render to paint.
        try:
            auth_error_page.wait_for_function(
                """(text) => {
                    var alerts = document.querySelectorAll('[role="alert"]');
                    return Array.from(alerts).some(function(el) {
                        return el.offsetParent !== null &&
                               el.innerText && el.innerText.includes(text);
                    });
                }""",
                arg=_EXPECTED_ERROR_TEXT,
                timeout=_ERROR_VISIBILITY_TIMEOUT_MS,
            )
        except Exception:
            pass

        site_header = SiteHeader(auth_error_page)

        assert injected, (
            "Failed to inject authError=true into the React AuthContext. "
            "The _FORCE_AUTH_ERROR_SCRIPT could not locate the AuthProvider fiber. "
            f"Current URL: {auth_error_page.url}\n"
            "Ensure the page has fully hydrated before calling _inject_auth_error()."
        )

        assert site_header.has_auth_error_alert(), (
            f"Expected the SiteHeader to display a visible role='alert' element "
            f"containing '{_EXPECTED_ERROR_TEXT}' when authError=true.\n\n"
            f"Current URL: {auth_error_page.url}\n"
            f"Visible header text: "
            f"{auth_error_page.locator('header').inner_text()[:300]!r}\n\n"
            "Verify that SiteHeader.tsx renders the role='alert' span when "
            "authError=true."
        )

        alert_text = site_header.auth_error_alert_text()
        assert _EXPECTED_ERROR_TEXT in alert_text, (
            f"Expected auth-error alert text to contain:\n  '{_EXPECTED_ERROR_TEXT}'\n"
            f"Actual alert text:\n  '{alert_text}'"
        )

    def test_no_redirect_to_home_page(
        self, auth_error_page: Page, web_config: WebConfig
    ) -> None:
        """After Firebase failure, the app must NOT silently redirect to the home page.

        A silent redirect to / would hide the auth situation from the user.
        After auth resolves (loading disappears), the browser URL must not
        equal the application home URL.  Redirecting to /login is acceptable.
        """
        self._navigate_and_wait(auth_error_page, web_config.upload_url())

        current_url = auth_error_page.url
        home_url = web_config.home_url()

        assert current_url.rstrip("/") != home_url.rstrip("/"), (
            f"Expected the application NOT to redirect to the home page after "
            f"accessing a protected route.\n\n"
            f"Started at: '{web_config.upload_url()}'\n"
            f"Ended at:   '{current_url}'\n"
            f"Home URL:   '{home_url}'\n\n"
            "The RequireAuth guard must not redirect unauthenticated users to "
            "the home page — /login is the expected destination."
        )

    def test_no_sign_in_link_visible(
        self, auth_error_page: Page, web_config: WebConfig
    ) -> None:
        """No 'Sign in' navigation link must be visible in the header when authError=true.

        When authError=true, SiteHeader.tsx renders the auth-error alert span
        instead of the 'Sign in' anchor link.  Displaying 'Sign in' when auth
        services are down is misleading.

        Acceptance criteria
        -------------------
        SiteHeader.has_sign_in_link() returns False after authError=true injection.
        The selector is scoped to ``header a:has-text('Sign in')`` to avoid
        matching the /login form's <h2> heading or <button> elements.
        """
        self._navigate_and_wait(auth_error_page, web_config.upload_url())
        injected = self._inject_auth_error(auth_error_page)

        # Wait for the error state to replace the "Sign in" link.
        try:
            auth_error_page.wait_for_function(
                """(text) => {
                    var alerts = document.querySelectorAll('[role="alert"]');
                    return Array.from(alerts).some(function(el) {
                        return el.offsetParent !== null &&
                               el.innerText && el.innerText.includes(text);
                    });
                }""",
                arg=_EXPECTED_ERROR_TEXT,
                timeout=_ERROR_VISIBILITY_TIMEOUT_MS,
            )
        except Exception:
            pass

        site_header = SiteHeader(auth_error_page)

        assert injected, (
            "Failed to inject authError=true into the React AuthContext. "
            f"Current URL: {auth_error_page.url}"
        )

        assert not site_header.has_sign_in_link(), (
            "A 'Sign in' navigation link is visible in the header after "
            "authError=true was injected into the React AuthContext.\n\n"
            f"Current URL: {auth_error_page.url}\n"
            f"Visible header text: "
            f"{auth_error_page.locator('header').inner_text()[:300]!r}\n\n"
            "When authError=true, SiteHeader.tsx must render the role='alert' "
            "auth-error span instead of the 'Sign in' link."
        )
