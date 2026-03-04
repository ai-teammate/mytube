"""
MYTUBE-230: View public playlist page — videos displayed sequentially by position.

Objective
---------
Verify that the public playlist page renders the correct videos in the order
defined by their position metadata.

Preconditions
-------------
A playlist exists with multiple videos assigned specific positions (1, 2, 3).
This test uses Playwright route interception to inject a deterministic mock
API response — no database or authentication is required.

Steps
-----
1. Register a Playwright route interceptor for GET /api/playlists/:id that
   returns a controlled mock playlist with three videos at positions 1, 2, 3.
2. Navigate to /pl/<playlist_id>/ without logging in.
3. Wait for the Queue panel to appear (page loaded successfully).
4. Assert the page title matches the mock playlist title.
5. Assert exactly three video items are rendered in the queue.
6. Assert the queue items appear in ascending position order:
   "Alpha Video" (pos 1) → "Beta Video" (pos 2) → "Gamma Video" (pos 3).
7. Assert the first item is marked as currently playing (aria-current="true").

Architecture
------------
- PlaylistPage (Page Object) from testing/components/pages/playlist_page/.
- WebConfig from testing/core/config/web_config.py.
- Playwright sync API with route interception for API mocking.
- No hardcoded URLs outside env-var helpers.
- No authentication needed — the playlist page is publicly accessible.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Deployed frontend base URL.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Headless mode (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from playwright.sync_api import Browser, Page, Route, Request, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.playlist_page.playlist_page import PlaylistPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The deployed GitHub Pages site generates a static shell for the playlist route
# using the placeholder ID "_" (via generateStaticParams in web/src/app/pl/[id]/page.tsx).
# Real playlist IDs are designed to fall back to this shell via the 404.html SPA
# mechanism.  We navigate to the static shell directly so the test does not depend
# on GitHub Pages 404-routing behavior.
_PLAYLIST_ID = "_"
_PAGE_LOAD_TIMEOUT = 30_000   # ms
_QUEUE_LOAD_TIMEOUT = 20_000  # ms

# Mock API response — three videos in ascending position order.
# The real API returns videos ORDER BY position ASC; we mirror that here.
_MOCK_PLAYLIST = {
    "id": "00000000-0000-0000-0000-000000000230",
    "title": "Test Playlist MYTUBE-230",
    "owner_username": "ci_test_user",
    "videos": [
        {
            "id": "00000000-0000-0000-0001-000000000001",
            "title": "Alpha Video",
            "thumbnail_url": None,
            "position": 1,
        },
        {
            "id": "00000000-0000-0000-0001-000000000002",
            "title": "Beta Video",
            "thumbnail_url": None,
            "position": 2,
        },
        {
            "id": "00000000-0000-0000-0001-000000000003",
            "title": "Gamma Video",
            "thumbnail_url": None,
            "position": 3,
        },
    ],
}

_EXPECTED_TITLES_IN_ORDER = ["Alpha Video", "Beta Video", "Gamma Video"]


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------


def _handle_playlist_route(route: Route, request: Request) -> None:
    """Intercept GET /api/playlists/:id and return the mock playlist."""
    if request.method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_MOCK_PLAYLIST),
        )
    else:
        route.continue_()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def playlist_page_loaded(browser: Browser, web_config: WebConfig):
    """Navigate to the playlist page with mocked API and yield loaded state.

    Yields a dict with keys:
      page          – the Playwright Page object
      playlist_page – the PlaylistPage page-object
      playlist_id   – the UUID used in the URL
    """
    context = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Intercept all GET /api/playlists/:id requests so the page receives
    # deterministic mock data regardless of the real API state.
    page.route("**/api/playlists/*", _handle_playlist_route)

    playlist_pg = PlaylistPage(page)
    playlist_pg.navigate(web_config.base_url, _PLAYLIST_ID)

    # Wait for the page to exit the loading state.
    playlist_pg.wait_for_loaded(timeout=_QUEUE_LOAD_TIMEOUT)

    yield {
        "page": page,
        "playlist_page": playlist_pg,
        "playlist_id": _PLAYLIST_ID,
    }

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPublicPlaylistPageLoads:
    """MYTUBE-230 — Playlist page is publicly accessible (no auth required)."""

    def test_page_loads_without_authentication(
        self, playlist_page_loaded: dict
    ) -> None:
        """The playlist page must load without any login.

        Verifies the page is NOT in a not-found or error state.
        """
        pl_page: PlaylistPage = playlist_page_loaded["playlist_page"]
        assert not pl_page.is_not_found(), (
            "Expected the playlist page to load successfully, "
            "but 'Playlist not found.' was displayed — the page may not be "
            "accessible without authentication or the route is not working."
        )
        assert not pl_page.has_error(), (
            "Expected the playlist page to load without errors, "
            "but an error alert was displayed."
        )

    def test_queue_panel_is_visible(self, playlist_page_loaded: dict) -> None:
        """The Queue panel must be visible after the page loads."""
        pl_page: PlaylistPage = playlist_page_loaded["playlist_page"]
        assert pl_page.is_queue_visible(), (
            "Expected the Queue panel (h2 'Queue') to be visible, "
            "but it was not found on the page."
        )

    def test_page_title_matches_playlist_title(
        self, playlist_page_loaded: dict
    ) -> None:
        """The <h1> element must display the playlist title."""
        pl_page: PlaylistPage = playlist_page_loaded["playlist_page"]
        title = pl_page.get_page_title()
        assert title is not None, (
            "Expected a <h1> element with the playlist title, but none was found."
        )
        assert title == _MOCK_PLAYLIST["title"], (
            f"Expected page title '{_MOCK_PLAYLIST['title']}', got '{title}'."
        )


class TestPlaylistVideoOrdering:
    """MYTUBE-230 — Videos are displayed in ascending position order."""

    def test_queue_has_correct_number_of_items(
        self, playlist_page_loaded: dict
    ) -> None:
        """The queue must contain exactly three video items."""
        pl_page: PlaylistPage = playlist_page_loaded["playlist_page"]
        count = pl_page.get_queue_item_count()
        assert count == 3, (
            f"Expected 3 video items in the queue, but found {count}. "
            "All three videos at positions 1, 2, and 3 must be rendered."
        )

    def test_videos_displayed_in_ascending_position_order(
        self, playlist_page_loaded: dict
    ) -> None:
        """Queue items must appear in ascending position order (1 → 2 → 3).

        The mock API response has videos at positions 1, 2, 3 — matching
        the ORDER BY position ASC that the real API enforces.
        """
        pl_page: PlaylistPage = playlist_page_loaded["playlist_page"]
        actual_titles = pl_page.get_queue_item_titles()
        assert actual_titles == _EXPECTED_TITLES_IN_ORDER, (
            f"Expected queue order {_EXPECTED_TITLES_IN_ORDER}, "
            f"but got {actual_titles}. "
            "Videos must be displayed sorted ascending by their position value."
        )

    def test_first_position_video_is_first_in_queue(
        self, playlist_page_loaded: dict
    ) -> None:
        """The video at position 1 must appear first in the queue."""
        pl_page: PlaylistPage = playlist_page_loaded["playlist_page"]
        titles = pl_page.get_queue_item_titles()
        assert titles, "Expected at least one queue item, but none were found."
        assert titles[0] == "Alpha Video", (
            f"Expected 'Alpha Video' (position 1) to be first in queue, "
            f"but got '{titles[0]}'."
        )

    def test_last_position_video_is_last_in_queue(
        self, playlist_page_loaded: dict
    ) -> None:
        """The video at position 3 must appear last in the queue."""
        pl_page: PlaylistPage = playlist_page_loaded["playlist_page"]
        titles = pl_page.get_queue_item_titles()
        assert titles, "Expected at least one queue item, but none were found."
        assert titles[-1] == "Gamma Video", (
            f"Expected 'Gamma Video' (position 3) to be last in queue, "
            f"but got '{titles[-1]}'."
        )

    def test_first_queue_item_is_marked_as_currently_playing(
        self, playlist_page_loaded: dict
    ) -> None:
        """The first queue item must have aria-current='true' on load.

        The playlist page auto-selects the first video (index 0) on load,
        so the position-1 video must be the active item.
        """
        pl_page: PlaylistPage = playlist_page_loaded["playlist_page"]
        playing_title = pl_page.get_first_playing_item_title()
        assert playing_title == "Alpha Video", (
            f"Expected 'Alpha Video' (position 1) to be the currently-playing item "
            f"(aria-current='true'), but got '{playing_title}'."
        )
