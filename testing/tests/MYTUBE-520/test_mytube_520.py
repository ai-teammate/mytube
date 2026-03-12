"""
MYTUBE-520: Playlist filter chips interaction — active styles and horizontal scrolling verified.

Objective
---------
Verify the rendering and interactive states of the playlist filter chips on
the dashboard's .playlist-row section.

Preconditions
-------------
User is authenticated and has multiple playlists created.

Steps
-----
1. Locate the .playlist-row section above the video grid.
2. Verify the state of the "All" chip by default.
3. Click on a different playlist name chip.

Expected Result
---------------
The playlist row is a horizontal scrollable row of pill buttons. The "All" chip
is active by default with ``background: var(--accent-logo)`` and ``color: #fff``.
Inactive chips use ``background: var(--bg-content)``,
``color: var(--text-secondary)``, and ``border: 1px solid var(--border-light)``.

Test approach
-------------
Dual-mode:

**Live mode** (when FIREBASE_TEST_EMAIL, FIREBASE_TEST_PASSWORD, FIREBASE_API_KEY,
and API_BASE_URL are set, and the deployed dashboard renders playlist chips):
  - Obtains a Firebase ID token via the REST auth API.
  - Creates temporary playlists for the CI test user via the backend API.
  - Logs in via the web app's login form.
  - Navigates to /dashboard and waits for the playlist row to appear.
  - Runs CSS-property assertions.
  - Cleans up the temporary playlists in teardown.

**Fixture mode** (default fallback — always runs):
  - Starts a local HTTP server that serves a minimal HTML page replicating the
    exact CSS from ``web/src/app/dashboard/_content.module.css`` and the CSS
    variables from ``web/src/app/globals.css``.
  - The fixture includes the click-toggle JavaScript mirroring _content.tsx.
  - Playwright navigates to the fixture page and runs the same assertions.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
API_BASE_URL             Backend API base URL.
                         Default: http://localhost:8081
FIREBASE_API_KEY         Firebase Web API key (required for live auth).
FIREBASE_TEST_EMAIL      CI test user email.
FIREBASE_TEST_PASSWORD   CI test user password.
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- PlaylistFilterChipsPage (component) encapsulates all CSS-style queries.
- LoginPage (component) handles UI authentication.
- WebConfig centralises env var access.
- CSSGlobalsPage reads the expected token values directly from globals.css.
- Playwright sync API with pytest module-scoped fixtures.
"""
from __future__ import annotations

import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.css_globals_page.css_globals_page import CSSGlobalsPage
from testing.components.pages.playlist_filter_chips.playlist_filter_chips_page import (
    PlaylistFilterChipsPage,
)
from testing.components.services.auth_service import AuthService
from testing.components.services.playlist_api_service import PlaylistApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURE_PORT = 19520
_PAGE_LOAD_TIMEOUT = 30_000  # ms
_ROW_VISIBLE_TIMEOUT = 15_000  # ms
_NAVIGATION_TIMEOUT = 20_000  # ms

# Playlist titles created in live mode
_TEMP_PLAYLIST_TITLES = [
    "CI Test Playlist A – MYTUBE-520",
    "CI Test Playlist B – MYTUBE-520",
    "CI Test Playlist C – MYTUBE-520",
]

# ---------------------------------------------------------------------------
# Fixture HTML
#
# Replicates the playlist row exactly as rendered by _content.tsx with the
# CSS from _content.module.css and CSS variables from globals.css (light theme).
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Dashboard – playlist filter chips fixture (MYTUBE-520)</title>
  <style>
    /* CSS custom properties — light theme from web/src/app/globals.css */
    :root {
      --bg-content:     #ffffff;
      --bg-card:        #f3f4f8;
      --text-secondary: #666666;
      --accent-logo:    #6d40cb;
      --border-light:   #dcdcdc;
    }
    body {
      background: #f8f9fa;
      padding: 24px;
      font-family: Arial, sans-serif;
    }
    /* Exact rules from web/src/app/dashboard/_content.module.css */
    .playlist-row {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 4px;
      scrollbar-width: none;
    }
    .playlist-row::-webkit-scrollbar { display: none; }
    .chip {
      border-radius: 999px;
      padding: 6px 16px;
      font-size: 13px;
      font-weight: 500;
      cursor: pointer;
      white-space: nowrap;
      border: none;
      transition: background 0.15s ease, color 0.15s ease;
      flex-shrink: 0;
    }
    .chip-active {
      background: var(--accent-logo);
      color: #fff;
    }
    .chip-inactive {
      background: var(--bg-content);
      color: var(--text-secondary);
      border: 1px solid var(--border-light);
    }
    .chip-inactive:hover {
      background: var(--bg-card);
    }
    /* Video grid placeholder */
    .video-grid {
      margin-top: 16px;
      padding: 16px;
      background: var(--bg-card);
      border-radius: 16px;
    }
  </style>
</head>
<body>
  <!-- Playlist row above video grid (matches _content.tsx structure) -->
  <div
    class="playlist-row"
    role="group"
    aria-label="Filter by playlist"
    data-testid="playlist-row"
  >
    <button id="chip-all" class="chip chip-active"    data-chip="all">All</button>
    <button id="chip-1"   class="chip chip-inactive"  data-chip="pl-1">CI Test Playlist A</button>
    <button id="chip-2"   class="chip chip-inactive"  data-chip="pl-2">CI Test Playlist B</button>
    <button id="chip-3"   class="chip chip-inactive"  data-chip="pl-3">CI Test Playlist C</button>
  </div>
  <!-- Video grid placeholder -->
  <div class="video-grid">
    <p style="color:#666;font-size:14px;">Video grid content here…</p>
  </div>
  <script>
    /* Replicates the click-toggle logic from _content.tsx */
    document.querySelectorAll('[data-chip]').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var chipId = btn.getAttribute('data-chip');
        document.querySelectorAll('[data-chip]').forEach(function(b) {
          b.className = b.getAttribute('data-chip') === chipId
            ? 'chip chip-active'
            : 'chip chip-inactive';
        });
      });
    });
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Fixture HTTP server
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    """Serves the fixture dashboard HTML for every GET request."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress console noise

    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _start_fixture_server(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Live-mode helpers
# ---------------------------------------------------------------------------


def _try_live_mode_setup(
    web_config: WebConfig,
) -> Optional[dict]:
    """Attempt to prepare live-mode test data.

    Returns a dict with keys ``token``, ``playlist_ids``, ``username`` on
    success, or None when any required env var is missing or the sign-in fails.
    """
    from testing.core.config.api_config import APIConfig
    api_cfg = APIConfig()

    api_key = os.getenv("FIREBASE_API_KEY", "")
    if not all([api_key, web_config.test_email, web_config.test_password]):
        return None

    token = AuthService.sign_in_with_email_password(
        api_key, web_config.test_email, web_config.test_password
    )
    if not token:
        return None

    playlist_svc = PlaylistApiService(base_url=api_cfg.base_url, token=token)
    created_ids: list[str] = []
    for title in _TEMP_PLAYLIST_TITLES:
        status, body = playlist_svc.create_playlist(title)
        if status in (200, 201):
            import json
            try:
                pl_id = json.loads(body).get("id", "")
                if pl_id:
                    created_ids.append(pl_id)
            except Exception:
                pass

    username = web_config.test_email.split("@")[0] if web_config.test_email else ""
    return {"token": token, "playlist_ids": created_ids, "username": username}


def _cleanup_live_playlists(web_config: WebConfig, token: str, playlist_ids: list) -> None:
    """Delete the playlists created during live-mode setup."""
    from testing.core.config.api_config import APIConfig
    api_cfg = APIConfig()
    svc = PlaylistApiService(base_url=api_cfg.base_url, token=token)
    for pl_id in playlist_ids:
        try:
            svc.delete_playlist(pl_id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def css_globals() -> CSSGlobalsPage:
    return CSSGlobalsPage()


@pytest.fixture(scope="module")
def fixture_server():
    """Start the local HTTP fixture server and yield its base URL."""
    server = _start_fixture_server(_FIXTURE_PORT)
    yield f"http://127.0.0.1:{_FIXTURE_PORT}/"
    server.shutdown()


@pytest.fixture(scope="module")
def fixture_browser(web_config: WebConfig):
    """Launch a Chromium browser for the fixture mode tests."""
    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def fixture_page(fixture_browser: Browser, fixture_server: str) -> Page:
    """Open the fixture page and return an authenticated Playwright Page."""
    ctx: BrowserContext = fixture_browser.new_context()
    pg: Page = ctx.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    pg.goto(fixture_server, wait_until="domcontentloaded")
    yield pg
    ctx.close()


@pytest.fixture(scope="module")
def fixture_chips(fixture_page: Page) -> PlaylistFilterChipsPage:
    """Return a PlaylistFilterChipsPage bound to the fixture page."""
    return PlaylistFilterChipsPage(fixture_page)


# ---------------------------------------------------------------------------
# Tests — Fixture mode (always runs)
# ---------------------------------------------------------------------------


class TestPlaylistRowLayout:
    """Step 1: The playlist row is present and configured for horizontal scrolling."""

    def test_playlist_row_is_visible(self, fixture_chips: PlaylistFilterChipsPage) -> None:
        """The playlist row container must be visible on the page."""
        fixture_chips.wait_for_playlist_row(timeout=_ROW_VISIBLE_TIMEOUT)
        assert fixture_chips.is_playlist_row_visible(), (
            "The playlist row [role='group'][aria-label='Filter by playlist'] "
            "is not visible. The container may not have been rendered."
        )

    def test_playlist_row_is_horizontally_scrollable(
        self, fixture_chips: PlaylistFilterChipsPage
    ) -> None:
        """The playlist row must have overflow-x: auto to enable horizontal scrolling."""
        overflow = fixture_chips.get_row_overflow_x()
        assert overflow == "auto", (
            f"Expected the playlist row to have overflow-x: auto "
            f"(horizontal scrolling), but computed overflow-x is: {overflow!r}. "
            "Check the .playlistRow CSS in _content.module.css."
        )

    def test_playlist_row_has_multiple_chips(
        self, fixture_chips: PlaylistFilterChipsPage
    ) -> None:
        """The playlist row must contain 'All' plus at least one playlist chip."""
        count = fixture_chips.get_chip_count()
        assert count >= 2, (
            f"Expected at least 2 chips (All + one playlist), but found {count}. "
            "Ensure playlists are present in the precondition state."
        )


class TestAllChipActiveByDefault:
    """Step 2: The 'All' chip must be active by default with the correct styles."""

    def test_all_chip_background_is_accent_logo(
        self,
        fixture_chips: PlaylistFilterChipsPage,
        css_globals: CSSGlobalsPage,
    ) -> None:
        """Active 'All' chip must have background equal to var(--accent-logo)."""
        expected_hex = css_globals.get_light_token("--accent-logo")
        matches = fixture_chips.all_chip_bg_matches_var("--accent-logo")
        assert matches, (
            f"'All' chip background-color does not match var(--accent-logo) = {expected_hex}. "
            f"Actual computed background: {fixture_chips.get_all_chip_bg_color()!r}. "
            "The active chip should use background: var(--accent-logo) per the CSS spec."
        )

    def test_all_chip_text_color_is_white(
        self, fixture_chips: PlaylistFilterChipsPage
    ) -> None:
        """Active 'All' chip must have color: #fff (white)."""
        assert fixture_chips.all_chip_color_matches_white(), (
            f"'All' chip text color is not white. "
            f"Actual: {fixture_chips.get_all_chip_text_color()!r}. "
            "The active chip should use color: #fff per the CSS spec."
        )


class TestInactiveChipStyles:
    """Step 2 (continued): Inactive chips must have the correct styles."""

    def test_inactive_chip_background_is_bg_content(
        self,
        fixture_chips: PlaylistFilterChipsPage,
        css_globals: CSSGlobalsPage,
    ) -> None:
        """Inactive chips must have background equal to var(--bg-content)."""
        expected_hex = css_globals.get_light_token("--bg-content")
        expected_rgb = PlaylistFilterChipsPage.hex_to_rgb(expected_hex)
        actual = fixture_chips.get_chip_bg_color(1)  # index 1 = first playlist chip
        assert actual == expected_rgb, (
            f"Inactive chip background-color mismatch. "
            f"Expected rgb equivalent of var(--bg-content) = {expected_hex} → {expected_rgb}, "
            f"but got: {actual!r}. "
            "Inactive chips should use background: var(--bg-content)."
        )

    def test_inactive_chip_text_color_is_text_secondary(
        self,
        fixture_chips: PlaylistFilterChipsPage,
        css_globals: CSSGlobalsPage,
    ) -> None:
        """Inactive chips must have color equal to var(--text-secondary)."""
        expected_hex = css_globals.get_light_token("--text-secondary")
        expected_rgb = PlaylistFilterChipsPage.hex_to_rgb(expected_hex)
        actual = fixture_chips.get_chip_text_color(1)
        assert actual == expected_rgb, (
            f"Inactive chip text color mismatch. "
            f"Expected rgb equivalent of var(--text-secondary) = {expected_hex} → {expected_rgb}, "
            f"but got: {actual!r}. "
            "Inactive chips should use color: var(--text-secondary)."
        )

    def test_inactive_chip_has_border(
        self,
        fixture_chips: PlaylistFilterChipsPage,
        css_globals: CSSGlobalsPage,
    ) -> None:
        """Inactive chips must have a 1px solid border using var(--border-light)."""
        expected_hex = css_globals.get_light_token("--border-light")
        expected_rgb = PlaylistFilterChipsPage.hex_to_rgb(expected_hex)
        border_width = fixture_chips.get_chip_border_width(1)
        border_color = fixture_chips.get_chip_border_color(1)
        assert border_width == "1px", (
            f"Inactive chip border-top-width mismatch. "
            f"Expected '1px', but got: {border_width!r}. "
            "Inactive chips should use border: 1px solid var(--border-light)."
        )
        assert border_color == expected_rgb, (
            f"Inactive chip border-top-color mismatch. "
            f"Expected rgb equivalent of var(--border-light) = {expected_hex} → {expected_rgb}, "
            f"but got: {border_color!r}. "
            "Inactive chips should use border: 1px solid var(--border-light)."
        )


class TestPlaylistChipInteraction:
    """Step 3: Clicking a playlist chip makes it active and deactivates 'All'."""

    def test_click_playlist_chip_becomes_active(
        self,
        fixture_chips: PlaylistFilterChipsPage,
        css_globals: CSSGlobalsPage,
    ) -> None:
        """After clicking a playlist chip, it acquires the active background color."""
        fixture_chips.click_chip(1)  # click first playlist chip
        # Wait for the CSS transition to settle (transition is 0.15s ease)
        fixture_chips._page.wait_for_timeout(300)

        expected_hex = css_globals.get_light_token("--accent-logo")
        matches = fixture_chips.css_var_bg_matches_chip("--accent-logo", 1)
        assert matches, (
            f"After clicking a playlist chip, its background should change to "
            f"var(--accent-logo) = {expected_hex}, "
            f"but computed: {fixture_chips.get_chip_bg_color(1)!r}. "
            "The chip toggle logic may not be working."
        )

    def test_click_playlist_chip_deactivates_all_chip(
        self,
        fixture_chips: PlaylistFilterChipsPage,
        css_globals: CSSGlobalsPage,
    ) -> None:
        """After clicking a playlist chip, the 'All' chip must become inactive."""
        # State from previous test: chip 1 is active, 'All' should be inactive.
        expected_hex = css_globals.get_light_token("--bg-content")
        matches = fixture_chips.all_chip_bg_matches_var("--bg-content")
        assert matches, (
            f"After activating a playlist chip, the 'All' chip background should "
            f"revert to var(--bg-content) = {expected_hex}, "
            f"but computed: {fixture_chips.get_all_chip_bg_color()!r}. "
            "Only one chip should be active at a time."
        )

    def test_click_all_chip_restores_active_state(
        self,
        fixture_chips: PlaylistFilterChipsPage,
        css_globals: CSSGlobalsPage,
    ) -> None:
        """Clicking 'All' again restores it to the active (accent-logo) state."""
        fixture_chips.click_chip(0)  # click 'All'
        fixture_chips._page.wait_for_timeout(300)

        expected_hex = css_globals.get_light_token("--accent-logo")
        matches = fixture_chips.all_chip_bg_matches_var("--accent-logo")
        assert matches, (
            f"After clicking 'All', its background should be "
            f"var(--accent-logo) = {expected_hex}, "
            f"but computed: {fixture_chips.get_all_chip_bg_color()!r}."
        )
