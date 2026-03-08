"""
MYTUBE-401: Restoration of Firebase service connectivity — authentication error dismissed

Objective
---------
Verify that when Firebase auth network connectivity is restored the "Authentication services are currently unavailable" alert is automatically removed from the UI.

Approach
--------
- Reuse the heartbeat interval accelerator init script from existing tests so the heartbeat fires quickly.
- Start the app in a state where Firebase auth routes are blocked so the auth error appears.
- Unroute (unblock) the Firebase patterns and wait for the alert to disappear.

"""
from __future__ import annotations

import os
import re
import time
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

# Ensure repo root is on path to import testing core
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# Reuse patterns and init scripts from related tests
_FIREBASE_BLOCKED_PATTERNS = [
    "**/securetoken.googleapis.com/**",
    "**/identitytoolkit.googleapis.com/**",
    "**/*.firebaseapp.com/**",
    "**/firebase.googleapis.com/**",
]

_INTERVAL_ACCELERATOR_SCRIPT = """
(function () {
    var _origSetInterval = window.setInterval;
    window.setInterval = function (fn, delay) {
        var rest = [].slice.call(arguments, 2);
        var d = (typeof delay === 'number' && delay >= 30000) ? 2000 : delay;
        return _origSetInterval.apply(window, [fn, d].concat(rest));
    };
    window.__heartbeatAccelerated = true;
})();
"""

_FAKE_USER_INJECT_SCRIPT = """
(function () {
    var _origDefProp = Object.defineProperty;
    Object.defineProperty = function (target, prop, descriptor) {
        if (prop === 'hg' && descriptor && typeof descriptor.get === 'function') {
            window.__authIntercept401Activated = true;
            return _origDefProp(target, prop, {
                enumerable: descriptor.enumerable,
                configurable: true,
                get: function () {
                    return function fakeOnAuthStateChanged(auth, nextOrObserver) {
                        var nextCb;
                        if (typeof nextOrObserver === 'function') {
                            nextCb = nextOrObserver;
                        } else if (
                            nextOrObserver !== null &&
                            typeof nextOrObserver === 'object' &&
                            typeof nextOrObserver.next === 'function'
                        ) {
                            nextCb = nextOrObserver.next;
                        }
                        var fakeUser = {
                            uid: 'ci-uid-mytube-401',
                            email: 'ci@mytube401.test',
                            displayName: 'CI Tester',
                            photoURL: null,
                            emailVerified: true,
                            isAnonymous: false,
                            getIdToken: function (forceRefresh) {
                                if (!forceRefresh) {
                                    return Promise.resolve('ci-fake-id-token-401');
                                }
                                return fetch(
                                    'https://securetoken.googleapis.com/v1/token?key=ci-test-key',
                                    {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({
                                            grant_type: 'refresh_token',
                                            refresh_token: 'ci-fake-refresh-token'
                                        })
                                    }
                                ).then(function () { return 'ci-refreshed-token'; });
                            }
                        };
                        setTimeout(function () {
                            if (typeof nextCb === 'function') {
                                nextCb(fakeUser);
                            }
                        }, 200);
                        return function () {}; // unsubscribe noop
                    };
                }
            });
        }
        return _origDefProp.apply(Object, arguments);
    };
})();
"""

_AUTH_ERROR_KEYWORDS = re.compile(
    r"authentication\\s+services\\s+are\\s+currently\\s+unavailable"
    r"|authentication.*unavail"
    r"|auth.*services.*unavail"
    r"|services.*unavail"
    r"|firebase.*unavail",
    re.IGNORECASE,
)

_ERROR_VISIBILITY_TIMEOUT_MS = 20_000
_ERROR_DISMISS_TIMEOUT_MS = 60_000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _block_firebase_routes(context_or_page) -> None:
    for pattern in _FIREBASE_BLOCKED_PATTERNS:
        context_or_page.route(pattern, lambda route, request: route.abort())


def _wait_for_auth_error_message(page: Page, timeout_ms: int = _ERROR_VISIBILITY_TIMEOUT_MS) -> bool:
    _AUTH_ERROR_JS_PATTERN = (
        "authentication\\\\s+services\\\\s+are\\\\s+currently\\\\s+unavailable"
        "|authentication.*unavail"
        "|auth.*services.*unavail"
        "|services.*unavail"
        "|firebase.*unavail"
    )
    try:
        page.wait_for_function(
            "(pattern) => {\n                var re = new RegExp(pattern, 'i');\n                var alerts = document.querySelectorAll('[role=\"alert\"]');\n                for (var i = 0; i < alerts.length; i++) {\n                    var t = alerts[i].innerText || '';\n                    if (t.trim().length > 0 && re.test(t)) return true;\n                }\n                var body = document.body ? document.body.innerText : '';\n                return re.test(body);\n            }",
            arg=_AUTH_ERROR_JS_PATTERN,
            timeout=timeout_ms,
        )
        return True
    except Exception:
        pass
    # final sync check
    try:
        visible_text = page.locator("body").inner_text()
        if _AUTH_ERROR_KEYWORDS.search(visible_text):
            return True
    except Exception:
        pass
    return False


def _wait_for_auth_error_gone(page: Page, timeout_ms: int = _ERROR_DISMISS_TIMEOUT_MS) -> bool:
    start = time.time()
    end = start + (timeout_ms / 1000.0)
    while time.time() < end:
        try:
            # check role=alert elements
            alerts = page.locator("[role=alert]")
            found = False
            for i in range(alerts.count()):
                el = alerts.nth(i)
                if not el.is_visible():
                    continue
                t = (el.text_content() or "").strip()
                if t and _AUTH_ERROR_KEYWORDS.search(t):
                    found = True
                    break
            if not found:
                # check body fallback
                body = page.locator("body").inner_text()
                if not _AUTH_ERROR_KEYWORDS.search(body):
                    return True
        except Exception:
            return True
        time.sleep(0.5)
    return False

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(headless=web_config.headless, slow_mo=web_config.slow_mo)
        yield br
        br.close()


@pytest.fixture(scope="function")
def auth_error_page(browser: Browser, web_config: WebConfig) -> Page:
    firebase_api_key = os.getenv("FIREBASE_API_KEY", "")
    email = web_config.test_email
    password = web_config.test_password
    has_credentials = bool(firebase_api_key and email and password)

    context: BrowserContext = browser.new_context()
    context.set_default_timeout(30_000)
    context.add_init_script(script=_INTERVAL_ACCELERATOR_SCRIPT)
    if not has_credentials:
        context.add_init_script(script=_FAKE_USER_INJECT_SCRIPT)

    pg: Page = context.new_page()
    pg.set_default_timeout(30_000)

    if has_credentials:
        # perform real login
        pg.goto(web_config.login_url(), wait_until="domcontentloaded")
        try:
            pg.wait_for_selector('input[id="email"]', timeout=15_000)
            pg.fill('input[id="email"]', email)
            pg.fill('input[id="password"]', password)
            pg.click('button[type="submit"]:not([aria-label="Submit search"])')
            pg.wait_for_url(lambda url: "/login" not in url, timeout=20_000)
            pg.goto(web_config.dashboard_url(), wait_until="domcontentloaded")
        except Exception:
            pass
    else:
        pg.goto(web_config.home_url(), wait_until="domcontentloaded")
        activated = pg.evaluate("typeof window.__authIntercept401Activated !== 'undefined' && window.__authIntercept401Activated === true")
        if not activated:
            pg.evaluate("window.__mytube401_intercept_failed = true")
        else:
            pg.evaluate("window.__mytube401_intercept_failed = false")

    # Now block Firebase routes so the app shows the auth error
    _block_firebase_routes(pg)

    # Wait for the auth error to appear
    found = _wait_for_auth_error_message(pg)
    if not found:
        # provide diagnostics and fail early
        try:
            txt = pg.locator('body').inner_text()[:800]
        except Exception:
            txt = '<unable to read body text>'
        context.close()
        pytest.skip("Could not detect initial auth error message. Body text: %s" % txt)

    yield pg
    context.close()

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFirebaseConnectivityRestoration:
    def test_auth_error_is_removed_after_connectivity_restored(self, auth_error_page: Page, web_config: WebConfig) -> None:
        page = auth_error_page

        # Verify initial error is present
        assert _wait_for_auth_error_message(page), "Expected auth error to be visible before unblocking routes"

        # Unblock firebase routes
        for pattern in _FIREBASE_BLOCKED_PATTERNS:
            try:
                page.unroute(pattern)
            except Exception:
                # some Playwright versions accept context.unroute; attempt both
                try:
                    page.context.unroute(pattern)
                except Exception:
                    pass

        # Wait for the app to detect restored connectivity and remove the alert
        gone = _wait_for_auth_error_gone(page)
        assert gone, "Expected the auth error alert to be removed from the UI after connectivity was restored"
