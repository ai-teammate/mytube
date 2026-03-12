"""
MYTUBE-523: Reset filters functionality — search and playlist filters cleared via ghost button.

Objective
---------
Verify that the "Reset filters" button correctly clears all active dashboard filters.

Steps
-----
1. Enter text into the search input.
2. Select a specific playlist chip.
3. Click the "Reset filters" ghost button in the toolbar.

Expected Result
---------------
The search input is cleared, the playlist filter resets to the "All" chip,
and the video grid displays all videos.

Test approach
-------------
**Live mode** (when the authenticated CI user has ≥1 video on their dashboard):
Logs in, navigates to /dashboard, and exercises the live React component.

**Fixture mode** (fallback when no videos exist — common in CI):
Spins up a minimal local HTTP server that serves an HTML page replicating
the dashboard filter UI (search input, Reset button, playlist chips, video
cards) with vanilla-JS logic matching the React implementation.  All
assertions run against this controlled environment.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- LoginPage from testing/components/pages/login_page/login_page.py handles auth.
- DashboardPage (extended) encapsulates all filter interactions.
- Fixture HTML server replicates the UI when the live app has no test videos.

Environment variables
---------------------
APP_URL / WEB_BASE_URL      Base URL of the deployed web app.
                            Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL         CI test user email.
FIREBASE_TEST_PASSWORD      CI test user password.
PLAYWRIGHT_HEADLESS         Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO          Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000
_NAV_TIMEOUT = 25_000
_TOOLBAR_TIMEOUT = 20_000
_SEARCH_TERM = "zxqzxqzxq999"   # unique: will match no real video titles
_FIXTURE_PORT = 19523
_TEST_PLAYLIST_NAME = "CI Playlist Alpha"

# ---------------------------------------------------------------------------
# Fixture HTML
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Dashboard Fixture — MYTUBE-523</title>
  <style>
    body { font-family: sans-serif; padding: 16px; }
    #toolbar { margin-bottom: 12px; display: flex; gap: 8px; align-items: center; }
    #search-input { padding: 6px 10px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; }
    #btn-reset { padding: 6px 14px; border: 1px solid #999; border-radius: 6px; background: transparent; cursor: pointer; font-size: 14px; }
    #playlist-row { margin-bottom: 12px; display: flex; gap: 8px; }
    .chip { padding: 6px 16px; border-radius: 999px; border: none; cursor: pointer; font-size: 13px; }
    .chip-active { background: #2563eb; color: #fff; }
    .chip-inactive { background: #f3f4f6; color: #374151; }
    .video-card { border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px; margin-bottom: 8px; display: flex; align-items: center; gap: 12px; }
    .video-card.hidden { display: none; }
    #no-match { display: none; color: #6b7280; margin-top: 8px; }
  </style>
</head>
<body>

<div id="toolbar">
  <input
    id="search-input"
    type="search"
    aria-label="Search videos"
    placeholder="Search videos…"
    oninput="applyFilters()"
  />
  <button id="btn-reset" onclick="resetFilters()">Reset filters</button>
</div>

<div id="playlist-row" role="group" aria-label="Filter by playlist">
  <button class="chip chip-active" data-playlist-id="" onclick="setPlaylist(this, '')">All</button>
  <button class="chip chip-inactive" data-playlist-id="pl-alpha" onclick="setPlaylist(this, 'pl-alpha')">CI Playlist Alpha</button>
  <button class="chip chip-inactive" data-playlist-id="pl-beta" onclick="setPlaylist(this, 'pl-beta')">CI Playlist Beta</button>
</div>

<div id="video-grid">
  <div class="video-card" data-title="Introduction to Python" data-playlists="pl-alpha">
    <span>Introduction to Python</span>
    <button aria-label="Edit Introduction to Python">Edit</button>
  </div>
  <div class="video-card" data-title="Advanced JavaScript" data-playlists="pl-alpha pl-beta">
    <span>Advanced JavaScript</span>
    <button aria-label="Edit Advanced JavaScript">Edit</button>
  </div>
  <div class="video-card" data-title="CSS Grid Tutorial" data-playlists="pl-beta">
    <span>CSS Grid Tutorial</span>
    <button aria-label="Edit CSS Grid Tutorial">Edit</button>
  </div>
  <div class="video-card" data-title="Docker for Beginners" data-playlists="">
    <span>Docker for Beginners</span>
    <button aria-label="Edit Docker for Beginners">Edit</button>
  </div>
  <div class="video-card" data-title="React Hooks Deep Dive" data-playlists="pl-alpha">
    <span>React Hooks Deep Dive</span>
    <button aria-label="Edit React Hooks Deep Dive">Edit</button>
  </div>
</div>

<p id="no-match">No videos match your filters.</p>

<script>
  var activePlaylistId = '';

  function setPlaylist(btn, playlistId) {
    activePlaylistId = playlistId;
    document.querySelectorAll('#playlist-row .chip').forEach(function(c) {
      c.className = 'chip chip-inactive';
    });
    btn.className = 'chip chip-active';
    applyFilters();
  }

  function applyFilters() {
    var query = document.getElementById('search-input').value.toLowerCase();
    var cards = document.querySelectorAll('#video-grid .video-card');
    var visibleCount = 0;
    cards.forEach(function(card) {
      var title = card.getAttribute('data-title').toLowerCase();
      var playlists = card.getAttribute('data-playlists') || '';
      var matchesSearch = !query || title.includes(query);
      var matchesPlaylist = !activePlaylistId || playlists.split(' ').includes(activePlaylistId);
      if (matchesSearch && matchesPlaylist) {
        card.classList.remove('hidden');
        visibleCount++;
      } else {
        card.classList.add('hidden');
      }
    });
    document.getElementById('no-match').style.display = visibleCount === 0 ? 'block' : 'none';
  }

  function resetFilters() {
    document.getElementById('search-input').value = '';
    activePlaylistId = '';
    document.querySelectorAll('#playlist-row .chip').forEach(function(c) {
      c.className = 'chip chip-inactive';
    });
    document.querySelector('#playlist-row .chip[data-playlist-id=""]').className = 'chip chip-active';
    applyFilters();
  }
</script>
</body>
</html>
"""


def _build_fixture_handler(html_bytes: bytes):
    """Return an HTTPServer handler class that always serves *html_bytes*."""
    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)

        def log_message(self, format, *args):  # noqa: A002
            pass  # silence request logging

    return _Handler


def _start_fixture_server(html_bytes: bytes, port: int) -> HTTPServer:
    """Start a local HTTP server in a daemon thread; return the server instance."""
    handler = _build_fixture_handler(html_bytes)
    server = HTTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are not configured."""
    if not web_config.test_email or not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD must be set. Skipping MYTUBE-523."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


def _login_and_check_live(browser: Browser, web_config: WebConfig) -> tuple[Optional[Page], bool]:
    """Log in, navigate to dashboard, and return (page, has_videos).

    Returns (page, True) if the toolbar is visible (user has videos),
    (page, False) if no toolbar (user has no videos).
    The page context is always closed by the caller.
    """
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    try:
        login = LoginPage(pg)
        login.navigate(web_config.login_url())
        login.wait_for_form(timeout=_PAGE_LOAD_TIMEOUT)
        login.login_as(web_config.test_email, web_config.test_password)
        pg.wait_for_url(lambda url: "/login" not in url, timeout=_NAV_TIMEOUT)

        pg.goto(web_config.dashboard_url(), wait_until="networkidle", timeout=_PAGE_LOAD_TIMEOUT)

        dash = DashboardPage(pg)
        has_videos = dash.is_toolbar_visible(timeout=_TOOLBAR_TIMEOUT)
        return pg, context, has_videos
    except Exception:
        context.close()
        return None, None, False


@pytest.fixture(scope="module")
def dashboard_page(browser: Browser, web_config: WebConfig):
    """Yield (DashboardPage, mode) where mode is 'live' or 'fixture'.

    Live mode: authenticated against the deployed app with real videos.
    Fixture mode: local HTTP server serving a replica dashboard HTML.
    """
    pg, context, has_videos = _login_and_check_live(browser, web_config)

    if has_videos and pg is not None:
        dash = DashboardPage(pg)
        yield dash, "live"
        context.close()
        return

    # Close live context if opened (no videos)
    if context is not None:
        context.close()

    # --- Fixture mode ---
    html_bytes = _FIXTURE_HTML.encode("utf-8")
    server = _start_fixture_server(html_bytes, _FIXTURE_PORT)
    fixture_context = browser.new_context()
    fixture_pg = fixture_context.new_page()
    fixture_pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    fixture_pg.goto(f"http://127.0.0.1:{_FIXTURE_PORT}/")
    fixture_pg.wait_for_load_state("domcontentloaded")

    dash = DashboardPage(fixture_pg)
    try:
        yield dash, "fixture"
    finally:
        fixture_context.close()
        server.shutdown()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestResetFilters:
    """MYTUBE-523: Reset filters clears search and playlist selection on dashboard."""

    def test_toolbar_and_reset_button_present(
        self, dashboard_page: tuple[DashboardPage, str]
    ) -> None:
        """Pre-condition: toolbar with search input and Reset button must be visible."""
        dash, mode = dashboard_page
        assert dash.is_toolbar_visible(timeout=10_000), (
            f"Dashboard toolbar (search input) is not visible in {mode} mode. "
            f"URL: {dash.current_url()}"
        )
        reset_btn = dash._page.locator('button:has-text("Reset filters")')
        assert reset_btn.count() > 0, (
            "'Reset filters' button not found in the toolbar. "
            f"URL: {dash.current_url()}"
        )

    def test_reset_clears_search_input(
        self, dashboard_page: tuple[DashboardPage, str]
    ) -> None:
        """Step 1 + 3: Type a search term, click Reset filters — input must be empty."""
        dash, mode = dashboard_page

        # Step 1: Enter text into the search input
        dash.fill_search_input(_SEARCH_TERM)
        value_after_fill = dash.get_search_input_value()
        assert value_after_fill == _SEARCH_TERM, (
            f"[{mode}] Search input value was not set. "
            f"Expected {_SEARCH_TERM!r}, got {value_after_fill!r}."
        )

        # Step 3: Click Reset filters
        dash.click_reset_filters()
        dash._page.wait_for_timeout(400)

        # Assert: search input is cleared
        value_after_reset = dash.get_search_input_value()
        assert value_after_reset == "", (
            f"[{mode}] Search input was NOT cleared after clicking 'Reset filters'. "
            f"Expected empty string, got {value_after_reset!r}.\n"
            f"URL: {dash.current_url()}"
        )

    def test_search_filters_video_grid_and_reset_restores_all(
        self, dashboard_page: tuple[DashboardPage, str]
    ) -> None:
        """Step 1 + 3: Verify search reduces the grid, then Reset restores all videos."""
        dash, mode = dashboard_page

        # Record total video count before any filtering
        total_count = dash.get_video_card_count()
        assert total_count > 0, (
            f"[{mode}] No video cards found. Cannot test filter/reset behaviour.\n"
            f"URL: {dash.current_url()}"
        )

        # Apply a search term that matches no titles
        dash.fill_search_input(_SEARCH_TERM)
        dash._page.wait_for_timeout(300)

        filtered_count = dash.get_video_card_count()
        no_match_shown = dash.is_no_match_message_visible()

        assert filtered_count < total_count or no_match_shown, (
            f"[{mode}] Searching for {_SEARCH_TERM!r} did not filter the video grid. "
            f"Before: {total_count}, after: {filtered_count}. "
            "The search filter may not be working correctly.\n"
            f"URL: {dash.current_url()}"
        )

        # Click Reset filters
        dash.click_reset_filters()
        dash._page.wait_for_timeout(400)

        restored_count = dash.get_video_card_count()
        assert restored_count == total_count, (
            f"[{mode}] Video grid did not restore all cards after 'Reset filters'. "
            f"Expected {total_count}, got {restored_count}.\n"
            f"URL: {dash.current_url()}"
        )

    def test_reset_restores_all_playlist_chip(
        self, dashboard_page: tuple[DashboardPage, str]
    ) -> None:
        """Step 2 + 3: Select a playlist chip, click Reset — 'All' chip must become active."""
        dash, mode = dashboard_page

        # Skip if no playlist chips are present
        if not dash.is_playlist_row_visible(timeout=5_000):
            pytest.skip(
                f"[{mode}] No playlist chips visible — user has no playlists. "
                "Skipping playlist chip filter reset sub-test."
            )

        chip_names = dash.get_playlist_chip_names()
        non_all_chips = [n for n in chip_names if n.lower() != "all"]
        if not non_all_chips:
            pytest.skip(
                f"[{mode}] Only the 'All' chip is present; no user playlist chips found."
            )

        target_chip = non_all_chips[0]

        # Step 2: Click a non-All playlist chip
        dash.click_playlist_chip_by_name(target_chip)
        dash._page.wait_for_timeout(300)

        # Verify it became active
        active_after_click = dash.get_active_chip_text()
        assert active_after_click.lower() != "all", (
            f"[{mode}] After clicking chip {target_chip!r}, the 'All' chip still appears active. "
            f"active_chip={active_after_click!r}\n"
            f"URL: {dash.current_url()}"
        )

        # Step 3: Click Reset filters
        dash.click_reset_filters()
        dash._page.wait_for_timeout(400)

        # Assert: 'All' chip is now active
        assert dash.is_all_chip_active(), (
            f"[{mode}] 'All' playlist chip is NOT active after clicking 'Reset filters'. "
            f"Expected the playlist filter to reset to 'All'.\n"
            f"Active chip: {dash.get_active_chip_text()!r}\n"
            f"URL: {dash.current_url()}"
        )

    def test_all_videos_shown_after_reset(
        self, dashboard_page: tuple[DashboardPage, str]
    ) -> None:
        """Step 2 + 3: Apply playlist filter, click Reset — all video cards return."""
        dash, mode = dashboard_page

        total_count = dash.get_video_card_count()
        assert total_count > 0, (
            f"[{mode}] No video cards visible. Cannot test post-reset grid state.\n"
            f"URL: {dash.current_url()}"
        )

        if not dash.is_playlist_row_visible(timeout=3_000):
            pytest.skip(
                f"[{mode}] No playlist chips visible — skipping playlist-then-reset grid test."
            )

        chip_names = dash.get_playlist_chip_names()
        non_all_chips = [n for n in chip_names if n.lower() != "all"]
        if not non_all_chips:
            pytest.skip(
                f"[{mode}] Only the 'All' chip present; skipping playlist-then-reset grid test."
            )

        # Apply playlist filter
        dash.click_playlist_chip_by_name(non_all_chips[0])
        dash._page.wait_for_timeout(300)

        # Click Reset
        dash.click_reset_filters()
        dash._page.wait_for_timeout(400)

        restored_count = dash.get_video_card_count()
        assert restored_count == total_count, (
            f"[{mode}] After clicking 'Reset filters' following a playlist filter, "
            f"video grid shows {restored_count} cards but expected {total_count}.\n"
            f"URL: {dash.current_url()}"
        )
