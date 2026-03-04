"""
MYTUBE-233: Save to playlist on watch page — authenticated user can select a
playlist from the dropdown.

Objective
---------
Verify the "Save to playlist" feature on the video watch page for authenticated
users.  When the button is clicked a dropdown appears containing the titles of
the user's current playlists.  Selecting a playlist triggers a successful
addition of the video to that collection (checkmark indicator is shown).

Preconditions
-------------
- User is logged in (FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD).
- User has at least two playlists.

Test steps
----------
1. Login via the web app's login form using Firebase credentials.
2. Register Playwright route interceptors so the watch page always receives
   deterministic mock data:
   - GET  **/api/videos/_      → mock video detail response
   - GET  **/api/me/playlists  → two controlled test playlists
   - POST **/api/playlists/*/videos → HTTP 204 (successful save)
3. Navigate to the static placeholder watch page (/v/_/).
4. Wait for the Save-to-Playlist button to become visible (auth resolved).
5. Click the "Save to playlist" button.
6. Verify the dropdown opens (div[role="menu"] visible).
7. Verify both mock playlist titles appear in the dropdown.
8. Select one playlist.
9. Verify the ✓ saved checkmark appears (span[aria-label="Saved"]).

Note on routing
---------------
The Next.js static export for GitHub Pages only pre-generates /v/_/ (the
placeholder route).  Real video IDs are served via the 404 SPA fallback, which
routes back to the home page in the current GitHub Pages configuration.
Following the pattern established in MYTUBE-205 (rating widget test), this test
navigates to /v/_/ and mocks the API responses so the watch page renders a
complete video with deterministic playlist data — decoupling the test from
backend state while still exercising the full UI interaction chain.

Environment variables
---------------------
FIREBASE_TEST_EMAIL     : Email of the Firebase test user (required).
FIREBASE_TEST_PASSWORD  : Password of the Firebase test user (required).
APP_URL / WEB_BASE_URL  : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses SaveToPlaylistWidget (Page Object) for dropdown interactions.
- Uses WatchPage (Page Object) for page navigation.
- Uses LoginPage (Page Object) for authentication.
- Uses Playwright route interception to inject deterministic API responses.
- WebConfig centralises all env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from playwright.sync_api import Browser, Page, Request, Route, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.watch_page.watch_page import WatchPage
from testing.components.pages.watch_page.save_to_playlist_widget import (
    SaveToPlaylistWidget,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000    # ms
_AUTH_RESOLVE_TIMEOUT = 20_000  # ms — Firebase auth resolves asynchronously
_VIDEO_LOAD_TIMEOUT = 10_000   # ms — watch page renders video metadata

# Placeholder video ID — the only pre-generated watch page in the static export
_PLACEHOLDER_VIDEO_ID = "_"

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

_MOCK_VIDEO_DETAIL = {
    "id": _PLACEHOLDER_VIDEO_ID,
    "title": "MYTUBE-233 Test Video",
    "description": "Automated test video for MYTUBE-233.",
    "thumbnail_url": None,
    "hls_manifest_url": None,
    "view_count": 1,
    "status": "ready",
    "tags": ["test"],
    "uploader": {
        "username": "ci-test",
        "avatar_url": None,
    },
    "created_at": "2026-01-01T00:00:00.000Z",
}

_MOCK_PLAYLISTS = [
    {
        "id": "mock-playlist-alpha-mytube-233",
        "title": "MYTUBE-233 Playlist Alpha",
        "owner_username": "ci-test",
        "created_at": "2026-01-01T00:00:00.000Z",
    },
    {
        "id": "mock-playlist-beta-mytube-233",
        "title": "MYTUBE-233 Playlist Beta",
        "owner_username": "ci-test",
        "created_at": "2026-01-01T00:00:00.000Z",
    },
]

# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _handle_video_route(route: Route, request: Request) -> None:
    """Serve a deterministic mock video detail for GET /api/videos/_."""
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(_MOCK_VIDEO_DETAIL),
    )


def _handle_playlists_route(route: Route, request: Request) -> None:
    """Serve deterministic mock playlists for GET /api/me/playlists."""
    route.fulfill(
        status=200,
        content_type="application/json",
        body=json.dumps(_MOCK_PLAYLISTS),
    )


def _handle_add_video_route(route: Route, request: Request) -> None:
    """Return HTTP 204 for POST /api/playlists/*/videos (successful save)."""
    if request.method == "POST":
        route.fulfill(status=204)
    else:
        route.continue_()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are absent."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-233 Save to Playlist "
            "test.  Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-233."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser instance shared across all tests in the module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def watch_page_loaded(browser: Browser, web_config: WebConfig) -> dict:
    """Login, register route interceptors, navigate to the watch page.

    Uses the placeholder video ID ``_`` — the only URL in the GitHub Pages
    static export that renders the WatchPageClient component.  Route
    interceptors inject deterministic mock data so tests are independent of
    backend state.

    Yields a dict with:
      page       – the Playwright Page object
      watch_page – WatchPage page-object (already navigated)
      widget     – SaveToPlaylistWidget page-object
    """
    ctx = browser.new_context()
    page: Page = ctx.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Step 1 — Login via the web app's login form
    login_pg = LoginPage(page)
    login_pg.navigate(web_config.login_url())
    login_pg.login_as(web_config.test_email, web_config.test_password)
    # Wait until the browser leaves the login page (redirect to home)
    page.wait_for_url(
        lambda url: "/login" not in url,
        timeout=_AUTH_RESOLVE_TIMEOUT,
    )

    # Step 2 — Register route interceptors before navigating to watch page
    page.route("**/api/videos/_", _handle_video_route)
    page.route("**/api/videos/_/", _handle_video_route)
    page.route("**/api/me/playlists", _handle_playlists_route)
    page.route("**/api/playlists/*/videos", _handle_add_video_route)

    # Step 3 — Navigate to the placeholder watch page URL
    watch_pg = WatchPage(page)
    watch_pg.navigate(web_config.base_url, _PLACEHOLDER_VIDEO_ID)

    # Wait for the video title to confirm the watch page rendered
    try:
        page.wait_for_selector("h1", state="visible", timeout=_VIDEO_LOAD_TIMEOUT)
    except Exception:
        pass  # even if h1 times out, proceed (test assertions will catch failures)

    widget = SaveToPlaylistWidget(page)

    yield {"page": page, "watch_page": watch_pg, "widget": widget}

    ctx.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSaveToPlaylistDropdown:
    """MYTUBE-233: SaveToPlaylist UI on the watch page for authenticated users."""

    def test_save_button_is_visible_for_authenticated_user(
        self,
        watch_page_loaded: dict,
    ):
        """The 'Save to playlist' button is visible for an authenticated user.

        WatchPageClient renders SaveToPlaylist with hidden={authLoading || !user}.
        Once Firebase auth resolves and the user object is set, the button must
        appear.  This test verifies the button becomes visible after login.
        """
        widget: SaveToPlaylistWidget = watch_page_loaded["widget"]
        page: Page = watch_page_loaded["page"]

        is_visible = widget.is_save_button_visible()

        assert is_visible, (
            "The 'Save to playlist' button was not visible after login and "
            "navigating to /v/_.  "
            "Expected button[aria-label='Save to playlist'] to be present and "
            "visible for authenticated users.  "
            "Check that Firebase auth resolved (authLoading=false, user!=null) "
            "in the WatchPage auth context.  "
            f"Current URL: {page.url}"
        )

    def test_dropdown_opens_on_button_click(
        self,
        watch_page_loaded: dict,
        web_config: WebConfig,
    ):
        """Clicking the 'Save to playlist' button opens the dropdown menu.

        The SaveToPlaylist component toggles ``open`` state on button click and
        renders a div[role='menu'] when open=true.
        """
        widget: SaveToPlaylistWidget = watch_page_loaded["widget"]
        page: Page = watch_page_loaded["page"]

        # Navigate fresh to ensure dropdown is closed
        watch_pg: WatchPage = watch_page_loaded["watch_page"]
        watch_pg.navigate(web_config.base_url, _PLACEHOLDER_VIDEO_ID)

        widget.open_dropdown()

        assert widget.is_dropdown_visible(), (
            "The dropdown (div[role='menu']) did not appear after clicking the "
            "'Save to playlist' button.  "
            "The SaveToPlaylist component must render the dropdown on toggle click.  "
            f"Current URL: {page.url}"
        )

    def test_dropdown_contains_both_mock_playlist_titles(
        self,
        watch_page_loaded: dict,
        web_config: WebConfig,
    ):
        """The dropdown lists the titles of the user's playlists.

        After clicking the button, the component calls GET /api/me/playlists and
        renders each playlist summary as a button[role='menuitem'].  Both mock
        playlists returned by the route interceptor must appear in the dropdown.
        """
        widget: SaveToPlaylistWidget = watch_page_loaded["widget"]
        watch_pg: WatchPage = watch_page_loaded["watch_page"]
        page: Page = watch_page_loaded["page"]

        watch_pg.navigate(web_config.base_url, _PLACEHOLDER_VIDEO_ID)

        widget.open_dropdown()
        titles = widget.get_playlist_titles()

        for pl in _MOCK_PLAYLISTS:
            expected_title = pl["title"]
            found = any(expected_title in item_text for item_text in titles)
            assert found, (
                f"Expected playlist '{expected_title}' to appear in the dropdown, "
                f"but it was not found.  "
                f"Dropdown items: {titles}.  "
                "The SaveToPlaylist component must call GET /api/me/playlists and "
                "render all returned playlist titles as button[role='menuitem'] elements."
            )

    def test_selecting_playlist_shows_success_indicator(
        self,
        watch_page_loaded: dict,
        web_config: WebConfig,
    ):
        """Selecting a playlist from the dropdown triggers a successful save.

        After clicking a playlist button, the component calls
        POST /api/playlists/:id/videos (mocked to return 204).  On success it
        sets savedPlaylistID which renders a span[aria-label='Saved'] (✓) next
        to the playlist title for ~800 ms before closing the dropdown.
        """
        widget: SaveToPlaylistWidget = watch_page_loaded["widget"]
        watch_pg: WatchPage = watch_page_loaded["watch_page"]
        page: Page = watch_page_loaded["page"]

        watch_pg.navigate(web_config.base_url, _PLACEHOLDER_VIDEO_ID)

        widget.open_dropdown()

        # Verify no pre-existing error in the dropdown
        pre_error = widget.get_error_text()
        assert pre_error is None, (
            f"An error was already displayed in the dropdown before selecting a "
            f"playlist: '{pre_error}'.  Cannot proceed with save test."
        )

        # Click the first mock playlist
        target_title = _MOCK_PLAYLISTS[0]["title"]
        widget.click_playlist(target_title)

        # Assert: the ✓ saved checkmark appears
        save_indicator_appeared = widget.wait_for_save_indicator()
        post_error = widget.get_error_text()

        assert post_error is None, (
            f"An error appeared after selecting playlist '{target_title}': "
            f"'{post_error}'.  "
            "The video should have been added to the playlist successfully.  "
            "Ensure POST /api/playlists/:id/videos returns HTTP 204.  "
            f"Current URL: {page.url}"
        )
        assert save_indicator_appeared, (
            f"The ✓ saved indicator (span[aria-label='Saved']) did not appear "
            f"after selecting playlist '{target_title}'.  "
            "Expected a visual confirmation that the video was added.  "
            "The SaveToPlaylist component must set savedPlaylistID on success, "
            "which renders the checkmark next to the playlist title.  "
            f"Current URL: {page.url}"
        )
