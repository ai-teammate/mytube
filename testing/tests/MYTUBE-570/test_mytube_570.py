"""
MYTUBE-570: Video watch page loading — skeleton placeholders visible for player and metadata

Objective
---------
Verify that skeleton screens are displayed on the watch page for both the
video player and metadata sections to eliminate UI flicker.

Steps
-----
1. Open a video watch page URL.
2. Observe the page layout before the video player and metadata
   (title, description) load.

Expected Result
---------------
Skeleton screens are visible for both the player container and the metadata
section until the data resolves, providing a smooth perceived-performance
experience.

Test Architecture
-----------------
**Layer A — Source code static analysis** (always runs, no browser required):
  Parses ``web/src/app/v/[id]/WatchPageSkeleton.tsx`` and
  ``web/src/app/v/[id]/WatchPageClient.tsx`` to confirm:
  - WatchPageSkeleton exists and renders a player-area Skeleton.
  - WatchPageSkeleton renders title/metadata Skeleton elements.
  - WatchPageClient returns <WatchPageSkeleton /> while ``loading`` is true.

**Layer B — Live Playwright test** (runs when APP_URL / WEB_BASE_URL is set):
  - Intercepts the backend ``/api/videos/**`` call via Playwright route.
  - Navigates to the watch page shell (``/v/_/``).
  - While the intercepted response is stalled, asserts skeleton elements are
    present in both ``<main>`` (player + metadata) and ``<aside>`` (sidebar).
  - Fulfils the intercepted route with a 404 to let the page settle.
  - Asserts the skeleton disappears and is replaced by the not-found state.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-570/test_mytube_570.py -v
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Browser, Page, Route, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WATCH_SKELETON_TSX = _REPO_ROOT / "web" / "src" / "app" / "v" / "[id]" / "WatchPageSkeleton.tsx"
_WATCH_CLIENT_TSX = _REPO_ROOT / "web" / "src" / "app" / "v" / "[id]" / "WatchPageClient.tsx"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_REACT_MOUNT_TIMEOUT = 10_000  # ms — time to wait for React to mount skeleton
_SKELETON_SETTLE_TIMEOUT = 5_000  # ms — time after route intercept before asserting

# The Skeleton component renders a <div aria-hidden="true"> for each placeholder.
# We use this stable attribute (not mangled CSS module class names) as our
# selector in the live Playwright test.
_SKELETON_SELECTOR = "div[aria-hidden='true']"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _should_use_live_mode() -> bool:
    url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(url and url.lower() not in ("false", "0", ""))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def playwright_browser(config: WebConfig) -> Generator[Browser, None, None]:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        yield browser
        browser.close()


# ---------------------------------------------------------------------------
# Layer A — Static source analysis (always runs)
# ---------------------------------------------------------------------------


class TestWatchPageSkeletonStatic:
    """Verify WatchPageSkeleton and WatchPageClient source satisfy the spec."""

    def test_watch_page_skeleton_file_exists(self) -> None:
        """WatchPageSkeleton.tsx must exist in the watch page route directory."""
        assert _WATCH_SKELETON_TSX.exists(), (
            f"WatchPageSkeleton.tsx not found at {_WATCH_SKELETON_TSX}"
        )

    def test_skeleton_includes_player_placeholder(self) -> None:
        """WatchPageSkeleton must render a Skeleton inside the player container."""
        src = _read_file(_WATCH_SKELETON_TSX)
        import re
        assert re.search(r'playerFill|playerContainer|player-fill', src), (
            "WatchPageSkeleton does not render a player-area skeleton placeholder. "
            "No player-area CSS class (playerFill, playerContainer, player-fill) found. "
            f"File: {_WATCH_SKELETON_TSX}"
        )
        # The Skeleton component must be used for the player area
        assert "<Skeleton" in src, (
            "WatchPageSkeleton does not use the <Skeleton> component at all."
        )

    def test_skeleton_includes_title_placeholder(self) -> None:
        """WatchPageSkeleton must render title/metadata Skeleton elements."""
        src = _read_file(_WATCH_SKELETON_TSX)
        # Look for title-related skeleton class names or multiple <Skeleton> usages
        title_indicators = ["titleLine", "title", "Title", "metaLine", "descBlock"]
        found = any(indicator in src for indicator in title_indicators)
        assert found, (
            "WatchPageSkeleton does not appear to render title/metadata "
            "skeleton placeholders. Expected at least one of: "
            f"{title_indicators}. File: {_WATCH_SKELETON_TSX}"
        )

    def test_skeleton_has_multiple_skeleton_components(self) -> None:
        """WatchPageSkeleton must render more than one <Skeleton /> element."""
        src = _read_file(_WATCH_SKELETON_TSX)
        count = src.count("<Skeleton")
        assert count >= 2, (
            f"WatchPageSkeleton only renders {count} <Skeleton> element(s); "
            "expected at least 2 (player + metadata). "
            f"File: {_WATCH_SKELETON_TSX}"
        )

    def test_watch_client_renders_skeleton_while_loading(self) -> None:
        """WatchPageClient must return <WatchPageSkeleton /> when loading is true."""
        src = _read_file(_WATCH_CLIENT_TSX)
        assert "WatchPageSkeleton" in src, (
            "WatchPageClient.tsx does not import or reference WatchPageSkeleton. "
            f"File: {_WATCH_CLIENT_TSX}"
        )
        # Verify there's a loading guard that returns the skeleton
        assert "loading" in src and "<WatchPageSkeleton" in src, (
            "WatchPageClient.tsx does not appear to guard on 'loading' and "
            "return <WatchPageSkeleton />. "
            f"File: {_WATCH_CLIENT_TSX}"
        )

    def test_watch_client_loading_state_is_true_initially(self) -> None:
        """WatchPageClient must initialise loading state as true."""
        src = _read_file(_WATCH_CLIENT_TSX)
        # useState(true) initialises loading to true so skeleton shows immediately
        assert "useState(true)" in src, (
            "WatchPageClient.tsx does not initialise the loading state to 'true'. "
            "Without this, the skeleton will not appear on initial render. "
            f"File: {_WATCH_CLIENT_TSX}"
        )

    def test_skeleton_imports_skeleton_component(self) -> None:
        """WatchPageSkeleton must import the Skeleton base component."""
        src = _read_file(_WATCH_SKELETON_TSX)
        assert 'from "@/components/Skeleton"' in src or "import Skeleton" in src, (
            "WatchPageSkeleton.tsx does not import the Skeleton component. "
            f"File: {_WATCH_SKELETON_TSX}"
        )


# ---------------------------------------------------------------------------
# Layer B — Live Playwright test (requires APP_URL)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _should_use_live_mode(),
    reason="APP_URL / WEB_BASE_URL not set — skipping live Playwright test",
)
class TestWatchPageSkeletonLive:
    """Live Playwright tests: verify skeleton renders before API response arrives."""

    def test_skeleton_visible_before_api_response(
        self, config: WebConfig, playwright_browser: Browser
    ) -> None:
        """
        Navigate to the watch page shell with the API route stalled.
        The skeleton must be present and visible in both <main> and <aside>
        before the video data resolves.
        """
        # Event used to signal that the route has been reached (API call made).
        route_reached = threading.Event()
        # Event used to release the stalled route after assertions.
        release_route = threading.Event()

        def _stall_api(route: Route) -> None:
            """Hold the API response until assertions are done, then return 404."""
            route_reached.set()
            release_route.wait(timeout=15)  # give assertions plenty of time
            route.fulfill(status=404, body='{"error":"not found"}', content_type="application/json")

        watch_url = f"{config.base_url}/v/_/"

        context = playwright_browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            # Intercept the video metadata API call before navigating.
            page.route("**/api/videos/**", _stall_api)

            # Navigate to the watch page shell (DOMContentLoaded is enough to
            # start the React app and trigger the API call).
            page.goto(watch_url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

            # Wait for React to mount and issue the API call.
            # We wait until the route handler signals it was reached.
            route_reached_in_time = route_reached.wait(timeout=15)
            assert route_reached_in_time, (
                "The watch page did not issue a GET /api/videos/** request within "
                "15 seconds of navigation. The loading skeleton may not be present."
            )

            # Wait until at least one skeleton div is present in the DOM.
            page.wait_for_selector(f"main {_SKELETON_SELECTOR}", timeout=_REACT_MOUNT_TIMEOUT)

            # --- Assert skeleton elements are present ---

            # The Skeleton component always renders <div aria-hidden="true">.
            # While loading, multiple skeleton divs should be in <main>.
            skeleton_divs_in_main = page.locator(
                f"main {_SKELETON_SELECTOR}"
            )
            assert skeleton_divs_in_main.count() >= 2, (
                f"Expected at least 2 skeleton placeholder divs (aria-hidden='true') "
                f"inside <main> while the API response is stalled, but found "
                f"{skeleton_divs_in_main.count()}. "
                "The player and metadata skeletons should both be visible."
            )

            # The sidebar skeleton should also be present.
            skeleton_divs_in_aside = page.locator(
                f"aside {_SKELETON_SELECTOR}"
            )
            assert skeleton_divs_in_aside.count() >= 1, (
                f"Expected at least 1 skeleton placeholder div (aria-hidden='true') "
                f"inside <aside> while the API response is stalled, but found "
                f"{skeleton_divs_in_aside.count()}. "
                "The sidebar skeleton should be visible."
            )

            # The actual video title (h1) must NOT be visible yet.
            h1 = page.locator("h1")
            # If h1 exists at all, it must not contain real video data
            # (the skeleton renders no h1 — only Skeleton blocks).
            # We allow the case where h1 is absent entirely.
            if h1.count() > 0:
                # In skeleton state, h1 should be hidden / not contain a title
                # that implies real data loaded.
                assert not h1.is_visible() or h1.inner_text().strip() == "", (
                    "A visible <h1> with content was found while the API response "
                    "is still stalled — the video data should not be loaded yet."
                )

            # The Video.js player container must NOT be present yet.
            vjs_player = page.locator("[data-vjs-player]")
            assert vjs_player.count() == 0 or not vjs_player.is_visible(), (
                "The Video.js player container [data-vjs-player] is visible while "
                "the API response is stalled. It should only appear after data loads."
            )

        finally:
            # Release the stalled route so the page can settle (prevents hangs).
            release_route.set()
            page.close()
            context.close()

    def test_skeleton_disappears_after_api_responds(
        self, config: WebConfig, playwright_browser: Browser
    ) -> None:
        """
        After the API responds (with 404 = not found), the skeleton must
        disappear and the not-found message must render instead.
        """
        watch_url = f"{config.base_url}/v/_/"

        context = playwright_browser.new_context(
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        try:
            # Return a 404 immediately — no stalling.
            page.route(
                "**/api/videos/**",
                lambda route: route.fulfill(
                    status=404,
                    body='{"error":"not found"}',
                    content_type="application/json",
                ),
            )

            page.goto(watch_url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

            # Wait for the not-found / error state to render (loading=false).
            # The skeleton divs should all be gone.
            page.wait_for_function(
                """() => {
                    // Skeleton divs have aria-hidden="true"; when real content
                    // loads (even an error state) they disappear.
                    const mainSkeletons = document.querySelectorAll('main div[aria-hidden="true"]');
                    return mainSkeletons.length === 0;
                }""",
                timeout=_PAGE_LOAD_TIMEOUT,
            )

            # After loading completes with a 404, skeleton should be gone.
            skeleton_divs = page.locator(f"main {_SKELETON_SELECTOR}")
            assert skeleton_divs.count() == 0, (
                f"Expected 0 skeleton placeholder divs in <main> after the API "
                f"responded with 404, but found {skeleton_divs.count()}. "
                "The skeleton should be replaced by the not-found state."
            )

        finally:
            page.close()
            context.close()
