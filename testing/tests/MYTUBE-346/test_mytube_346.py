"""
MYTUBE-346: Navigate between pages — global layout remains consistent.

Objective
---------
Ensure the Layout wrapper (AppShell) maintains consistent structure and shell
across different routes.  The header and footer must remain static and visible
when transitioning from the homepage (/) to the Playlists page (/dashboard),
and the main content area must preserve consistent margins and container
structure on both pages.

Steps
-----
1. Navigate to the homepage (/).
2. Assert the <header> is visible; record its bounding box.
3. Assert the <footer> is visible; record its bounding box.
4. Use the primary navigation "Playlists" link to navigate to /dashboard.
5. Assert the <header> is still visible after the transition.
6. Assert the <footer> is still visible after the transition.
7. Assert the header bounding box (position, width) is the same as on the
   homepage — confirming the header did not move or resize.
8. Assert the footer width is the same as on the homepage and the footer
   remains anchored to the bottom of the content.
9. Assert the <main> element carries the ``flex-1`` class on both pages,
   confirming consistent main-content-area margins.

Expected Result
---------------
Header and footer remain static and visible during the transition; the
<main> content area maintains ``flex-1`` on both routes.

Note: The footer y-position naturally varies between pages because the
AppShell uses a ``min-h-screen flex flex-col`` layout where the footer
is pushed to the bottom of the content (not sticky).  What must remain
consistent is visibility, full-width span, and the header's fixed position.

Prerequisites
-------------
The "Playlists" navigation link in SiteHeader is only rendered for
authenticated users (``{user && ...}``).  This test injects a Firebase ID
token into localStorage to authenticate without the login form.

Firebase ID tokens are obtained via the REST Identity Toolkit API using
FIREBASE_TEST_EMAIL, FIREBASE_TEST_PASSWORD, and FIREBASE_API_KEY.
The test is skipped gracefully when any of these env vars is absent.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web application.
                        Default: https://ai-teammate.github.io/mytube
FIREBASE_API_KEY        Firebase Web API key (required for token injection).
FIREBASE_TEST_EMAIL     Email of the registered Firebase test user (required).
FIREBASE_TEST_PASSWORD  Password for the test user (required).
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses HomePage Page Object from testing/components/pages/home_page/.
- WebConfig from testing/core/config/web_config.py manages env vars.
- Firebase auth state is injected via localStorage (no login form needed).
- Playwright sync API; no hardcoded URLs, credentials, or sleeps.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

import pytest
import requests
from playwright.sync_api import sync_playwright, Browser, Page, expect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.home_page.home_page import HomePage

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_AUTH_PROPAGATION_TIMEOUT = 10_000  # ms — time for auth state to populate React context
_SETTLE_MS = 2_000            # ms — time to let auth state propagate after reload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _bounding_box_equal(a: Optional[dict], b: Optional[dict], tolerance: int = 2) -> bool:
    """Return True if two bounding boxes share the same x, width within tolerance px."""
    if a is None or b is None:
        return False
    return (
        abs(a["x"] - b["x"]) <= tolerance
        and abs(a["width"] - b["width"]) <= tolerance
    )


def _get_firebase_token(api_key: str, email: str, password: str) -> dict:
    """Obtain a Firebase ID token via the REST Identity Toolkit API.

    Returns a dict with keys: idToken, refreshToken, localId (UID).
    Raises requests.HTTPError if sign-in fails.
    """
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        f"?key={api_key}"
    )
    resp = requests.post(
        url,
        json={"email": email, "password": password, "returnSecureToken": True},
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()


def _inject_firebase_auth(page: Page, api_key: str, email: str, token_data: dict) -> None:
    """Inject Firebase auth state into the page's localStorage.

    The Firebase JS SDK (v9/10) reads auth state from localStorage under the
    key ``firebase:authUser:<apiKey>:[DEFAULT]``.  Injecting a well-formed
    user object here causes the AuthContext to recognise the user on next load.
    """
    storage_key = f"firebase:authUser:{api_key}:[DEFAULT]"
    user_obj = {
        "uid": token_data["localId"],
        "email": email,
        "emailVerified": True,
        "displayName": "CI Test User",
        "isAnonymous": False,
        "providerData": [
            {
                "providerId": "password",
                "uid": email,
                "displayName": None,
                "email": email,
                "phoneNumber": None,
                "photoURL": None,
            }
        ],
        "stsTokenManager": {
            "refreshToken": token_data["refreshToken"],
            "accessToken": token_data["idToken"],
            "expirationTime": 9_999_999_999_999,
        },
        "createdAt": "1000000000000",
        "lastLoginAt": "1000000000000",
        "apiKey": api_key,
        "appName": "[DEFAULT]",
    }
    page.evaluate(
        f"""() => {{ localStorage.setItem({json.dumps(storage_key)}, {json.dumps(json.dumps(user_obj))}); }}"""
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def firebase_api_key() -> str:
    """Return the Firebase Web API key from environment."""
    key = os.environ.get("FIREBASE_API_KEY", "")
    if not key:
        pytest.skip(
            "FIREBASE_API_KEY is not set — skipping layout-consistency test."
        )
    return key


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig, firebase_api_key: str) -> None:
    """Skip the entire module when Firebase test credentials are not provided."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL is not set — skipping layout-consistency test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD is not set — skipping layout-consistency test."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def authenticated_page(
    browser: Browser,
    web_config: WebConfig,
    firebase_api_key: str,
) -> Page:
    """Open a browser context with Firebase auth injected into localStorage.

    Uses the Firebase Identity Toolkit REST API to obtain a valid ID token,
    then injects the token into the page's localStorage so the React app
    recognises the user without going through the login form.

    The fixture also waits for the auth-gated 'Playlists' nav link to become
    visible, confirming that auth state has fully propagated before tests run.
    All tests in this module share this authenticated session.
    """
    token_data = _get_firebase_token(
        firebase_api_key,
        web_config.test_email,
        web_config.test_password,
    )

    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Navigate to the app to establish the origin for localStorage.
    pg.goto(web_config.base_url + "/", wait_until="domcontentloaded")

    # Inject Firebase auth state and reload so AuthContext picks it up.
    _inject_firebase_auth(pg, firebase_api_key, web_config.test_email, token_data)
    pg.reload(wait_until="domcontentloaded")

    # Wait for the auth-conditional Playlists link to confirm auth is ready.
    playlists_link = pg.locator(
        "nav[aria-label='Primary navigation'] a:has-text('Playlists')"
    )
    expect(playlists_link).to_be_visible(timeout=_AUTH_PROPAGATION_TIMEOUT)

    yield pg
    context.close()


@pytest.fixture(scope="module")
def home_page(authenticated_page: Page) -> HomePage:
    return HomePage(authenticated_page)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLayoutConsistencyAcrossNavigation:
    """MYTUBE-346: Layout wrapper maintains consistent header/footer shell across routes."""

    # --- Step 1 & 2: homepage layout ----------------------------------------

    def test_header_visible_on_homepage(
        self, home_page: HomePage, web_config: WebConfig
    ) -> None:
        """Steps 1–2a — navigate to homepage and assert <header> is visible."""
        home_page.navigate(web_config.base_url)

        # Wait for auth-gated elements (Playlists) to ensure auth state is ready.
        expect(
            home_page._page.locator(
                "nav[aria-label='Primary navigation'] a:has-text('Playlists')"
            )
        ).to_be_visible(timeout=_AUTH_PROPAGATION_TIMEOUT)

        header = home_page._page.locator("header")
        expect(header).to_be_visible()

    def test_footer_visible_on_homepage(
        self, home_page: HomePage
    ) -> None:
        """Step 2b — <footer> is present and visible on the homepage."""
        footer = home_page._page.locator("footer")
        expect(footer).to_be_visible()

    def test_main_has_flex1_on_homepage(self, home_page: HomePage) -> None:
        """Step 9a — <main> carries the flex-1 class on the homepage."""
        main_el = home_page._page.locator("main")
        class_attr = main_el.get_attribute("class") or ""
        assert "flex-1" in class_attr, (
            "Expected the <main> element on the homepage to have the 'flex-1' class "
            "(set by AppShell), which ensures consistent main-content-area layout. "
            f"Actual class attribute: {class_attr!r}"
        )

    # --- Step 3: Playlists nav link visible ----------------------------------

    def test_playlists_nav_link_is_visible(self, home_page: HomePage) -> None:
        """Precondition for Step 3 — the 'Playlists' nav link is visible to an authenticated user."""
        playlists_link = home_page._page.locator(
            "nav[aria-label='Primary navigation'] a:has-text('Playlists')"
        )
        expect(playlists_link).to_be_visible(timeout=_AUTH_PROPAGATION_TIMEOUT)

    # --- Steps 3–9: navigate to Playlists and verify layout -----------------

    def test_layout_consistent_after_navigating_to_playlists(
        self, home_page: HomePage, web_config: WebConfig
    ) -> None:
        """Steps 3–9 — header and footer remain visible and anchored after navigation.

        Records the header and footer bounding boxes on the homepage, then
        clicks the 'Playlists' navigation link, and asserts that:
        - Both elements remain visible on the destination page.
        - Header x position and width are unchanged (static header).
        - Footer x position and width are unchanged (always full-width).

        NOTE: Footer y-position naturally differs between pages because the
        AppShell uses a flex column layout where the footer is pushed to the
        bottom of the content, not fixed/sticky.  Therefore y is NOT asserted
        to be identical — only x and width consistency is verified.
        """
        page = home_page._page

        # Ensure we start on the homepage with auth loaded.
        home_page.navigate(web_config.base_url)
        expect(
            page.locator("nav[aria-label='Primary navigation'] a:has-text('Playlists')")
        ).to_be_visible(timeout=_AUTH_PROPAGATION_TIMEOUT)

        header_loc = page.locator("header")
        footer_loc = page.locator("footer")

        # Step 2: record bounding boxes before navigation.
        header_box_before: Optional[dict] = header_loc.bounding_box()
        footer_box_before: Optional[dict] = footer_loc.bounding_box()

        assert header_box_before is not None, (
            "Could not obtain bounding box for <header> on the homepage. "
            "Ensure the header element is rendered and visible."
        )
        assert footer_box_before is not None, (
            "Could not obtain bounding box for <footer> on the homepage. "
            "Ensure the footer element is in the viewport."
        )

        # Step 3: click the Playlists nav link.
        playlists_link = page.locator(
            "nav[aria-label='Primary navigation'] a:has-text('Playlists')"
        )
        playlists_link.click()
        page.wait_for_load_state("domcontentloaded")

        # Steps 4–5: header still visible after transition.
        expect(header_loc).to_be_visible()

        # Step 6: footer still visible after transition.
        expect(footer_loc).to_be_visible()

        # Step 7: header x and width unchanged (it must stay at the top full-width).
        header_box_after: Optional[dict] = header_loc.bounding_box()
        assert _bounding_box_equal(header_box_before, header_box_after), (
            "The <header> changed its x position or width after navigating to Playlists. "
            f"Before: x={header_box_before.get('x')}, width={header_box_before.get('width')}. "
            f"After:  x={header_box_after.get('x') if header_box_after else 'N/A'}, "
            f"width={header_box_after.get('width') if header_box_after else 'N/A'}. "
            "The header should maintain the same horizontal span across all routes."
        )

        # Step 8: footer x and width unchanged (full-width on both pages).
        footer_box_after: Optional[dict] = footer_loc.bounding_box()
        assert _bounding_box_equal(footer_box_before, footer_box_after), (
            "The <footer> changed its x position or width after navigating to Playlists. "
            f"Before: x={footer_box_before.get('x')}, width={footer_box_before.get('width')}. "
            f"After:  x={footer_box_after.get('x') if footer_box_after else 'N/A'}, "
            f"width={footer_box_after.get('width') if footer_box_after else 'N/A'}. "
            "The footer should maintain full-width span across all routes."
        )

    def test_main_has_flex1_on_playlists_page(self, home_page: HomePage) -> None:
        """Step 9b — <main> retains the flex-1 class after navigating to the Playlists page."""
        main_el = home_page._page.locator("main")
        class_attr = main_el.get_attribute("class") or ""
        assert "flex-1" in class_attr, (
            "Expected the <main> element on the Playlists/Dashboard page to retain "
            "the 'flex-1' class (set by AppShell), ensuring consistent content-area "
            f"layout. Actual class attribute: {class_attr!r}. "
            f"Current URL: {home_page.current_url()}"
        )

    def test_navigated_to_dashboard_url(
        self, home_page: HomePage, web_config: WebConfig
    ) -> None:
        """After clicking 'Playlists', the URL must contain /dashboard."""
        current = home_page.current_url().rstrip("/")
        assert "/dashboard" in current, (
            f"Expected the 'Playlists' nav link to navigate to a URL containing "
            f"'/dashboard', but the current URL is '{current}'. "
            "Check the href attribute of the Playlists <Link> in SiteHeader.tsx."
        )
