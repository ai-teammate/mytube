"""
MYTUBE-395: Auth state resolution with expired token and blocked network —
error message displayed instead of guest state.

Objective
---------
Verify that the application displays an error message when it cannot refresh
an expired or invalid session token due to network blocking, preventing a
silent fallback to a guest state.

Preconditions
-------------
The browser's local storage contains an expired or invalid Firebase session
token.

Steps
-----
1. Block all Firebase authentication domains at the network level.
2. Load the application home page.
3. Observe the UI state once the initial loading indicator disappears.

Expected Result
---------------
The application displays the error message:
  "Authentication services are currently unavailable."
The user is NOT silently transitioned to an unauthenticated guest state
(i.e., the page does NOT render a "Sign in" link or the public home page
without any error indication).

Test approach
-------------
Phase 1 — API key discovery:
  A clean Playwright page loads the deployed app and captures the Firebase
  API key either from outbound network requests to googleapis.com (?key=...)
  or, if no such request is made for an unauthenticated session, by scanning
  the webpack module registry in the page's JS context for the ``AIza...``
  key pattern embedded by the Next.js build process.

Phase 2 — Blocked-network test:
  A fresh Playwright context is created with:
    1. An ``add_init_script`` that populates localStorage with a structurally
       valid but expired Firebase user object under the key
       ``firebase:authUser:<apiKey>:[DEFAULT]``.  The stsTokenManager carries
       an ``expirationTime`` in the past so the Firebase SDK detects an expired
       access token and attempts a refresh before calling onAuthStateChanged.
    2. ``context.route()`` rules that abort all requests to Firebase auth and
       token endpoints (securetoken.googleapis.com, identitytoolkit.googleapis.com,
       and the configured authDomain).  With the network blocked the token
       refresh fails and Firebase fires the onAuthStateChanged error callback,
       which sets ``authError = true`` in AuthContext.
  The test then asserts:
    - The loading indicator disappears (app resolves auth state).
    - An auth-error message is visible (role="alert" or body text matching
      auth-unavailability keywords).
    - No "Sign in" link is visible (not silently treated as unauthenticated).

Why not re-use the webpack intercept from MYTUBE-351?
  MYTUBE-351 uses a minification-dependent export key ("hg") to override
  onAuthStateChanged.  MYTUBE-395 tests a different code path: the actual
  Firebase SDK behaviour when it holds an expired session token and the
  network is unavailable.  Network blocking is the mechanism called for in
  the ticket and tests a real production failure scenario.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- SiteHeader Page Object from testing/components/pages/site_header/ is used
  to query auth state (auth error alert, sign-in link).
- Playwright sync API with pytest function-scoped fixtures.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from typing import Optional
from urllib.parse import urlparse, parse_qs

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.site_header.site_header import SiteHeader

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# How long to wait for the loading indicator to disappear (ms).
_LOADING_DISMISS_TIMEOUT_MS = 20_000

# How long to wait for the auth-error alert to become visible after loading
# clears.  Firebase SDK v12 attempts a token refresh synchronously before
# calling onAuthStateChanged; with the network blocked the request fails
# within the OS TCP timeout (~10 s) or immediately when Playwright aborts it.
_ERROR_VISIBILITY_TIMEOUT_MS = 15_000

# Playwright abort timeout for the initial key-discovery navigation (ms).
_DISCOVERY_TIMEOUT_MS = 30_000

# Selector for the loading state.
_LOADING_TEXT_SELECTOR = "text=Loading…"

# Keywords that confirm an auth-error message is visible.
_AUTH_ERROR_KEYWORDS = re.compile(
    r"unavailable|authentication.*(error|fail|unavail)|"
    r"(error|fail).*authentication|firebase.*error|"
    r"sign.in.*unavail|services.*unavail",
    re.IGNORECASE,
)

# Firebase auth / token request patterns to block.
_FIREBASE_BLOCK_PATTERNS = [
    "**/*securetoken.googleapis.com/**",
    "**/*identitytoolkit.googleapis.com/**",
    "**/*googleapis.com/identitytoolkit/**",
    # Also block any *.firebaseapp.com auth domain calls
    "**/*.firebaseapp.com/**",
    "**/*firebaseio.com/**",
]

# Expired Firebase user fixture stored in localStorage.
# The ``expirationTime`` (2001-01-01 UTC in ms) is in the past, which causes
# the Firebase SDK to attempt an access-token refresh before resolving
# onAuthStateChanged.  The refresh endpoint is blocked by the route rules,
# which triggers the error callback and sets authError = true in AuthContext.
_EXPIRED_USER_TEMPLATE = {
    "uid": "mytube-395-test-uid",
    "email": "mytube-395-test@example.com",
    "emailVerified": False,
    "isAnonymous": False,
    "providerData": [
        {
            "providerId": "password",
            "uid": "mytube-395-test@example.com",
            "displayName": None,
            "email": "mytube-395-test@example.com",
            "phoneNumber": None,
            "photoURL": None,
        }
    ],
    "stsTokenManager": {
        # A structurally plausible but fake/invalid refresh token.
        # Firebase will attempt to exchange this for a new access token
        # via securetoken.googleapis.com; the blocked network causes failure.
        "refreshToken": "AEu4IL3j_fake_refresh_token_for_mytube_395_testing_only",
        # A fake access token that is structurally invalid (not a real JWT).
        "accessToken": "fake.access.token.mytube395",
        # Expiry in the past: 2001-01-01T00:00:00Z = 978307200000 ms.
        "expirationTime": 978307200000,
    },
    "createdAt": "978307200000",
    "lastLoginAt": "978307200000",
}


# ---------------------------------------------------------------------------
# Helper: Firebase API key discovery
# ---------------------------------------------------------------------------


def _discover_firebase_api_key_from_browser(
    browser: Browser, web_config: WebConfig
) -> Optional[str]:
    """Load the home page once in a clean context and extract the Firebase API key.

    Three strategies are tried in order:
    1. Intercept JS response bodies from the Next.js bundle and scan for the
       ``AIza...`` pattern.  The Firebase API key is a NEXT_PUBLIC env var that
       the build embeds verbatim in an external chunk file.
    2. Intercept outbound requests to googleapis.com and parse the ``key=``
       query parameter (only works if Firebase makes an auth request, which
       requires a cached session).
    3. Scan inline ``<script>`` elements and the webpack module registry via
       page.evaluate() as a last resort.

    Returns the API key string, or None if it cannot be found.
    """
    _AIKEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_-]{35}")
    api_key_ref: dict = {"value": None}

    def _on_response(response) -> None:  # type: ignore[no-untyped-def]
        if api_key_ref["value"]:
            return
        url = response.url
        if ".js" not in url or "_next" not in url:
            return
        try:
            body = response.body().decode("utf-8", errors="ignore")
            m = _AIKEY_PATTERN.search(body)
            if m:
                api_key_ref["value"] = m.group(0)
                _logger.debug("Firebase API key found in JS bundle: %s…", m.group(0)[:8])
        except Exception:
            pass

    def _on_request(request) -> None:  # type: ignore[no-untyped-def]
        if api_key_ref["value"]:
            return
        if "googleapis.com" in request.url:
            try:
                qs = parse_qs(urlparse(request.url).query)
                if "key" in qs and qs["key"]:
                    api_key_ref["value"] = qs["key"][0]
                    _logger.debug("Firebase API key from request param: %s…", qs["key"][0][:8])
            except Exception:
                pass

    context = browser.new_context()
    try:
        page = context.new_page()
        page.set_default_timeout(_DISCOVERY_TIMEOUT_MS)
        page.on("response", _on_response)
        page.on("request", _on_request)

        try:
            page.goto(web_config.home_url(), wait_until="networkidle", timeout=_DISCOVERY_TIMEOUT_MS)
        except Exception as exc:
            _logger.warning("Discovery page load error (non-fatal): %s", exc)

        if api_key_ref["value"]:
            return api_key_ref["value"]

        # Strategy 3: inline scripts and webpack module registry.
        try:
            result = page.evaluate(
                """() => {
                    const pat = /AIza[0-9A-Za-z_-]{35}/;
                    try {
                        const mods = Object.values(window.__webpack_modules__ || {});
                        for (const m of mods) {
                            const s = typeof m === 'function' ? m.toString() : String(m || '');
                            const match = s.match(pat);
                            if (match) return match[0];
                        }
                    } catch (e) {}
                    try {
                        const nd = JSON.stringify(window.__NEXT_DATA__ || {});
                        const match = nd.match(pat);
                        if (match) return match[0];
                    } catch (e) {}
                    try {
                        const scripts = document.querySelectorAll('script:not([src])');
                        for (const s of scripts) {
                            const match = (s.textContent || '').match(pat);
                            if (match) return match[0];
                        }
                    } catch (e) {}
                    return null;
                }"""
            )
            if result:
                _logger.debug("Firebase API key via evaluate: %s…", result[:8])
                return result
        except Exception as exc:
            _logger.warning("evaluate-based scan failed: %s", exc)
    finally:
        context.close()

    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_instance(web_config: WebConfig):
    """Long-lived Chromium browser for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def firebase_api_key(browser_instance: Browser, web_config: WebConfig) -> str:
    """Discover the Firebase API key used by the deployed app.

    Reuses the already-running browser_instance to avoid nested sync_playwright
    context managers (which Playwright forbids inside pytest fixtures).

    If discovery fails the fixture raises pytest.skip so tests are skipped
    rather than erroring with a misleading message.
    """
    key = _discover_firebase_api_key_from_browser(browser_instance, web_config)
    if not key:
        pytest.skip(
            "Could not discover Firebase API key from the deployed app. "
            "The app may not be reachable, or the bundle does not expose the key. "
            f"Tried: {web_config.home_url()}"
        )
    _logger.info("Using Firebase API key: %s…", key[:8])
    return key


def _build_expired_token_init_script(api_key: str) -> str:
    """Return an init script that populates localStorage and speeds up the heartbeat.

    Two things are done before any page scripts run:

    1. Set ``firebase:authUser:<apiKey>:[DEFAULT]`` in localStorage with a
       structurally valid but expired Firebase user object.  The access token
       expiry is set to 2001-01-01 UTC so Firebase detects the token as
       expired and attempts a background refresh via securetoken.googleapis.com.

    2. Override ``window.setInterval`` to replace any interval >= 10 s with
       100 ms.  This accelerates the AuthContext heartbeat probe
       (normally fires every HEARTBEAT_INTERVAL_MS = 120 000 ms) so it runs
       almost immediately.  Within one probe cycle the app calls
       ``user.getIdToken(forceRefresh=true)``; because the network is blocked,
       the request fails and AuthContext sets ``authError = true``.  Without
       this override the test would need to wait 120+ seconds.
    """
    user_payload = dict(_EXPIRED_USER_TEMPLATE)
    ls_key = f"firebase:authUser:{api_key}:[DEFAULT]"
    return f"""
(function() {{
    // 1. Inject expired Firebase session token into localStorage.
    try {{
        localStorage.setItem(
            {json.dumps(ls_key)},
            {json.dumps(json.dumps(user_payload))}
        );
        window.__mytube395_expired_token_injected = true;
    }} catch (e) {{
        window.__mytube395_expired_token_injected = false;
        console.error('[MYTUBE-395] localStorage injection failed:', e);
    }}

    // 2. Accelerate any setInterval with a large delay so that the AuthContext
    //    heartbeat probe fires within ~100 ms instead of 120 000 ms.
    (function() {{
        var _origSetInterval = window.setInterval;
        window.setInterval = function(fn, delay) {{
            var rest = Array.prototype.slice.call(arguments, 2);
            var newDelay = (typeof delay === 'number' && delay >= 10000) ? 100 : delay;
            return _origSetInterval.apply(window, [fn, newDelay].concat(rest));
        }};
    }})();
}})();
"""


@pytest.fixture(scope="function")
def blocked_page(
    browser_instance: Browser,
    web_config: WebConfig,
    firebase_api_key: str,
) -> Page:
    """Yield a Playwright Page with:
    - An expired Firebase session token pre-injected into localStorage.
    - All Firebase auth / token network endpoints aborted (blocked).

    Each test function gets a fresh browser context so state never leaks.
    The page is pre-navigated to home_url before it is yielded.
    """
    context: BrowserContext = browser_instance.new_context()
    context.set_default_timeout(30_000)

    # 1. Inject expired Firebase token before any page scripts execute.
    init_script = _build_expired_token_init_script(firebase_api_key)
    context.add_init_script(script=init_script)

    # 2. Block all Firebase auth and token refresh endpoints.
    for pattern in _FIREBASE_BLOCK_PATTERNS:
        context.route(pattern, lambda route, _req: route.abort("blockedbyclient"))

    pg = context.new_page()
    pg.set_default_timeout(30_000)

    pg.goto(web_config.home_url(), wait_until="domcontentloaded")

    # Confirm the init script ran (sanity check).
    injected = pg.evaluate(
        "() => typeof window.__mytube395_expired_token_injected !== 'undefined' "
        "&& window.__mytube395_expired_token_injected === true"
    )
    if not injected:
        _logger.warning(
            "MYTUBE-395: localStorage injection flag not set. "
            "The expired token may not have been placed correctly."
        )

    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthExpiredTokenBlockedNetwork:
    """MYTUBE-395: With an expired token and blocked Firebase network,
    the app must display an error message — not silently fall back to
    the unauthenticated guest state."""

    # ------------------------------------------------------------------
    # 1. Loading indicator must resolve
    # ------------------------------------------------------------------

    def test_loading_state_resolves(
        self, blocked_page: Page, web_config: WebConfig
    ) -> None:
        """The loading indicator must disappear after Firebase fails to refresh
        the expired token.  A permanent loading state is also a failure.

        Note: ``blocked_page`` is pre-navigated to home_url by the fixture.
        """
        loading = blocked_page.locator(_LOADING_TEXT_SELECTOR)
        try:
            loading.wait_for(state="visible", timeout=5_000)
            loading.wait_for(state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS)
        except Exception:
            pass

        assert not loading.is_visible(), (
            "The application is stuck in a permanent loading state. "
            "Expected the loading indicator to disappear within "
            f"{_LOADING_DISMISS_TIMEOUT_MS} ms after Firebase auth domains "
            "were blocked and an expired token was present in localStorage."
        )

    # ------------------------------------------------------------------
    # 2. Auth error message must be visible
    # ------------------------------------------------------------------

    def test_auth_error_message_displayed(
        self, blocked_page: Page, web_config: WebConfig
    ) -> None:
        """An auth-error alert must be visible once loading resolves.

        Acceptance criteria (any ONE of these satisfies the test):
          - A ``[role="alert"]`` element with non-empty text matching
            auth-unavailability keywords is visible in the header.
          - The rendered body text contains text matching
            ``_AUTH_ERROR_KEYWORDS``.

        The SiteHeader.tsx component renders::

            <span role="alert" …>
              Authentication services are currently unavailable
            </span>

        when ``authError = true`` in AuthContext.

        Note: ``blocked_page`` is pre-navigated to home_url by the fixture.
        """
        # Wait for loading to clear first.
        try:
            blocked_page.locator(_LOADING_TEXT_SELECTOR).wait_for(
                state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS
            )
        except Exception:
            pass

        # Wait for an [role="alert"] element with non-empty text to appear.
        try:
            blocked_page.wait_for_function(
                """() => {
                    const alerts = document.querySelectorAll('[role="alert"]');
                    return Array.from(alerts).some(
                        el => (el.innerText || '').trim().length > 0
                    );
                }""",
                timeout=_ERROR_VISIBILITY_TIMEOUT_MS,
            )
        except Exception:
            pass

        # --- Primary check: SiteHeader auth-error alert ---
        site_header = SiteHeader(blocked_page)
        if site_header.has_auth_error_alert():
            alert_text = site_header.auth_error_alert_text()
            if _AUTH_ERROR_KEYWORDS.search(alert_text):
                return  # PASS

        # --- Secondary check: any [role="alert"] with auth-error keywords ---
        alert_locator = blocked_page.locator("[role='alert']")
        for i in range(alert_locator.count()):
            el = alert_locator.nth(i)
            if not el.is_visible():
                continue
            text = (el.text_content() or "").strip()
            if text and _AUTH_ERROR_KEYWORDS.search(text):
                return  # PASS

        # --- Tertiary check: visible body text ---
        visible_text = blocked_page.locator("body").inner_text()
        specific_patterns = [
            re.compile(r"authentication.*unavail", re.IGNORECASE),
            re.compile(r"auth.*services.*unavail", re.IGNORECASE),
            re.compile(r"services.*unavail", re.IGNORECASE),
        ]
        for pattern in specific_patterns:
            if pattern.search(visible_text):
                return  # PASS

        # --- FAIL: collect diagnostics ---
        page_url = blocked_page.url
        page_title = blocked_page.title()
        visible_snippet = visible_text[:800].replace("\n", " ")

        sign_in_visible = site_header.has_sign_in_link()
        fallback_note = (
            " The app appears to have silently fallen back to the unauthenticated "
            "guest state (Sign-in link is visible) without informing the user that "
            "authentication services are unavailable."
            if sign_in_visible
            else ""
        )

        assert False, (
            "Expected the application to display an auth-error message after "
            "blocking Firebase auth domains with an expired session token in "
            "localStorage, but no such message was found.\n\n"
            f"URL: {page_url}\n"
            f"Page title: {page_title!r}\n"
            f"Page body text (first 800 chars): {visible_snippet!r}\n"
            f"SiteHeader auth-error alert visible: {site_header.has_auth_error_alert()}\n"
            f"SiteHeader auth-error alert text: {site_header.auth_error_alert_text()!r}\n"
            f"Sign-in link visible (silent guest fallback): {sign_in_visible}\n\n"
            "The app should render <span role='alert'> with text "
            "'Authentication services are currently unavailable' in the site "
            "header when the expired token cannot be refreshed."
            + fallback_note
        )

    # ------------------------------------------------------------------
    # 3. No silent fallback to guest state
    # ------------------------------------------------------------------

    def test_no_silent_guest_fallback(
        self, blocked_page: Page, web_config: WebConfig
    ) -> None:
        """The application must NOT silently treat the auth failure as an
        unauthenticated session and show the "Sign in" navigation link.

        If the app shows "Sign in" it means it silently swallowed the error
        and fell back to guest mode, which is the incorrect behaviour this
        test is designed to prevent.

        Note: ``blocked_page`` is pre-navigated to home_url by the fixture.
        """
        # Wait for loading to clear.
        try:
            blocked_page.locator(_LOADING_TEXT_SELECTOR).wait_for(
                state="hidden", timeout=_LOADING_DISMISS_TIMEOUT_MS
            )
        except Exception:
            pass

        # Give any async auth state transition a moment to settle.
        try:
            blocked_page.wait_for_function(
                """() => {
                    const alerts = document.querySelectorAll('[role="alert"]');
                    return Array.from(alerts).some(
                        el => (el.innerText || '').trim().length > 0
                    );
                }""",
                timeout=_ERROR_VISIBILITY_TIMEOUT_MS,
            )
        except Exception:
            pass

        site_header = SiteHeader(blocked_page)
        sign_in_visible = site_header.has_sign_in_link()

        visible_text = blocked_page.locator("body").inner_text()
        has_error = bool(
            site_header.has_auth_error_alert()
            or any(
                p.search(visible_text)
                for p in [
                    re.compile(r"authentication.*unavail", re.IGNORECASE),
                    re.compile(r"auth.*services.*unavail", re.IGNORECASE),
                    re.compile(r"services.*unavail", re.IGNORECASE),
                ]
            )
        )

        assert not sign_in_visible or has_error, (
            "The application displayed a 'Sign in' link (guest state) WITHOUT "
            "also showing an authentication-error message. This indicates a "
            "silent fallback to the unauthenticated state, which violates the "
            "expected behaviour.\n\n"
            f"URL: {blocked_page.url}\n"
            f"Sign-in link visible: {sign_in_visible}\n"
            f"Auth error message found: {has_error}\n"
            f"Auth error alert text: {site_header.auth_error_alert_text()!r}\n\n"
            "Expected: the app shows an error message "
            "'Authentication services are currently unavailable' and does NOT "
            "render the Sign-in link when auth services are unavailable and an "
            "expired session token was present."
        )
