"""
MYTUBE-521: Dashboard client-side filtering — video grid updates based on playlist selection.

Objective
---------
Verify that selecting a playlist chip filters the video grid client-side without
a page reload, and that clicking "All" restores the full list of videos.

Preconditions
-------------
User has videos, some of which are associated with specific playlists.

Steps
-----
1. Navigate to the Dashboard.
2. Click on a playlist chip that contains a subset of the user's videos.
3. Click the "All" chip.

Expected Result
---------------
The video grid updates immediately to show only videos associated with the
selected playlist. Clicking "All" restores the full list of videos. Filtering
happens client-side using existing data.

Architecture
------------
- Fake Firebase user is injected via add_init_script (no real credentials needed).
- Playwright route interception mocks:
    GET **/api/me/videos         → 3 known videos
    GET **/api/me/playlists      → 1 playlist
    GET **/api/playlists/**      → playlist detail (2 of the 3 videos)
- DashboardPage (Page Object) encapsulates all dashboard interactions.
- WebConfig from testing/core/config/web_config.py provides the deployed URL.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_FILTER_WAIT_TIMEOUT = 5_000  # ms

# Mock data — deterministic, no external dependencies
_PLAYLIST_ID = "pl-521-test"
_PLAYLIST_NAME = "My Test Playlist"

# Video IDs — two are in the playlist, one is not
_VIDEO_ALPHA_ID = "vid-521-alpha"
_VIDEO_BETA_ID = "vid-521-beta"
_VIDEO_GAMMA_ID = "vid-521-gamma"

_MOCK_VIDEOS_RESPONSE = json.dumps([
    {
        "id": _VIDEO_ALPHA_ID,
        "title": "Video Alpha",
        "status": "ready",
        "thumbnail_url": None,
        "view_count": 10,
        "created_at": "2025-01-01T00:00:00Z",
        "description": None,
        "category_id": None,
        "tags": [],
    },
    {
        "id": _VIDEO_BETA_ID,
        "title": "Video Beta",
        "status": "ready",
        "thumbnail_url": None,
        "view_count": 20,
        "created_at": "2025-01-02T00:00:00Z",
        "description": None,
        "category_id": None,
        "tags": [],
    },
    {
        "id": _VIDEO_GAMMA_ID,
        "title": "Video Gamma",
        "status": "ready",
        "thumbnail_url": None,
        "view_count": 30,
        "created_at": "2025-01-03T00:00:00Z",
        "description": None,
        "category_id": None,
        "tags": [],
    },
])

_MOCK_PLAYLISTS_RESPONSE = json.dumps([
    {
        "id": _PLAYLIST_ID,
        "title": _PLAYLIST_NAME,
        "owner_username": "ci-user-521",
        "video_count": 2,
        "created_at": "2025-01-01T00:00:00Z",
    }
])

_MOCK_PLAYLIST_DETAIL_RESPONSE = json.dumps({
    "id": _PLAYLIST_ID,
    "title": _PLAYLIST_NAME,
    "owner_username": "ci-user-521",
    "videos": [
        {"id": _VIDEO_ALPHA_ID, "title": "Video Alpha", "thumbnail_url": None, "position": 0},
        {"id": _VIDEO_BETA_ID, "title": "Video Beta", "thumbnail_url": None, "position": 1},
    ],
})

# Injected before each page load to provide a fake authenticated Firebase user.
# This intercepts onAuthStateChanged so the app treats the fake user as signed in
# and proceeds to fetch videos and playlists.
_FAKE_AUTH_SCRIPT = """
(function () {
    var _origDefProp = Object.defineProperty;
    Object.defineProperty = function (target, prop, descriptor) {
        if (prop === 'hg' && descriptor && typeof descriptor.get === 'function') {
            window.__fakeAuth521Activated = true;
            return _origDefProp(target, prop, {
                enumerable: descriptor.enumerable,
                configurable: true,
                get: function () {
                    return function fakeOnAuthStateChanged(auth, nextOrObserver) {
                        var nextCb;
                        if (typeof nextOrObserver === 'function') {
                            nextCb = nextOrObserver;
                        } else if (
                            nextOrObserver !== null &&
                            typeof nextOrObserver === 'object' &&
                            typeof nextOrObserver.next === 'function'
                        ) {
                            nextCb = nextOrObserver.next;
                        }
                        var fakeUser = {
                            uid: 'ci-uid-mytube-521',
                            email: 'ci@mytube521.test',
                            displayName: 'CI Tester 521',
                            photoURL: null,
                            emailVerified: true,
                            isAnonymous: false,
                            getIdToken: function () {
                                return Promise.resolve('ci-fake-id-token-521');
                            }
                        };
                        setTimeout(function () {
                            if (typeof nextCb === 'function') {
                                nextCb(fakeUser);
                            }
                        }, 150);
                        return function () {};
                    };
                }
            });
        }
        return _origDefProp.apply(Object, arguments);
    };
})();
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="function")
def dashboard_page_with_mocks(browser: Browser, web_config: WebConfig):
    """Navigate to /dashboard with mocked API and fake auth. Yields DashboardPage."""
    context: BrowserContext = browser.new_context()
    context.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    context.add_init_script(script=_FAKE_AUTH_SCRIPT)

    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Mock: GET /api/me/videos → 3 videos
    page.route(
        "**/api/me/videos",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=_MOCK_VIDEOS_RESPONSE,
        ),
    )

    # Mock: GET /api/me/playlists → 1 playlist
    page.route(
        "**/api/me/playlists",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=_MOCK_PLAYLISTS_RESPONSE,
        ),
    )

    # Mock: GET /api/playlists/<id> → playlist detail with 2 videos
    page.route(
        f"**/api/playlists/{_PLAYLIST_ID}",
        lambda route: route.fulfill(
            status=200,
            content_type="application/json",
            body=_MOCK_PLAYLIST_DETAIL_RESPONSE,
        ),
    )

    # Navigate to the dashboard
    page.goto(web_config.dashboard_url(), wait_until="domcontentloaded")

    dashboard = DashboardPage(page)
    dashboard.wait_for_load(timeout=_PAGE_LOAD_TIMEOUT)

    yield dashboard, page

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDashboardPlaylistChipFiltering:
    """MYTUBE-521: Dashboard client-side filtering by playlist chip."""

    def test_all_videos_shown_initially(
        self,
        dashboard_page_with_mocks,
    ) -> None:
        """Step 1: Navigate to Dashboard — all 3 videos are visible before filtering."""
        dashboard, page = dashboard_page_with_mocks

        # Wait for the playlist chips to appear (they load after fetchPlaylists)
        dashboard.wait_for_playlist_chips(timeout=_PAGE_LOAD_TIMEOUT)

        card_count = dashboard.get_video_card_count(timeout=_PAGE_LOAD_TIMEOUT)
        assert card_count == 3, (
            f"Expected 3 video cards to be visible on the dashboard before any "
            f"filtering, but found {card_count}. "
            f"Page URL: {page.url!r}. "
            f"Card titles found: {dashboard.get_video_card_titles()!r}"
        )

    def test_playlist_chip_filters_video_grid(
        self,
        dashboard_page_with_mocks,
    ) -> None:
        """Step 2: Clicking a playlist chip shows only videos in that playlist."""
        dashboard, page = dashboard_page_with_mocks

        # Pre-condition: wait for chips and verify initial state
        dashboard.wait_for_playlist_chips(timeout=_PAGE_LOAD_TIMEOUT)
        initial_count = dashboard.get_video_card_count(timeout=_PAGE_LOAD_TIMEOUT)
        assert initial_count == 3, (
            f"Pre-condition failed: expected 3 videos before filtering, got {initial_count}. "
            f"Titles: {dashboard.get_video_card_titles()!r}"
        )

        # Click the playlist chip
        dashboard.click_playlist_chip(_PLAYLIST_NAME)

        # After clicking the chip, only the 2 playlist videos should be visible
        dashboard.wait_for_video_card_count(2, timeout=_FILTER_WAIT_TIMEOUT)
        filtered_count = dashboard.get_video_card_count()
        assert filtered_count == 2, (
            f"Expected 2 video cards after clicking playlist chip '{_PLAYLIST_NAME}', "
            f"but found {filtered_count}. "
            f"Titles visible: {dashboard.get_video_card_titles()!r}. "
            f"Expected only 'Video Alpha' and 'Video Beta' (both in the mock playlist). "
            f"'Video Gamma' should have been filtered out."
        )

        # Verify that the correct videos are shown
        assert dashboard.is_video_card_visible_by_title("Video Alpha"), (
            "Expected 'Video Alpha' (in playlist) to be visible after filtering, "
            f"but it was not. Visible cards: {dashboard.get_video_card_titles()!r}"
        )
        assert dashboard.is_video_card_visible_by_title("Video Beta"), (
            "Expected 'Video Beta' (in playlist) to be visible after filtering, "
            f"but it was not. Visible cards: {dashboard.get_video_card_titles()!r}"
        )

        # Verify the non-playlist video is gone
        gamma_visible = dashboard.is_video_card_visible_by_title("Video Gamma", timeout=500)
        assert not gamma_visible, (
            "Expected 'Video Gamma' (NOT in playlist) to be hidden after filtering, "
            f"but it is still visible. Visible cards: {dashboard.get_video_card_titles()!r}"
        )

    def test_all_chip_restores_full_video_list(
        self,
        dashboard_page_with_mocks,
    ) -> None:
        """Step 3: Clicking 'All' chip restores the full list of videos."""
        dashboard, page = dashboard_page_with_mocks

        # Pre-condition: wait for chips
        dashboard.wait_for_playlist_chips(timeout=_PAGE_LOAD_TIMEOUT)

        # Apply the playlist filter first
        dashboard.click_playlist_chip(_PLAYLIST_NAME)
        dashboard.wait_for_video_card_count(2, timeout=_FILTER_WAIT_TIMEOUT)

        # Click "All" to restore the full list
        dashboard.click_all_chip()

        # All 3 videos should be visible again
        dashboard.wait_for_video_card_count(3, timeout=_FILTER_WAIT_TIMEOUT)
        restored_count = dashboard.get_video_card_count()
        assert restored_count == 3, (
            f"Expected 3 video cards after clicking 'All' chip, but found {restored_count}. "
            f"Titles visible: {dashboard.get_video_card_titles()!r}. "
            f"Clicking 'All' should restore the full unfiltered video grid."
        )

        # Confirm all three specific titles are present
        for title in ("Video Alpha", "Video Beta", "Video Gamma"):
            assert dashboard.is_video_card_visible_by_title(title), (
                f"Expected '{title}' to be visible after clicking 'All', "
                f"but it was not. Visible: {dashboard.get_video_card_titles()!r}"
            )
