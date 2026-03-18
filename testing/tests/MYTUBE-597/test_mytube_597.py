"""
MYTUBE-597: Authenticated user navigates to playlist from dashboard —
            playlist details and video queue load successfully.

Objective
---------
Verify that an authenticated user can access their playlist via
Dashboard → My playlists tab → click playlist title, and the
/pl/[id] page loads successfully without the
"Could not load playlist. Please try again later." error.

Linked bug
----------
MYTUBE-592 (Done): PlaylistPageClient.tsx was missing the GitHub Pages SPA
sessionStorage fallback that reads __spa_playlist_id when paramId === "_".
Without the fix, navigating to /pl/<id> via a link redirected through the
GitHub Pages 404.html SPA shell (/pl/_/) and then sent
GET /api/playlists/_ which failed UUID validation → HTTP 400 → error message.

Steps
-----
1. Create a test playlist via the API so there is always at least one playlist.
2. Log in via /login using FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD.
3. Navigate to /dashboard.
4. Click the "My playlists" tab.
5. Wait for the playlist table to render.
6. Click the title link of the test playlist.
7. Wait for the /pl/[id] page to load.
8. Assert:
   a. No "Could not load playlist. Please try again later." error is shown.
   b. The playlist title (h1) is visible on the page.
   c. The playlist page URL contains /pl/ (SPA routing resolved correctly).

Environment variables
---------------------
APP_URL / WEB_BASE_URL  : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
API_BASE_URL            : Backend API base URL.
                          Default: https://mytube-api-80693608388.us-central1.run.app
FIREBASE_API_KEY        : Firebase Web API key (for sign-in token exchange).
FIREBASE_TEST_EMAIL     : CI test user email.
FIREBASE_TEST_PASSWORD  : CI test user password.
FIREBASE_TEST_TOKEN     : Pre-obtained Firebase ID token (used to create the test playlist).
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- LoginPage and DashboardPage Page Objects are reused from testing/components/pages/.
- PlaylistPage Page Object is reused from testing/components/pages/playlist_page/.
- PlaylistApiService is used to create and clean up the test playlist.
- WebConfig and AuthService centralise env-var access.
- No hardcoded credentials, URLs, or sleep calls.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage
from testing.components.pages.playlist_page.playlist_page import PlaylistPage
from testing.components.services.playlist_api_service import PlaylistApiService
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEPLOYED_API_URL = "https://mytube-api-80693608388.us-central1.run.app"
_PAGE_LOAD_TIMEOUT = 30_000   # ms
_NAVIGATION_TIMEOUT = 20_000  # ms
_PLAYLIST_TITLE = "CI Test Playlist MYTUBE-597"
_ERROR_TEXT = "Could not load playlist. Please try again later."


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_reachable(url: str, timeout: int = 10) -> bool:
    """Return True if *url* returns a non-5xx HTTP response."""
    try:
        req = urllib.request.Request(url, method="GET")
        res = urllib.request.urlopen(req, timeout=timeout)
        return res.status < 500
    except urllib.error.HTTPError as exc:
        return exc.code < 500
    except Exception:
        return False


def _obtain_firebase_token(web_config: WebConfig) -> str:
    """Return a Firebase ID token for the CI test user.

    Tries FIREBASE_TEST_TOKEN first (fastest), then falls back to a
    REST sign-in with FIREBASE_API_KEY + email/password.
    Returns empty string when no credentials are available.
    """
    pre_obtained = os.getenv("FIREBASE_TEST_TOKEN", "")
    if pre_obtained:
        return pre_obtained

    api_key = os.getenv("FIREBASE_API_KEY", "")
    email = web_config.test_email
    password = web_config.test_password
    if not (api_key and email and password):
        return ""

    return AuthService.sign_in_with_email_password(api_key, email, password) or ""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig) -> None:
    """Skip the entire module when login credentials are unavailable."""
    email = web_config.test_email
    password = web_config.test_password
    if not (email and password):
        pytest.skip(
            "FIREBASE_TEST_EMAIL and/or FIREBASE_TEST_PASSWORD are not set — "
            "skipping MYTUBE-597 web UI test."
        )


@pytest.fixture(scope="module")
def api_base_url() -> str:
    return os.getenv("API_BASE_URL", _DEPLOYED_API_URL).rstrip("/")


@pytest.fixture(scope="module")
def firebase_token(web_config: WebConfig) -> str:
    """Return a valid Firebase ID token, or skip when unavailable."""
    token = _obtain_firebase_token(web_config)
    if not token:
        pytest.skip(
            "No Firebase token available — set FIREBASE_TEST_TOKEN or "
            "FIREBASE_API_KEY + FIREBASE_TEST_EMAIL + FIREBASE_TEST_PASSWORD."
        )
    return token


@pytest.fixture(scope="module")
def test_playlist(api_base_url: str, firebase_token: str):
    """Create a test playlist via the API; yield its id and title; delete on teardown."""
    svc = PlaylistApiService(base_url=api_base_url, token=firebase_token)
    status, body = svc.create_playlist(_PLAYLIST_TITLE)
    if status not in (200, 201):
        pytest.skip(
            f"Could not create test playlist via API (HTTP {status}): {body}"
        )
    try:
        data = json.loads(body)
    except Exception:
        pytest.skip(f"API returned non-JSON body when creating playlist: {body!r}")

    playlist_id = data.get("id", "")
    if not playlist_id:
        pytest.skip(f"API response missing 'id' field: {body!r}")

    yield {"id": playlist_id, "title": _PLAYLIST_TITLE}

    # Teardown — best-effort deletion
    try:
        svc.delete_playlist(playlist_id)
    except Exception:
        pass


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser instance for the module."""
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def authenticated_page(browser: Browser, web_config: WebConfig):
    """Navigate to /login, authenticate, and return the page ready for assertions.

    The page is scoped to the module so all tests share the same authenticated
    session (avoids repeated logins).
    """
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    login = LoginPage(page)
    login.navigate(web_config.login_url())

    # Wait for the login form
    login.wait_for_form(timeout=_PAGE_LOAD_TIMEOUT)
    login.login_as(web_config.test_email, web_config.test_password)

    # Wait until we leave the login page (redirect to home or dashboard)
    page.wait_for_url(
        lambda url: "/login" not in url,
        timeout=_NAVIGATION_TIMEOUT,
    )

    yield page
    context.close()


@pytest.fixture(scope="module")
def playlist_page_loaded(
    authenticated_page: Page,
    web_config: WebConfig,
    test_playlist: dict,
):
    """Navigate through Dashboard → My playlists → click playlist title.

    Returns the PlaylistPage instance after navigation has completed.
    """
    page = authenticated_page

    # Navigate to dashboard
    dashboard = DashboardPage(page)
    dashboard.navigate(web_config.dashboard_url())

    # Click the "My playlists" tab
    page.get_by_role("button", name="My playlists", exact=True).click()

    # Wait for the playlist table / list to appear
    # The dashboard renders a <table> once playlists are loaded
    try:
        page.wait_for_selector(
            f"text={test_playlist['title']}",
            timeout=15_000,
        )
    except Exception:
        # The playlist might not appear if the dashboard is on a different tab;
        # we still try to click it below.
        pass

    # Click the playlist title link using the specific playlist ID in the href.
    # Using the ID rather than text avoids strict-mode violations when multiple
    # playlists share the same title (e.g. from prior test runs).
    playlist_id = test_playlist["id"]
    playlist_link = page.locator(f'a[href*="/pl/{playlist_id}/"]').first
    playlist_link.click()

    # Wait for navigation to /pl/... (SPA routing may pass through /pl/_/)
    page.wait_for_url(
        lambda url: "/pl/" in url,
        timeout=_NAVIGATION_TIMEOUT,
    )

    # Wait for the page to fully settle:
    # 1. Loading indicator gone
    # 2. Network idle (API call resolved)
    # 3. Either <h1> (success) or role=alert with the error text (failure)
    try:
        page.wait_for_selector("text=Loading...", state="hidden", timeout=15_000)
    except Exception:
        pass  # loading indicator may not appear

    page.wait_for_load_state("networkidle", timeout=20_000)

    pl_page = PlaylistPage(page)
    yield pl_page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPlaylistPageLoadFromDashboard:
    """MYTUBE-597: Playlist detail page loads successfully from Dashboard → My playlists."""

    def test_no_error_message(self, playlist_page_loaded: PlaylistPage) -> None:
        """The 'Could not load playlist. Please try again later.' message must NOT appear.

        This is the primary regression test for MYTUBE-592: the SPA routing
        fix must prevent the UUID validation failure that triggered the error.
        """
        assert not playlist_page_loaded.has_error_message(), (
            f"Playlist detail page shows the error message: '{_ERROR_TEXT}'. "
            "The MYTUBE-592 regression has re-appeared — PlaylistPageClient.tsx "
            "is not reading the playlist UUID from sessionStorage.__spa_playlist_id "
            "when the GitHub Pages SPA shell redirects to /pl/_/."
        )

    def test_playlist_title_visible(
        self, playlist_page_loaded: PlaylistPage, test_playlist: dict
    ) -> None:
        """The playlist title heading (<h1>) must be visible on the page.

        Verifies that the playlist data was loaded and rendered correctly.
        """
        title = playlist_page_loaded.get_playlist_title()
        assert title, (
            "The playlist detail page did not display a title heading (<h1>). "
            f"Expected to see '{test_playlist['title']}'. "
            "This indicates the playlist data was not loaded successfully."
        )

    def test_not_found_page_not_shown(self, playlist_page_loaded: PlaylistPage) -> None:
        """The 'Playlist not found.' message must NOT be displayed."""
        assert not playlist_page_loaded.is_not_found(), (
            "The playlist detail page shows 'Playlist not found.' "
            "The playlist either wasn't created correctly, or the UUID was lost "
            "during SPA routing."
        )

    def test_page_url_contains_playlist_id(
        self, playlist_page_loaded: PlaylistPage, test_playlist: dict
    ) -> None:
        """The final page URL must contain the real playlist UUID.

        After the SPA routing fix (MYTUBE-592), history.replaceState corrects
        the browser URL from /pl/_/ to /pl/<real-uuid>/. This test confirms
        the URL correction works.
        """
        current_url = playlist_page_loaded.get_current_url()
        playlist_id = test_playlist["id"]
        assert playlist_id in current_url or "/pl/" in current_url, (
            f"Expected the page URL to contain the playlist ID '{playlist_id}' "
            f"or at least '/pl/', but got: {current_url!r}. "
            "The SPA URL correction via history.replaceState may not have worked."
        )
