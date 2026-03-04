"""
MYTUBE-232: Playback auto-advance on playlist page — next video starts automatically.

Objective
---------
Verify that the player logic on the playlist page automatically progresses to the
next video in the queue when the current video finishes.

Preconditions
-------------
- Playlist exists with at least two videos.

Steps
-----
1. Navigate to /pl/[id].
2. Play the first video in the playlist.
3. Seek to the end of the video (simulate via 'ended' event or 'Skip').

Expected Result
---------------
Upon completion of the first video, the player automatically loads the source for
the second video in the list and begins playback.

Test approach
-------------
The auto-advance logic lives in PlaylistPageClient
(web/src/app/pl/[id]/PlaylistPageClient.tsx).  AutoAdvancePlayer attaches a native
'ended' event listener to the <video> element.  When the event fires,
handleVideoEnded() increments currentIndex causing React to re-render the player
with the next video's HLS source.

Two modes:
  live mode   — Discovers a real 2+ video playlist via the API. Dispatches the
                native 'ended' event on <video> to simulate video completion.
  mock mode   — Uses Playwright request routing to intercept API calls and return
                a fake 2-video playlist (hls_manifest_url=null). The
                PlaylistVideoPlayerWrapper then renders "Video not available." with a
                'Skip' button; clicking Skip calls onEnded() → handleVideoEnded(),
                exercising the same auto-advance state machine.

Route note: The deployed Next.js static export only generates /pl/_/ (see
generateStaticParams in page.tsx). All tests therefore navigate to /pl/_/ and
override the /api/playlists/_ response via route interception.

Environment variables
---------------------
APP_URL / WEB_BASE_URL : Base URL of the deployed frontend.
                         Default: https://ai-teammate.github.io/mytube
API_BASE_URL           : Backend API URL for live playlist discovery.
PLAYWRIGHT_HEADLESS    : Run headless (default: true).
PLAYWRIGHT_SLOW_MO     : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses PlaylistPage (Page Object) from testing/components/pages/playlist_page/.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module/function-scoped fixtures.
- No hardcoded URLs or credentials outside of config.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Route

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.playlist_page.playlist_page import PlaylistPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_AUTO_ADVANCE_TIMEOUT = 8_000 # ms

# The Next.js static export only generates one playlist page: /pl/_/
# All tests navigate to this path and intercept the API call for the "_" ID.
_STATIC_PLAYLIST_ID = "_"

# Fake video UUIDs injected via mock responses — unique to this test ticket
_FAKE_VIDEO_1_ID = "11111111-1111-1111-1111-111111232201"
_FAKE_VIDEO_2_ID = "22222222-2222-2222-2222-222222232202"

_FAKE_PLAYLIST_TITLE = "MYTUBE-232 Auto-Advance Test Playlist"
_FAKE_VIDEO_1_TITLE  = "First Auto-Advance Test Video"
_FAKE_VIDEO_2_TITLE  = "Second Auto-Advance Test Video"

_TESTER_USERNAME = "tester"


# ---------------------------------------------------------------------------
# Live playlist discovery
# ---------------------------------------------------------------------------

def _fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    """Issue a GET request, return parsed JSON or None on any error."""
    import urllib.request
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _discover_live_playlist_with_id(api_base_url: str) -> Optional[str]:
    """Find a public playlist ID for the tester user that has ≥ 2 videos.

    Returns the playlist ID string, or None if none found.
    """
    summaries = _fetch_json(
        f"{api_base_url.rstrip('/')}/api/users/{_TESTER_USERNAME}/playlists"
    )
    if not summaries or not isinstance(summaries, list):
        return None

    for summary in summaries:
        pid = summary.get("id")
        if not pid:
            continue
        detail = _fetch_json(f"{api_base_url.rstrip('/')}/api/playlists/{pid}")
        if detail and len(detail.get("videos", [])) >= 2:
            return pid
    return None


# ---------------------------------------------------------------------------
# Mock response builders
# ---------------------------------------------------------------------------

def _fake_playlist_body(playlist_id: str = _STATIC_PLAYLIST_ID) -> bytes:
    return json.dumps({
        "id": playlist_id,
        "title": _FAKE_PLAYLIST_TITLE,
        "owner_username": _TESTER_USERNAME,
        "videos": [
            {
                "id": _FAKE_VIDEO_1_ID,
                "title": _FAKE_VIDEO_1_TITLE,
                "thumbnail_url": None,
                "position": 1,
            },
            {
                "id": _FAKE_VIDEO_2_ID,
                "title": _FAKE_VIDEO_2_TITLE,
                "thumbnail_url": None,
                "position": 2,
            },
        ],
    }).encode()


def _fake_video_body(video_id: str, title: str) -> bytes:
    """hls_manifest_url=null → PlaylistVideoPlayerWrapper shows 'Video not available.'"""
    return json.dumps({
        "id": video_id,
        "title": title,
        "description": None,
        "hls_manifest_url": None,   # triggers 'Video not available.' overlay
        "thumbnail_url": None,
        "view_count": 0,
        "created_at": "2025-01-01T00:00:00Z",
        "status": "ready",
        "uploader": {"username": _TESTER_USERNAME, "avatar_url": None},
        "tags": [],
    }).encode()


_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
}


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def test_context(web_config: WebConfig) -> dict:
    """Determine test mode (live vs mock) and the playlist ID to use.

    Live mode: A real tester playlist with ≥ 2 videos was found via the API.
               The test navigates to /pl/_/ and intercepts just the playlist
               and video API calls so the discovered real data is served
               through mock routes.
               Advance is triggered via the native 'ended' event on <video>.

    Mock mode: No suitable live playlist found (or API_BASE_URL not set).
               The test intercepts /api/playlists/_ and returns a fake playlist
               with hls_manifest_url=null.  Advance is triggered via 'Skip'.

    Both modes navigate to /pl/_/ (the only statically generated playlist page).
    """
    api_base_url = os.getenv("API_BASE_URL", "").strip()
    live_pid = _discover_live_playlist_with_id(api_base_url) if api_base_url else None

    if live_pid:
        # Live mode: real playlist data, but still routed through /pl/_/
        live_detail = _fetch_json(
            f"{api_base_url.rstrip('/')}/api/playlists/{live_pid}"
        )
        return {
            "mode": "live",
            "playlist_id": _STATIC_PLAYLIST_ID,
            "total_videos": len(live_detail.get("videos", [])),
            "use_skip": False,       # will try 'ended' event first
            "live_playlist_detail": live_detail,
            "live_api_base_url": api_base_url,
        }

    return {
        "mode": "mock",
        "playlist_id": _STATIC_PLAYLIST_ID,
        "total_videos": 2,
        "use_skip": True,
        "live_playlist_detail": None,
        "live_api_base_url": None,
    }


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    """Launch a Chromium browser for the test module."""
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture
def page(browser: Browser, test_context: dict) -> Page:
    """Open a fresh browser context with mock API routes registered."""
    context: BrowserContext = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    _register_routes(pg, test_context)

    yield pg
    context.close()


def _register_routes(pg: Page, ctx: dict) -> None:
    """Register Playwright request interceptions for the test playlist/videos."""

    if ctx["mode"] == "live" and ctx.get("live_playlist_detail"):
        # Rewrite the real playlist under the static "_" ID so the page can load it.
        real_detail = ctx["live_playlist_detail"]
        rewritten = dict(real_detail)
        rewritten["id"] = _STATIC_PLAYLIST_ID
        playlist_body = json.dumps(rewritten).encode()

        def handle_playlist(route: Route) -> None:
            route.fulfill(status=200, headers=_JSON_HEADERS, body=playlist_body)

        pg.route("**/api/playlists/_", handle_playlist)
        # Video routes: pass through to real API (no interception needed in live mode)

    else:
        # Mock mode: serve fully synthetic responses
        playlist_body = _fake_playlist_body()
        video_1_body = _fake_video_body(_FAKE_VIDEO_1_ID, _FAKE_VIDEO_1_TITLE)
        video_2_body = _fake_video_body(_FAKE_VIDEO_2_ID, _FAKE_VIDEO_2_TITLE)

        pg.route("**/api/playlists/_", lambda r: r.fulfill(
            status=200, headers=_JSON_HEADERS, body=playlist_body
        ))
        pg.route(f"**/api/videos/{_FAKE_VIDEO_1_ID}", lambda r: r.fulfill(
            status=200, headers=_JSON_HEADERS, body=video_1_body
        ))
        pg.route(f"**/api/videos/{_FAKE_VIDEO_2_ID}", lambda r: r.fulfill(
            status=200, headers=_JSON_HEADERS, body=video_2_body
        ))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPlaylistAutoAdvance:
    """MYTUBE-232: Auto-advance to next video on playlist page."""

    @pytest.fixture(autouse=True)
    def setup(self, page: Page, test_context: dict, web_config: WebConfig) -> None:
        """Navigate to the playlist page before each test."""
        self._playlist_page = PlaylistPage(page)
        self._ctx = test_context
        self._web_config = web_config
        self._page = page
        self._playlist_page.navigate(
            web_config.base_url,
            _STATIC_PLAYLIST_ID,
        )
        # Allow React to settle after navigation
        page.wait_for_timeout(1000)

    # ── Sub-test 1: Page loads and queue is visible ──────────────────────────

    def test_playlist_page_loads_with_queue(self) -> None:
        """Playlist page renders the queue sidebar with at least 2 items."""
        count = self._playlist_page.get_queue_item_count()
        assert count >= 2, (
            f"Expected at least 2 queue items in the sidebar, but found {count}. "
            "The queue must show all playlist videos."
        )

    # ── Sub-test 2: First video is initially selected ────────────────────────

    def test_first_video_is_initially_current(self) -> None:
        """The first queue item is highlighted (aria-current='true') on load."""
        current_index = self._playlist_page.get_current_queue_index()
        assert current_index == 0, (
            f"Expected queue item 0 to be current (aria-current='true'), "
            f"but found current index: {current_index}. "
            "The first video must be selected when the playlist page first loads."
        )

    # ── Sub-test 3: 'Now playing (1/N)' label is shown ──────────────────────

    def test_now_playing_shows_first_video(self) -> None:
        """'Now playing (1/N)' label is present and correct below the player."""
        total = self._ctx["total_videos"]
        now_playing = self._playlist_page.get_now_playing_text()
        assert now_playing is not None, (
            "Expected a 'Now playing (…)' label below the player, "
            "but it was not found in the DOM."
        )
        expected = f"(1/{total})"
        assert expected in now_playing, (
            f"Expected 'Now playing' text to contain '{expected}', "
            f"but got: '{now_playing}'."
        )

    # ── Sub-test 4 (core): Auto-advance to next video ───────────────────────

    def test_player_auto_advances_to_next_video_on_end(self) -> None:
        """After the first video ends, the player auto-advances to video 2.

        Trigger mechanism:
          mock mode — clicks 'Skip' on the 'Video not available.' overlay.
                      Skip calls onEnded() directly, which is handleVideoEnded().
          live mode — dispatches the native 'ended' event on <video.video-js>,
                      which AutoAdvancePlayer's event listener forwards to
                      handleVideoEnded().

        Both paths exercise the same auto-advance state machine.
        """
        total = self._ctx["total_videos"]

        self._advance_one_video()

        # ── Assert: 'Now playing (2/N)' label is visible ──────────────────
        try:
            self._playlist_page.wait_for_now_playing_index(2, total)
        except Exception:
            now_playing = self._playlist_page.get_now_playing_text()
            current_idx = self._playlist_page.get_current_queue_index()
            pytest.fail(
                f"After first video ended, expected 'Now playing (2/{total})' "
                f"within {_AUTO_ADVANCE_TIMEOUT}ms, but label shows: "
                f"'{now_playing}'. Current queue index: {current_idx}. "
                "The player did not auto-advance to the second video."
            )

        # ── Assert: Second queue item is now highlighted ───────────────────
        advanced = self._playlist_page.wait_for_auto_advance(
            expected_index=1,
            timeout=_AUTO_ADVANCE_TIMEOUT,
        )
        assert advanced, (
            "After 'Now playing (2/…)' appeared, expected queue item 1 to "
            "have aria-current='true', but it does not. "
            "Queue highlight did not update to the second video."
        )

    # ── Sub-test 5: End-of-playlist overlay after last video ────────────────

    def test_end_of_playlist_shown_after_all_videos(self) -> None:
        """After advancing through all videos, 'End of playlist' overlay appears."""
        total = self._ctx["total_videos"]

        # Advance through every video in the playlist
        for _i in range(total):
            self._advance_one_video()

        assert self._playlist_page.is_end_of_playlist_shown(), (
            "After advancing through all videos in the playlist, expected the "
            "'End of playlist' overlay (data-testid='end-of-playlist') to be "
            "visible, but it was not found."
        )

    # ── Private advance helpers ───────────────────────────────────────────────

    def _advance_one_video(self) -> None:
        """Trigger the end of the current video using the appropriate mechanism."""
        if self._ctx["use_skip"]:
            self._advance_via_skip()
        else:
            self._advance_via_ended_event()

    def _advance_via_skip(self) -> None:
        """Wait for 'Video not available.' overlay and click the Skip button."""
        try:
            self._page.wait_for_selector(
                "p:has-text('Video not available.')",
                timeout=_PAGE_LOAD_TIMEOUT,
            )
        except Exception:
            # Overlay not visible — maybe this video has an HLS URL; fall back.
            self._advance_via_ended_event()
            return

        assert self._playlist_page.has_skip_button(), (
            "Expected a 'Skip' button on the 'Video not available.' overlay, "
            "but it was not found."
        )
        self._playlist_page.click_skip()
        # Small settle time for React state update
        self._page.wait_for_timeout(500)

    def _advance_via_ended_event(self) -> None:
        """Wait for <video.video-js> to exist and dispatch the 'ended' event."""
        found = self._playlist_page.wait_for_video_element(timeout=_PAGE_LOAD_TIMEOUT)
        assert found, (
            "Expected a <video.video-js> element in the DOM after Video.js "
            f"initialises, but it was not found within {_PAGE_LOAD_TIMEOUT}ms."
        )
        fired = self._playlist_page.fire_video_ended_event()
        assert fired, (
            "fire_video_ended_event() returned False: <video.video-js> "
            "was absent from the DOM at event-dispatch time."
        )
        self._page.wait_for_timeout(500)
