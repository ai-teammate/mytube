"""
MYTUBE-367: Auth status observer failure during active session — error message displayed.

Objective
---------
Verify that the application handles errors from the Firebase authentication state
observer (onAuthStateChanged) that occur after the initial application load, and
that it displays a clear error message instead of silently treating the user as a
guest.

Preconditions
-------------
The application is initially loaded with a successful authentication status.

Steps
-----
1. Load the application successfully (Firebase auth available during initial load).
2. Wait for the auth state to resolve (loading spinner disappears).
3. Block Firebase auth domains (identitytoolkit.googleapis.com,
   securetoken.googleapis.com, *.firebaseapp.com) to simulate a network failure
   or outage occurring AFTER the app has already initialized.
4. Trigger a re-invocation of the auth observer — either by forcing a token
   refresh (when credentials are available) or by injecting a fake session with
   an expired token so Firebase attempts a refresh that fails due to the blocked
   network.
5. Assert that:
   a. "Authentication services are currently unavailable." appears in a
      role="alert" element.
   b. The user is NOT silently transitioned to an unauthenticated guest state
      without notification.

Expected Result
---------------
The application displays "Authentication services are currently unavailable."
The user is informed — NOT silently treated as a guest.

Test approach
-------------
Three modes, tried in order:

**Mode 1 — Authenticated** (FIREBASE_TEST_EMAIL + FIREBASE_TEST_PASSWORD set):
  1. Log in via the login page UI.
  2. Wait for authenticated state.
  3. Block Firebase auth domains.
  4. Wait HEARTBEAT_INTERVAL_MS + HEARTBEAT_PROBE_TIMEOUT_MS + buffer (≈135 s)
     for the periodic heartbeat probe to fire and detect the blocked network.
     The heartbeat (added in MYTUBE-381/MYTUBE-399 fix) calls
     user.getIdToken(forceRefresh=true) every 120 seconds; when that call
     times out (10 s) it sets authError=true.
  5. Assert error message visible in role="alert" element.

**Mode 2 — Fake-session injection** (no credentials, but Firebase API key extractable):
  1. Navigate to the home page (Firebase available → auth resolves to null).
  2. Wait for loading to clear (initial auth cycle completed successfully).
  3. Extract the Firebase API key from the page's bundled JavaScript.
  4. Inject a fake authenticated user into localStorage with an EXPIRED token —
     this simulates "the application was initially loaded with a successful
     authentication status".
  5. Block Firebase auth domains.
  6. Reload the page and wait the full heartbeat window.
     NOTE: Firebase JS SDK v12 fires onAuthStateChanged(null) rather than the
     error callback when the token refresh fails over a blocked network.
     The heartbeat fix only fires when user is non-null; if Firebase briefly
     sets user from localStorage the heartbeat may fire, otherwise this mode
     may not reliably trigger the error on its own.
  7. Assert error message.

**Mode 3 — Fallback** (no credentials, no API key extractable):
  1. Navigate to home page (Firebase available) → initial auth resolves.
  2. Block Firebase auth domains.
  3. Perform a hard page reload while Firebase is blocked.
  4. Assert error message (equivalent to MYTUBE-351 but after a successful
     initial load, demonstrating the error appears on re-initialization too).

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Test user email for authenticated mode.
FIREBASE_TEST_PASSWORD   Test user password for authenticated mode.
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- LoginPage from testing/components/pages/login_page/ handles login interactions.
- Playwright sync API with pytest fixtures (module-scoped browser).
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Firebase auth-related domains to block AFTER initial load.
_FIREBASE_AUTH_PATTERNS = [
    "**/identitytoolkit.googleapis.com/**",
    "**/securetoken.googleapis.com/**",
    "**/*.firebaseapp.com/**",
    "**/firebase.googleapis.com/**",
    "**/googleapis.com/identitytoolkit/**",
]

# How long to wait for the loading spinner to disappear after initial navigation.
_INITIAL_LOAD_TIMEOUT_MS = 20_000

# How long to wait for the auth error message to appear after blocking Firebase.
_ERROR_VISIBILITY_TIMEOUT_MS = 15_000

# -----------------------------------------------------------------------
# Heartbeat timing — must match AuthContext.tsx exported constants.
#
# The MYTUBE-381/MYTUBE-399 fix adds a periodic heartbeat that calls
# user.getIdToken(forceRefresh=true) every HEARTBEAT_INTERVAL_MS ms.
# When Firebase auth domains are blocked mid-session the probe times out
# after HEARTBEAT_PROBE_TIMEOUT_MS ms and sets authError=true.
#
# The test MUST wait at least HEARTBEAT_INTERVAL_MS + HEARTBEAT_PROBE_TIMEOUT_MS
# after blocking Firebase before asserting the error is visible.
# -----------------------------------------------------------------------
_HEARTBEAT_INTERVAL_MS = 120_000   # AuthContext.tsx: HEARTBEAT_INTERVAL_MS
_HEARTBEAT_PROBE_TIMEOUT_MS = 10_000  # AuthContext.tsx: HEARTBEAT_PROBE_TIMEOUT_MS
# Add a 5-second buffer on top of the theoretical maximum detection latency.
_HEARTBEAT_WAIT_MS = _HEARTBEAT_INTERVAL_MS + _HEARTBEAT_PROBE_TIMEOUT_MS + 5_000

# Regex to match the expected auth error text (case-insensitive).
_AUTH_ERROR_KEYWORDS = re.compile(
    r"authentication.*unavail|services.*unavail|unavail.*authentication|"
    r"auth.*unavail|unavail.*auth",
    re.IGNORECASE,
)

# Exact text rendered by SiteHeader.tsx when authError=true.
_EXPECTED_ERROR_TEXT = "Authentication services are currently unavailable"

# CSS selector for the auth error alert rendered by SiteHeader.
_AUTH_ERROR_ALERT_SELECTOR = "[role='alert']"

# The loading text rendered by RequireAuth.tsx / AuthContext consumers.
_LOADING_TEXT = "Loading\u2026"

# Firebase API keys always start with 'AIza' followed by ~35 alphanumeric chars.
_FIREBASE_API_KEY_PATTERN = re.compile(r"AIza[0-9A-Za-z_\-]{35}")


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for_initial_load(page: Page) -> None:
    """Wait for the application's loading state to resolve after initial navigation."""
    loading_locator = page.locator(f"text={_LOADING_TEXT}")
    try:
        loading_locator.wait_for(state="visible", timeout=5_000)
        loading_locator.wait_for(state="hidden", timeout=_INITIAL_LOAD_TIMEOUT_MS)
    except Exception:
        pass


def _block_firebase_auth(context: BrowserContext) -> None:
    """Register abort handlers on the browser context for all Firebase auth domains.

    Call this AFTER the initial page load to simulate a network failure that
    occurs mid-session rather than at application startup.
    """
    for pattern in _FIREBASE_AUTH_PATTERNS:
        context.route(pattern, lambda route, request: route.abort())


def _extract_firebase_api_key(page: Page) -> str | None:
    """Extract the Firebase API key from the page's bundled JavaScript.

    Firebase API keys embedded in Next.js static exports have the 'AIza...'
    format.  We search the page HTML (which includes inline next.js data) and
    any accessible JavaScript bundle URLs already fetched by the browser.
    """
    try:
        api_key: str | None = page.evaluate(
            r"""() => {
                // Firebase API keys have the format 'AIza' + 35 alphanumeric chars.
                const pattern = /AIza[0-9A-Za-z_\-]{35}/;

                // Search inline <script> tags embedded in the page.
                for (const script of document.querySelectorAll('script:not([src])')) {
                    const m = script.textContent.match(pattern);
                    if (m) return m[0];
                }

                // Search the raw HTML of the document (includes __NEXT_DATA__).
                const m = document.documentElement.innerHTML.match(pattern);
                if (m) return m[0];

                return null;
            }"""
        )
        return api_key
    except Exception:
        return None


def _inject_fake_user_session(page: Page, api_key: str) -> None:
    """Inject a fake Firebase auth user into localStorage with an expired token.

    When the page is reloaded, Firebase will find this user in localStorage,
    determine the token is expired, and attempt a network refresh to
    securetoken.googleapis.com.  If Firebase auth domains are blocked at that
    point, the request fails with auth/network-request-failed, which triggers
    the onAuthStateChanged error callback in AuthContext.tsx and sets
    authError=true.

    The fake user object follows the format used by Firebase JS SDK v9+ with
    browserLocalPersistence (window.localStorage).
    """
    fake_user = {
        "uid": "test-uid-mytube-367",
        "email": "test-observer@mytube367.test",
        "emailVerified": False,
        "displayName": "Test Observer",
        "isAnonymous": False,
        "providerData": [
            {
                "uid": "test-observer@mytube367.test",
                "email": "test-observer@mytube367.test",
                "providerId": "password",
                "displayName": None,
                "photoURL": None,
                "phoneNumber": None,
            }
        ],
        # stsTokenManager with an EXPIRED accessToken forces Firebase to attempt
        # a token refresh using the refreshToken when the user is restored.
        "stsTokenManager": {
            "refreshToken": "fake-refresh-token-mytube-367-do-not-use",
            # accessToken is a minimal JWT-shaped string (not valid, just parseable)
            "accessToken": (
                "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9"
                ".eyJzdWIiOiJ0ZXN0LXVpZC1teXR1YmUtMzY3IiwiZXhwIjoxMDAwMDAwMDAwfQ"
                ".fake-signature"
            ),
            # expirationTime in the far past forces immediate refresh attempt.
            "expirationTime": 1_000_000_000_000,
        },
        "lastLoginAt": "1000000000000",
        "createdAt": "1000000000000",
        "apiKey": api_key,
        "appName": "[DEFAULT]",
    }

    storage_key = f"firebase:authUser:{api_key}:[DEFAULT]"
    fake_user_json = json.dumps(fake_user)

    page.evaluate(
        """([key, value]) => {
            try {
                window.localStorage.setItem(key, value);
            } catch (e) {
                console.error('localStorage injection failed:', e);
            }
        }""",
        [storage_key, fake_user_json],
    )


def _assert_auth_error_visible(page: Page, source_url: str) -> None:
    """Assert that the auth-unavailability error message is visible.

    Raises pytest.fail with detailed diagnostics if the message is absent.
    """
    # Poll for a non-empty role=alert element with auth-error text.
    try:
        page.wait_for_function(
            """() => {
                const alerts = document.querySelectorAll('[role="alert"]');
                return Array.from(alerts).some(
                    el => el.innerText && el.innerText.trim().length > 0
                );
            }""",
            timeout=_ERROR_VISIBILITY_TIMEOUT_MS,
        )
    except Exception:
        pass

    # Check all role="alert" elements for non-empty auth-error content.
    alert_locator = page.locator(_AUTH_ERROR_ALERT_SELECTOR)
    for i in range(alert_locator.count()):
        el = alert_locator.nth(i)
        if not el.is_visible():
            continue
        alert_text = (el.text_content() or "").strip()
        if alert_text and _AUTH_ERROR_KEYWORDS.search(alert_text):
            return  # PASS — visible auth-error alert found.

    # Broader search of visible page body text.
    visible_text = page.locator("body").inner_text()
    if _AUTH_ERROR_KEYWORDS.search(visible_text):
        return  # PASS — auth-error text visible somewhere on the page.

    # Failure — collect diagnostics.
    page_title = page.title()
    visible_snippet = visible_text[:600].replace("\n", " ")
    sign_in_visible = (
        page.locator("a[href*='/login']").count() > 0
        or page.get_by_text("Sign in").count() > 0
    )
    loading_stuck = _LOADING_TEXT in visible_text
    silent_fallback_note = ""
    if sign_in_visible:
        silent_fallback_note = (
            " The app silently transitioned to an unauthenticated guest state "
            "(a 'Sign in' link is visible) without informing the user that "
            "authentication services are unavailable."
        )
    elif loading_stuck:
        silent_fallback_note = (
            " The app is stuck in the 'Loading\u2026' state indefinitely — "
            "the auth observer never fired its error callback, so the loading "
            "indicator never cleared and no error message was shown."
        )

    pytest.fail(
        f"Expected the application to display an auth-unavailability error "
        f"message (e.g. '{_EXPECTED_ERROR_TEXT}') after Firebase auth domains "
        f"were blocked DURING an active session, but no such message was found.\n\n"
        f"URL at assertion time: {source_url}\n"
        f"Page title: {page_title!r}\n"
        f"Visible body text (first 600 chars): {visible_snippet!r}\n"
        f"Sign-in link visible (silent unauthenticated fallback): {sign_in_visible}\n"
        f"Stuck in loading state: {loading_stuck}"
        + silent_fallback_note
    )


def _is_auth_error_present(page: Page) -> bool:
    """Return True if an auth-error alert is currently visible on the page."""
    alert_locator = page.locator(_AUTH_ERROR_ALERT_SELECTOR)
    for i in range(alert_locator.count()):
        el = alert_locator.nth(i)
        if el.is_visible():
            t = (el.text_content() or "").strip()
            if t and _AUTH_ERROR_KEYWORDS.search(t):
                return True
    visible_text = page.locator("body").inner_text()
    return bool(_AUTH_ERROR_KEYWORDS.search(visible_text))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthObserverFailureDuringActiveSession:
    """MYTUBE-367: Auth observer error after successful init → error message displayed."""

    def test_auth_error_shown_after_firebase_blocked_mid_session(
        self,
        browser: Browser,
        web_config: WebConfig,
    ) -> None:
        """Blocking Firebase AFTER successful app init must surface an auth-error message.

        Tries three escalating approaches to trigger the onAuthStateChanged error:

        1. Authenticated mode: log in, block Firebase, force token refresh.
        2. Fake-session injection: inject an expired Firebase user session, block
           Firebase, reload — forces a background token refresh that fails and
           triggers the auth observer error callback.
        3. Hard-reload fallback: block Firebase, reload — Firebase SDK re-initialises
           with blocked network and fires the error callback during init.
        """
        context: BrowserContext = browser.new_context()
        context.set_default_timeout(30_000)
        page: Page = context.new_page()
        page.set_default_timeout(30_000)

        try:
            has_credentials = bool(
                web_config.test_email and web_config.test_password
            )

            if has_credentials:
                # ------------------------------------------------------------------
                # Mode 1: Authenticated — log in, block Firebase, force refresh.
                # ------------------------------------------------------------------
                login_page = LoginPage(page)
                login_page.navigate(web_config.login_url())
                _wait_for_initial_load(page)
                login_page.login_as(web_config.test_email, web_config.test_password)

                try:
                    page.wait_for_url(
                        re.compile(r".*/(?:$|\?|#)"),
                        timeout=15_000,
                    )
                except Exception:
                    pass
                _wait_for_initial_load(page)

                # Block Firebase AFTER successful login.
                _block_firebase_auth(context)

                # Attempt to force a token refresh — will fail with network blocked.
                try:
                    page.evaluate(
                        """async () => {
                            try {
                                if (
                                    window.firebase &&
                                    typeof window.firebase.auth === 'function' &&
                                    window.firebase.auth().currentUser
                                ) {
                                    await window.firebase.auth().currentUser.getIdToken(true);
                                }
                            } catch (_) {}
                        }"""
                    )
                except Exception:
                    pass

                # The heartbeat probe fires every HEARTBEAT_INTERVAL_MS (120 s).
                # After each probe fails it waits up to HEARTBEAT_PROBE_TIMEOUT_MS
                # (10 s) for the token refresh to time out.  We must wait the full
                # worst-case detection window before asserting the error.
                page.wait_for_timeout(_HEARTBEAT_WAIT_MS)

            else:
                # ------------------------------------------------------------------
                # Step 1: Load the home page with Firebase AVAILABLE.
                # This satisfies the precondition: "application initially loaded
                # with a successful authentication status."
                # The initial auth resolves cleanly (user=null, loading=false,
                # authError=false) because Firebase is reachable.
                # ------------------------------------------------------------------
                page.goto(web_config.home_url(), wait_until="domcontentloaded")
                _wait_for_initial_load(page)

                # Verify the precondition: no auth error before blocking Firebase.
                initial_text = page.locator("body").inner_text()
                assert not _AUTH_ERROR_KEYWORDS.search(initial_text), (
                    "Auth error message unexpectedly present BEFORE Firebase was "
                    "blocked. Precondition (successful initial load) not met. "
                    f"Visible text: {initial_text[:300]!r}"
                )

                # ------------------------------------------------------------------
                # Step 2: Attempt to extract the Firebase API key so we can inject
                # a fake user session with an expired token.  This allows the test
                # to authentically simulate a mid-session scenario where a signed-in
                # user's token refresh fails because Firebase becomes unavailable.
                # ------------------------------------------------------------------
                api_key = _extract_firebase_api_key(page)

                if api_key:
                    # Mode 2: Fake-session injection.
                    # Inject an expired user session → block Firebase → reload.
                    # Firebase restores the user from localStorage, sees the expired
                    # token, tries a network refresh → request aborted →
                    # auth/network-request-failed → onAuthStateChanged error callback
                    # → authError=true → error message displayed.
                    _inject_fake_user_session(page, api_key)

                    _block_firebase_auth(context)

                    page.reload(wait_until="domcontentloaded")
                    _wait_for_initial_load(page)
                    # Wait the full heartbeat window.  If Firebase briefly
                    # surfaces the stored user before clearing it, the
                    # heartbeat may still fire.
                    page.wait_for_timeout(_HEARTBEAT_WAIT_MS)

                else:
                    # Mode 3: Hard-reload fallback (no API key extractable).
                    # Block Firebase, then reload — Firebase SDK re-initialises with
                    # the network blocked and fires the error callback.
                    _block_firebase_auth(context)

                    page.reload(wait_until="domcontentloaded")
                    _wait_for_initial_load(page)
                    page.wait_for_timeout(15_000)

            # ------------------------------------------------------------------
            # Final assertion: auth-error message MUST be visible.
            # ------------------------------------------------------------------
            _assert_auth_error_visible(page, page.url)

        finally:
            context.close()

    def test_no_silent_guest_fallback_when_auth_fails_mid_session(
        self,
        browser: Browser,
        web_config: WebConfig,
    ) -> None:
        """User must NOT be silently treated as unauthenticated guest when auth fails.

        After a fake authenticated session is established and Firebase is blocked,
        the application must NOT silently fall back to showing only a 'Sign in' link
        with no error message.  The user must be informed that authentication
        services are unavailable.

        This test focuses on the *absence* of the silent-fallback anti-pattern.
        When real credentials are available the test uses Mode 1 (authenticated
        heartbeat path) for deterministic results; otherwise it falls back to
        fake-session injection.
        """
        context: BrowserContext = browser.new_context()
        context.set_default_timeout(30_000)
        page: Page = context.new_page()
        page.set_default_timeout(30_000)

        try:
            has_credentials = bool(
                web_config.test_email and web_config.test_password
            )

            if has_credentials:
                # Mode 1: authenticated heartbeat path (same as test 1).
                # After the heartbeat probe fails the header must show the
                # auth-error alert, NOT silently degrade to a guest state.
                login_page = LoginPage(page)
                login_page.navigate(web_config.login_url())
                _wait_for_initial_load(page)
                login_page.login_as(web_config.test_email, web_config.test_password)

                try:
                    page.wait_for_url(
                        re.compile(r".*/(?:$|\?|#)"),
                        timeout=15_000,
                    )
                except Exception:
                    pass
                _wait_for_initial_load(page)

                _block_firebase_auth(context)

                # Wait for the heartbeat to fire and detect the blocked network.
                page.wait_for_timeout(_HEARTBEAT_WAIT_MS)

            else:
                # Step 1: Load home page successfully (Firebase reachable).
                page.goto(web_config.home_url(), wait_until="domcontentloaded")
                _wait_for_initial_load(page)

                # Step 2: Extract Firebase API key and inject fake session.
                api_key = _extract_firebase_api_key(page)
                if api_key:
                    _inject_fake_user_session(page, api_key)

                # Step 3: Block Firebase auth domains mid-session.
                _block_firebase_auth(context)

                # Step 4: Reload to trigger the auth cycle with Firebase blocked.
                page.reload(wait_until="domcontentloaded")
                _wait_for_initial_load(page)
                page.wait_for_timeout(_HEARTBEAT_WAIT_MS)

            # ------------------------------------------------------------------
            # Assertion: if a 'Sign in' link is visible, an auth-error message
            # MUST also be visible — the app must not silently fall back.
            # ------------------------------------------------------------------
            visible_text = page.locator("body").inner_text()
            sign_in_visible = (
                page.locator("a[href*='/login']").count() > 0
                or page.get_by_text("Sign in").count() > 0
            )
            has_auth_error = _AUTH_ERROR_KEYWORDS.search(visible_text)

            if sign_in_visible and not has_auth_error:
                pytest.fail(
                    "The application silently fell back to an unauthenticated guest "
                    "state after Firebase was blocked during an active session, "
                    "without displaying any authentication-error notification. "
                    "A 'Sign in' link is visible, but no auth-error message is present.\n\n"
                    f"URL: {page.url}\n"
                    f"Visible body (first 400 chars): {visible_text[:400]!r}\n\n"
                    "Expected: an element with role='alert' containing text such as "
                    f"'{_EXPECTED_ERROR_TEXT}' to be visible alongside or instead of "
                    "the Sign in link."
                )

        finally:
            context.close()
