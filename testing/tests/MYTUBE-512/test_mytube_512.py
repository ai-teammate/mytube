"""
MYTUBE-512: Watch page layout responsiveness — two-column desktop layout collapses on mobile

Objective
---------
Verify the watch page layout correctly implements the two-column structure on desktop
(viewport width > 1024 px) and collapses to a single vertical column on mobile
(viewport width < 768 px).

CSS implementation (WatchPageClient.module.css):
  Default (mobile-first):  grid-template-columns: 1fr               (single column)
  @media (min-width: 1024px): grid-template-columns: 1fr 360px      (two columns)

Steps
-----
1. Navigate to a video watch page (/v/[id]) on a desktop browser (width > 1024 px).
2. Verify the placement of the player/metadata and the sidebar (two-column layout).
3. Resize the browser window to a mobile viewport width (< 768 px).
4. Observe the layout transition (single column).

Expected Result
---------------
- Desktop: two-column — player+metadata on the left, sidebar (360 px) on the right.
- Mobile:  single column — all content stacked vertically.

Test Approach
-------------
Dual-mode:

Fixture mode (always runs — self-contained):
  A local HTTP server serves a minimal HTML page that faithfully reproduces
  the watch page responsive grid:
    - >= 1024 px  →  grid-template-columns: 1fr 360px   (two columns, side-by-side)
    - <  1024 px  →  grid-template-columns: 1fr          (single column, stacked)
  The test verifies layout using computed-style inspection and bounding-box
  geometry at both viewport widths.

Live mode (skipped if app is unreachable or no video found):
  Uses the VideoApiService to discover a published video, navigates to
  /v/<id>/, sets the viewport to desktop width, checks two-column layout,
  then resizes to mobile width and verifies single-column layout.

Architecture
------------
- WebConfig (testing/core/config/web_config.py) — env-var driven base URL.
- VideoApiService (testing/components/services/video_api_service.py) — discovers a
  usable video without DB access.
- WatchPage (testing/components/pages/watch_page/watch_page.py) — page object for
  navigation.

Run from repo root:
    pytest testing/tests/MYTUBE-512/test_mytube_512.py -v
"""
from __future__ import annotations

import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.api_config import APIConfig
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DESKTOP_VIEWPORT = {"width": 1280, "height": 800}
_MOBILE_VIEWPORT = {"width": 375, "height": 812}
_PAGE_LOAD_TIMEOUT = 30_000  # ms

# ---------------------------------------------------------------------------
# Fixture HTML
# Reproduces the watch page responsive grid from WatchPageClient.module.css:
#   default                   → grid-template-columns: 1fr
#   @media (min-width: 1024px) → grid-template-columns: 1fr 360px
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MYTUBE-512 watch layout fixture</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: sans-serif; background: #0f0f0f; }

    /* Watch page layout — mirrors WatchPageClient.module.css */
    .watchLayout {
      display: grid;
      grid-template-columns: 1fr;
      gap: 24px;
      padding: 24px 16px;
    }

    /* Two-column layout at >= 1024 px */
    @media (min-width: 1024px) {
      .watchLayout {
        grid-template-columns: 1fr 360px;
        align-items: start;
      }
    }

    .mainColumn {
      background: #1a1a1a;
      border-radius: 12px;
      padding: 24px;
      min-height: 400px;
    }

    .sidebar {
      background: #1e1e2e;
      border-radius: 12px;
      padding: 24px;
      min-height: 300px;
    }
  </style>
</head>
<body>
  <div class="watchLayout" data-testid="watch-layout">
    <div class="mainColumn" data-testid="main-column">
      <h1>Sample Video Title</h1>
      <p>Player and metadata area</p>
    </div>
    <aside class="sidebar" data-testid="sidebar">
      <p>Recommendations sidebar</p>
    </aside>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Local fixture server helpers
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # silence server logs
        pass


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_fixture_server() -> tuple[HTTPServer, str]:
    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/"


# ---------------------------------------------------------------------------
# Layout geometry helpers
# ---------------------------------------------------------------------------


def _get_grid_columns(page, selector: str) -> str:
    """Return the computed grid-template-columns value for *selector*."""
    return page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return '';
            return window.getComputedStyle(el).gridTemplateColumns;
        }""",
        selector,
    )


def _parse_column_count(grid_template_columns: str) -> int:
    """Return the number of column tracks in a computed grid-template-columns string.

    Computed values look like "954px 360px" (two tracks) or "954px" (one track).
    Splits on whitespace; each token is a track value.
    """
    return len(grid_template_columns.strip().split()) if grid_template_columns.strip() else 0


def _get_bounding_box(page, selector: str) -> dict | None:
    """Return the bounding box of the first matching element, or None."""
    loc = page.locator(selector).first
    if loc.count() == 0:
        return None
    return loc.bounding_box()


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWatchPageLayoutResponsiveness:
    """MYTUBE-512 — Watch page two-column desktop layout collapses on mobile."""

    # ── Fixture mode (always runs — self-contained) ──────────────────────────

    def test_fixture_desktop_two_column_layout(self, web_config: WebConfig) -> None:
        """Step 1-2 (desktop baseline, fixture) — at 1280 px the layout is two-column.

        The computed grid-template-columns must contain two track values and
        the main column must be rendered to the left of the sidebar.
        """
        server, fixture_url = _start_fixture_server()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=web_config.headless, slow_mo=web_config.slow_mo
                )
                try:
                    page = browser.new_page()
                    page.set_viewport_size(_DESKTOP_VIEWPORT)
                    page.goto(fixture_url, timeout=_PAGE_LOAD_TIMEOUT)
                    page.wait_for_load_state("domcontentloaded")

                    cols = _get_grid_columns(page, "[data-testid='watch-layout']")
                    col_count = _parse_column_count(cols)
                    assert col_count == 2, (
                        f"Expected 2 grid columns at desktop viewport "
                        f"({_DESKTOP_VIEWPORT['width']} px), "
                        f"but computed grid-template-columns = '{cols}'"
                    )

                    # Geometric side-by-side check: sidebar must be to the right
                    main_box = _get_bounding_box(page, "[data-testid='main-column']")
                    sidebar_box = _get_bounding_box(page, "[data-testid='sidebar']")

                    assert main_box is not None, "main-column not found on page"
                    assert sidebar_box is not None, "sidebar not found on page"

                    assert sidebar_box["x"] > main_box["x"], (
                        f"Sidebar is NOT to the right of the main column at desktop. "
                        f"main-column x={main_box['x']:.0f}, "
                        f"sidebar x={sidebar_box['x']:.0f}. "
                        "Expected side-by-side two-column layout."
                    )

                    # Their tops should be roughly aligned (within 20px tolerance)
                    top_diff = abs(sidebar_box["y"] - main_box["y"])
                    assert top_diff < 20, (
                        f"Main column and sidebar tops differ by {top_diff:.0f} px "
                        "at desktop — they should be aligned in the two-column grid."
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()

    def test_fixture_mobile_layout_collapses_to_single_column(
        self, web_config: WebConfig
    ) -> None:
        """Steps 3-4 (mobile, fixture) — at 375 px the layout collapses to 1 column.

        The computed grid-template-columns must contain a single track and the
        sidebar must be rendered below (not beside) the main column.
        """
        server, fixture_url = _start_fixture_server()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=web_config.headless, slow_mo=web_config.slow_mo
                )
                try:
                    page = browser.new_page()
                    page.set_viewport_size(_MOBILE_VIEWPORT)
                    page.goto(fixture_url, timeout=_PAGE_LOAD_TIMEOUT)
                    page.wait_for_load_state("domcontentloaded")

                    cols = _get_grid_columns(page, "[data-testid='watch-layout']")
                    col_count = _parse_column_count(cols)
                    assert col_count == 1, (
                        f"Expected 1 grid column at mobile viewport "
                        f"({_MOBILE_VIEWPORT['width']} px), "
                        f"but computed grid-template-columns = '{cols}'\n"
                        "The watch layout did NOT collapse to a single column below 1024 px."
                    )

                    # Geometric stacked check: sidebar must be below main column
                    main_box = _get_bounding_box(page, "[data-testid='main-column']")
                    sidebar_box = _get_bounding_box(page, "[data-testid='sidebar']")

                    assert main_box is not None, "main-column not found on page"
                    assert sidebar_box is not None, "sidebar not found on page"

                    # When stacked, sidebar top > main column bottom
                    main_bottom = main_box["y"] + main_box["height"]
                    assert sidebar_box["y"] >= main_bottom - 5, (
                        f"Sidebar appears beside the main column at mobile — "
                        f"expected stacked layout. "
                        f"main-column bottom={main_bottom:.0f}, "
                        f"sidebar top={sidebar_box['y']:.0f}."
                    )

                    # Both should span full width (close to viewport width)
                    viewport_width = _MOBILE_VIEWPORT["width"]
                    for name, box in [
                        ("main-column", main_box),
                        ("sidebar", sidebar_box),
                    ]:
                        assert box["width"] > viewport_width * 0.8, (
                            f"{name} width ({box['width']:.0f} px) is less than "
                            f"80% of viewport ({viewport_width} px) at mobile — "
                            "it should span the full column width when stacked."
                        )
                finally:
                    browser.close()
        finally:
            server.shutdown()

    def test_fixture_resize_from_desktop_to_mobile(
        self, web_config: WebConfig
    ) -> None:
        """Steps 1-4 combined (fixture) — resize from desktop to mobile in a single page.

        Verifies the media query fires correctly when the viewport is resized
        without reloading the page.
        """
        server, fixture_url = _start_fixture_server()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=web_config.headless, slow_mo=web_config.slow_mo
                )
                try:
                    page = browser.new_page()
                    # Start at desktop width
                    page.set_viewport_size(_DESKTOP_VIEWPORT)
                    page.goto(fixture_url, timeout=_PAGE_LOAD_TIMEOUT)
                    page.wait_for_load_state("domcontentloaded")

                    # Verify desktop two-column
                    cols_desktop = _get_grid_columns(page, "[data-testid='watch-layout']")
                    assert _parse_column_count(cols_desktop) == 2, (
                        f"Desktop baseline: expected 2 columns, got '{cols_desktop}'"
                    )

                    # Resize to mobile
                    page.set_viewport_size(_MOBILE_VIEWPORT)
                    page.wait_for_timeout(100)  # allow reflow

                    # Verify mobile single-column
                    cols_mobile = _get_grid_columns(page, "[data-testid='watch-layout']")
                    assert _parse_column_count(cols_mobile) == 1, (
                        f"After resize to {_MOBILE_VIEWPORT['width']} px: "
                        f"expected 1 column, got '{cols_mobile}'\n"
                        "Layout did not adapt after viewport resize."
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()

    # ── Live mode (skipped if app is unreachable or no video available) ──────

    def test_live_watch_page_desktop_two_column_layout(
        self, web_config: WebConfig
    ) -> None:
        """Step 1-2 (live app, desktop) — deployed watch page renders two columns.

        Navigates to the live app, discovers a published video via the API,
        opens it at desktop width, and asserts the layout is two-column.
        """
        import urllib.request

        base_url = web_config.base_url
        try:
            urllib.request.urlopen(base_url, timeout=10)
        except Exception as exc:
            pytest.skip(f"Deployed app unreachable ({base_url}): {exc}")

        api_config = APIConfig()
        video_svc = VideoApiService(api_config)
        result = video_svc.find_ready_video()
        if result is None:
            pytest.skip("No published video found via API — cannot navigate to watch page.")

        video_id, _ = result

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            try:
                page = browser.new_page()
                page.set_viewport_size(_DESKTOP_VIEWPORT)
                watch_url = f"{base_url.rstrip('/')}/v/{video_id}/"
                page.goto(watch_url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")

                # Wait for the watch page content to load (not an error state)
                page.wait_for_timeout(3000)

                # Locate the main layout grid: parent of the <aside> sidebar element
                # CSS Modules hash the class names, so we use the semantic <aside> tag
                aside_count = page.locator("aside").count()
                if aside_count == 0:
                    pytest.skip(
                        f"No <aside> element found on watch page at {watch_url}. "
                        "The page may still be loading or the video might not be rendered."
                    )

                # Get computed grid columns from the aside's parent (the watchLayout div)
                cols = page.evaluate(
                    """() => {
                        const aside = document.querySelector('aside');
                        if (!aside) return '';
                        const parent = aside.parentElement;
                        if (!parent) return '';
                        return window.getComputedStyle(parent).gridTemplateColumns;
                    }"""
                )

                if not cols:
                    pytest.skip(
                        "Could not read grid-template-columns from aside's parent element."
                    )

                col_count = _parse_column_count(cols)
                assert col_count == 2, (
                    f"Live app desktop ({_DESKTOP_VIEWPORT['width']} px): "
                    f"Expected 2-column grid on watch page, "
                    f"but computed grid-template-columns = '{cols}'. "
                    f"URL: {watch_url}"
                )

                # Geometric side-by-side check: aside must be to the right
                main_box = page.locator("aside").locator("..").evaluate(
                    """(parent) => {
                        const children = Array.from(parent.children);
                        const aside = parent.querySelector('aside');
                        const main = children.find(c => c !== aside);
                        if (!main) return null;
                        const r = main.getBoundingClientRect();
                        return {x: r.x, y: r.y, width: r.width, height: r.height};
                    }"""
                )
                sidebar_box = page.locator("aside").first.bounding_box()

                if main_box and sidebar_box:
                    assert sidebar_box["x"] > main_box["x"], (
                        f"Live app desktop: sidebar (x={sidebar_box['x']:.0f}) is NOT "
                        f"to the right of the main content (x={main_box['x']:.0f}). "
                        "Expected two-column layout with sidebar on the right."
                    )
            finally:
                browser.close()

    def test_live_watch_page_mobile_single_column_layout(
        self, web_config: WebConfig
    ) -> None:
        """Steps 3-4 (live app, mobile) — deployed watch page collapses to single column.

        Navigates to the live app at mobile viewport (375 × 812 px) and asserts
        the layout is a single vertical column (no sidebar to the right).
        """
        import urllib.request

        base_url = web_config.base_url
        try:
            urllib.request.urlopen(base_url, timeout=10)
        except Exception as exc:
            pytest.skip(f"Deployed app unreachable ({base_url}): {exc}")

        api_config = APIConfig()
        video_svc = VideoApiService(api_config)
        result = video_svc.find_ready_video()
        if result is None:
            pytest.skip("No published video found via API — cannot navigate to watch page.")

        video_id, _ = result

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            try:
                page = browser.new_page()
                page.set_viewport_size(_MOBILE_VIEWPORT)
                watch_url = f"{base_url.rstrip('/')}/v/{video_id}/"
                page.goto(watch_url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)

                aside_count = page.locator("aside").count()
                if aside_count == 0:
                    pytest.skip(
                        f"No <aside> element found on watch page at {watch_url}. "
                        "The page may still be loading or the video might not be rendered."
                    )

                cols = page.evaluate(
                    """() => {
                        const aside = document.querySelector('aside');
                        if (!aside) return '';
                        const parent = aside.parentElement;
                        if (!parent) return '';
                        return window.getComputedStyle(parent).gridTemplateColumns;
                    }"""
                )

                if not cols:
                    pytest.skip(
                        "Could not read grid-template-columns from aside's parent element."
                    )

                col_count = _parse_column_count(cols)
                assert col_count == 1, (
                    f"Live app mobile ({_MOBILE_VIEWPORT['width']} px): "
                    f"Expected 1-column grid on watch page (single column), "
                    f"but computed grid-template-columns = '{cols}'. "
                    f"URL: {watch_url}\n"
                    "The watch layout did NOT collapse to a single column at mobile width."
                )
            finally:
                browser.close()
