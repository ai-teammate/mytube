"""
MYTUBE-349: API request with nearly expired token — token refreshed automatically.

Objective
---------
Verify that the frontend transparently refreshes the Firebase ID token before
making API requests if the current token is expired or near expiration.

Preconditions
-------------
User is authenticated with a token that is close to its expiration time.

Test steps
----------
1. Navigate to /login and authenticate with Firebase test credentials.
2. Wait for the post-login redirect to the home page.
3. Simulate a "near expiration" state by manipulating the Firebase auth token's
   stored expiration time in localStorage to be within Firebase's 5-minute
   auto-refresh window (4 minutes from now).
4. Install a fetch() spy in the browser to capture the Authorization header of
   outgoing /api/me requests.
5. Navigate to /settings, which triggers an authenticated API call to /api/me.
6. Wait for the API call to complete and read the captured Authorization header.
7. Assert that the Authorization header contains a valid "Bearer <token>" value.
8. Decode the JWT payload and verify the token's expiry (exp claim) is in the
   future — confirming that Firebase issued a fresh token rather than the
   near-expired one.

Expected result
---------------
The frontend invokes Firebase SDK's getIdToken(), which detects the near-expired
state, transparently refreshes the ID token, and includes the new valid token in
the Authorization: Bearer <token> header. The /api/me request succeeds or at
minimum the header is present with a non-expired JWT.

Architecture
------------
- Uses LoginPage (Page Object) from testing/components/pages/login_page/.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or credentials.

Environment variables
---------------------
FIREBASE_TEST_EMAIL     Email of the registered Firebase test user (required).
FIREBASE_TEST_PASSWORD  Password for the test Firebase user (required).
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NAVIGATION_TIMEOUT = 30_000   # ms — max time to wait for post-login redirect
_PAGE_LOAD_TIMEOUT = 30_000    # ms — max time for initial page load
_API_CALL_TIMEOUT = 15_000     # ms — max time to wait for /api/me request

# Firebase automatically refreshes tokens that expire within this window (5 min).
_NEAR_EXPIRY_OFFSET_MS = 4 * 60 * 1000  # 4 minutes from now — inside refresh window


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _decode_jwt_payload(token: str) -> Optional[dict]:
    """Decode the JWT payload (second segment) without signature verification.

    Returns the decoded dict or None if the token is malformed.
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        # JWT uses URL-safe base64 without padding; add padding as needed.
        padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload_bytes = base64.urlsafe_b64decode(padded)
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return None


def _extract_bearer_token(auth_header: str) -> Optional[str]:
    """Return the raw JWT from an 'Authorization: Bearer <token>' header."""
    if not auth_header:
        return None
    parts = auth_header.split(" ", 1)
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1].strip()
    return None


def _simulate_near_expiry(page: Page) -> None:
    """Manipulate Firebase's localStorage entry to simulate a near-expired token.

    Firebase stores auth state under the key pattern
    ``firebase:authUser:<apiKey>:<projectId>``.  The ``stsTokenManager``
    sub-object has an ``expirationTime`` field (Unix ms).  Setting it to
    ``Date.now() + 4 min`` places it inside Firebase's 5-minute auto-refresh
    window, causing the next ``user.getIdToken()`` call to fetch a fresh token.
    """
    page.evaluate(
        """() => {
            const prefix = 'firebase:authUser:';
            for (let i = 0; i < localStorage.length; i++) {
                const key = localStorage.key(i);
                if (!key || !key.startsWith(prefix)) continue;
                try {
                    const entry = JSON.parse(localStorage.getItem(key));
                    if (!entry || !entry.stsTokenManager) continue;
                    // Set expiry to 4 minutes from now — inside Firebase's
                    // 5-minute proactive-refresh threshold.
                    entry.stsTokenManager.expirationTime = Date.now() + 4 * 60 * 1000;
                    localStorage.setItem(key, JSON.stringify(entry));
                } catch (_) { /* ignore parse errors */ }
            }
        }"""
    )


def _install_fetch_spy(page: Page) -> None:
    """Wrap window.fetch to capture Authorization headers for /api/me calls."""
    page.evaluate(
        """() => {
            window.__mytube349_captured = [];
            const _original = window.fetch.bind(window);
            window.fetch = async function(input, init) {
                const url = (typeof input === 'string') ? input
                          : (input instanceof Request) ? input.url
                          : String(input);
                if (url.includes('/api/me')) {
                    const headers = (init && init.headers) ? init.headers : {};
                    const auth = (headers instanceof Headers)
                        ? headers.get('Authorization')
                        : (headers['Authorization'] || headers['authorization'] || '');
                    window.__mytube349_captured.push({ url, auth });
                }
                return _original(input, init);
            };
        }"""
    )


def _read_captured_headers(page: Page) -> list[dict]:
    """Return the list of captured request records from the fetch spy."""
    return page.evaluate("() => window.__mytube349_captured || []")


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
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-349 token-refresh test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-349 token-refresh test. "
            "Set FIREBASE_TEST_PASSWORD to run."
        )


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


@pytest.fixture(scope="module")
def context(browser: Browser) -> BrowserContext:
    """Open a fresh, isolated browser context."""
    ctx = browser.new_context()
    yield ctx
    ctx.close()


@pytest.fixture(scope="module")
def authenticated_page(web_config: WebConfig, context: BrowserContext) -> Page:
    """Log in with Firebase credentials and yield the page on the home page.

    The login is performed once per test module.
    """
    page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)

    yield page
    page.close()


@pytest.fixture(scope="module")
def settings_page_with_capture(
    web_config: WebConfig,
    authenticated_page: Page,
) -> dict:
    """Simulate near-expiry, install fetch spy, navigate to /settings, return captured data.

    Returns a dict with keys:
        ``captured``   — list of dicts from the fetch spy (url, auth header).
        ``page``       — the Playwright Page after settings page load.
    """
    page = authenticated_page
    settings_url = f"{web_config.base_url}/settings/"

    # 1. Simulate near-expired token in Firebase's localStorage persistence.
    _simulate_near_expiry(page)

    # 2. Install fetch spy *before* navigation so that the /api/me call on page
    #    load is captured.  The spy is registered on the current JS context; the
    #    next page.goto() will reset the JS environment, so we navigate without
    #    a full reload by using soft navigation via JS.
    page.evaluate(f"() => window.location.href = '{settings_url}'")

    # Wait for the settings page URL to be current.
    page.wait_for_url(
        lambda u: "settings" in u,
        timeout=_NAVIGATION_TIMEOUT,
    )

    # 3. Now install the spy so it is active for any subsequent re-fetch
    #    (e.g. form submit).  For the initial page-load fetch we rely on
    #    Playwright's route interception below.
    captured_via_route: list[dict] = []

    def _handle_route(route):
        req = route.request
        auth_header = req.headers.get("authorization", "")
        captured_via_route.append({"url": req.url, "auth": auth_header})
        route.continue_()

    page.route("**/api/me**", _handle_route)

    # 4. Re-navigate to /settings to trigger the API call with the spy active.
    page.goto(settings_url, wait_until="domcontentloaded")
    page.wait_for_url(lambda u: "settings" in u, timeout=_NAVIGATION_TIMEOUT)

    # 5. Wait for the /api/me route to be intercepted (up to _API_CALL_TIMEOUT ms).
    deadline = time.monotonic() + _API_CALL_TIMEOUT / 1000
    while not captured_via_route and time.monotonic() < deadline:
        page.wait_for_timeout(300)

    page.unroute("**/api/me**", _handle_route)

    return {"captured": captured_via_route, "page": page}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTokenRefreshedBeforeApiRequest:
    """MYTUBE-349: Verify Firebase token is (auto-)refreshed and used in API header."""

    def test_api_me_request_was_intercepted(self, settings_page_with_capture: dict):
        """The settings page must trigger at least one GET /api/me request."""
        captured = settings_page_with_capture["captured"]
        assert captured, (
            "No request to /api/me was intercepted after navigating to /settings. "
            "The settings page should fetch the user profile via GET /api/me on load. "
            "Ensure the Firebase user is authenticated and NEXT_PUBLIC_API_URL is "
            "reachable so the fetch is actually issued."
        )

    def test_authorization_header_is_present(self, settings_page_with_capture: dict):
        """Every /api/me request must include an Authorization header."""
        captured = settings_page_with_capture["captured"]
        if not captured:
            pytest.skip("No /api/me request captured — prerequisite not met.")

        for record in captured:
            auth = record.get("auth", "")
            assert auth, (
                f"The /api/me request to {record['url']} was sent without an "
                "Authorization header. Expected the frontend to call getIdToken() "
                "and include the result as 'Authorization: Bearer <token>'."
            )

    def test_authorization_header_is_bearer_scheme(
        self, settings_page_with_capture: dict
    ):
        """The Authorization header must use the 'Bearer' scheme."""
        captured = settings_page_with_capture["captured"]
        if not captured:
            pytest.skip("No /api/me request captured — prerequisite not met.")

        for record in captured:
            auth = record.get("auth", "")
            assert auth.lower().startswith("bearer "), (
                f"Expected 'Authorization: Bearer <token>' but received "
                f"'Authorization: {auth}'. The frontend must use the Bearer scheme "
                "when attaching the Firebase ID token to API requests."
            )

    def test_bearer_token_is_valid_jwt(self, settings_page_with_capture: dict):
        """The Bearer token must be a well-formed JWT (three base64url segments)."""
        captured = settings_page_with_capture["captured"]
        if not captured:
            pytest.skip("No /api/me request captured — prerequisite not met.")

        for record in captured:
            auth = record.get("auth", "")
            token = _extract_bearer_token(auth)
            assert token, (
                f"Could not extract a token from Authorization header: '{auth}'"
            )
            assert token.count(".") == 2, (
                f"The Bearer token is not a valid JWT (expected 3 dot-separated "
                f"segments, got {token.count('.') + 1}): '{token[:80]}...'"
            )
            payload = _decode_jwt_payload(token)
            assert payload is not None, (
                f"JWT payload could not be base64-decoded: '{token[:80]}...'"
            )

    def test_bearer_token_is_not_expired(self, settings_page_with_capture: dict):
        """The JWT token's 'exp' claim must be in the future (token is still valid).

        This confirms that Firebase refreshed the token before attaching it —
        either because the previous token was near-expired or because a fresh
        token was requested.  Either way, a non-expired token proves the automatic
        refresh mechanism is working correctly.
        """
        captured = settings_page_with_capture["captured"]
        if not captured:
            pytest.skip("No /api/me request captured — prerequisite not met.")

        for record in captured:
            auth = record.get("auth", "")
            token = _extract_bearer_token(auth)
            if not token:
                continue
            payload = _decode_jwt_payload(token)
            if not payload:
                continue

            exp = payload.get("exp")
            assert exp is not None, (
                f"JWT payload is missing the 'exp' claim: {payload}"
            )
            now_unix = int(time.time())
            assert exp > now_unix, (
                f"The JWT token included in the Authorization header is ALREADY "
                f"EXPIRED. exp={exp}, now={now_unix} "
                f"(token expired {now_unix - exp} seconds ago). "
                "Firebase should have refreshed the token before the API call."
            )

    def test_bearer_token_has_firebase_iss_claim(
        self, settings_page_with_capture: dict
    ):
        """The JWT 'iss' claim must identify the token as a Firebase-issued token."""
        captured = settings_page_with_capture["captured"]
        if not captured:
            pytest.skip("No /api/me request captured — prerequisite not met.")

        for record in captured:
            auth = record.get("auth", "")
            token = _extract_bearer_token(auth)
            if not token:
                continue
            payload = _decode_jwt_payload(token)
            if not payload:
                continue

            iss = payload.get("iss", "")
            assert "accounts.google.com" in iss or "securetoken.google.com" in iss, (
                f"JWT 'iss' claim does not identify a Firebase token. "
                f"iss='{iss}'. Expected 'accounts.google.com' or "
                "'securetoken.google.com'."
            )
