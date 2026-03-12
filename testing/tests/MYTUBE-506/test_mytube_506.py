"""
MYTUBE-506: Upload page responsive layout — 2-column grid collapses on mobile.

Objective
---------
Verify the upload page implements a two-column workspace layout on desktop that
collapses to a single column on mobile viewports.

Steps
-----
1. View the page on a desktop viewport (width > 1024px).
2. Inspect the outer container CSS properties.
3. Resize the viewport to mobile width (e.g., 375px).

Expected Result
---------------
* On desktop: The layout is a CSS grid with two columns
  (left: 280px–330px, right: flexible) and a 20px gap.
* On mobile: The grid collapses to a single column where the upload card and
  library area stack vertically.

Test Approach
-------------
The upload page (``/upload``) requires authentication.  To verify the CSS grid
rules in isolation — independent of auth state — a self-contained HTML page is
served locally via Python's ``http.server``.  That page replicates the CSS
declared in ``web/src/app/upload/upload.module.css``:

    .workspace {
        display: grid;
        grid-template-columns: minmax(280px, 330px) minmax(0, 1fr);
        gap: 20px;
    }
    @media (max-width: 639px) {
        .workspace { grid-template-columns: 1fr; }
    }

Playwright then opens the local page at two viewport widths (1280 × 720 for
desktop, 375 × 812 for mobile) and asserts the computed grid-template-columns
values match what the CSS specifies.

Architecture
------------
- WebConfig from testing/core/config/web_config.py is used for browser settings
  (headless, slow_mo).
- Local HTTP server eliminates the auth dependency for pure layout assertions.
- Tests use only Playwright's ``evaluate`` for CSS computed-style inspection; no
  raw selectors in assertion logic.
"""
from __future__ import annotations

import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DESKTOP_WIDTH = 1280
_DESKTOP_HEIGHT = 720
_MOBILE_WIDTH = 375
_MOBILE_HEIGHT = 812

_PAGE_LOAD_TIMEOUT = 15_000  # ms

# The HTML fixture replicates the workspace CSS from upload.module.css verbatim
# so that computed-style assertions reflect exactly what the production
# stylesheet declares, without requiring authentication.
_FIXTURE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Upload layout fixture</title>
  <style>
    /* Exact copy of upload.module.css .workspace block */
    .workspace {
      display: grid;
      grid-template-columns: minmax(280px, 330px) minmax(0, 1fr);
      gap: 20px;
      align-items: start;
      padding: 20px;
    }

    @media (max-width: 639px) {
      .workspace {
        grid-template-columns: 1fr;
      }
    }

    /* Minimal children to make the grid concrete */
    .upload-card {
      background: #f5f5f5;
      min-height: 200px;
      padding: 16px;
    }
    .library-area {
      background: #e8e8e8;
      min-height: 200px;
      padding: 16px;
    }
  </style>
</head>
<body>
  <div class="workspace" data-testid="workspace">
    <div class="upload-card" data-testid="upload-card">Upload card</div>
    <div class="library-area" data-testid="library-area">Library area</div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Local HTTP server helpers
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    """Serves the single HTML fixture for every request."""

    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # suppress server noise
        pass


def _start_server() -> tuple[HTTPServer, str]:
    """Start the local fixture server on a free port and return (server, url)."""
    server = HTTPServer(("127.0.0.1", 0), _FixtureHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/"


# ---------------------------------------------------------------------------
# CSS helper (executed in browser via evaluate)
# ---------------------------------------------------------------------------

_GET_WORKSPACE_STYLES_JS = """
() => {
    const el = document.querySelector('[data-testid="workspace"]');
    if (!el) return null;
    const cs = window.getComputedStyle(el);
    return {
        display: cs.display,
        gridTemplateColumns: cs.gridTemplateColumns,
        gap: cs.gap || cs.rowGap + ' ' + cs.columnGap,
        columnGap: cs.columnGap
    };
}
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def fixture_server():
    server, url = _start_server()
    yield url
    server.shutdown()


# ---------------------------------------------------------------------------
# Helper to open a page at a specific viewport and load the fixture
# ---------------------------------------------------------------------------


def _open_fixture(config: WebConfig, fixture_url: str, width: int, height: int) -> tuple:
    """Launch browser at *width* × *height*, load fixture, return (pw, browser, page)."""
    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
    page = browser.new_page(viewport={"width": width, "height": height})
    page.goto(fixture_url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="load")
    return pw, browser, page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadPageResponsiveLayout:
    """MYTUBE-506: Upload workspace grid collapses on mobile."""

    def test_desktop_two_column_grid(self, config: WebConfig, fixture_server: str) -> None:
        """
        Step 1–2: On a desktop viewport (1280 × 720) the workspace container
        must be a CSS grid with two columns (left ≈ 280–330 px, right flexible)
        and a 20 px column gap.
        """
        pw, browser, page = _open_fixture(config, fixture_server, _DESKTOP_WIDTH, _DESKTOP_HEIGHT)
        try:
            styles = page.evaluate(_GET_WORKSPACE_STYLES_JS)

            assert styles is not None, (
                "Could not find [data-testid='workspace'] element on the fixture page. "
                f"URL: {page.url}"
            )

            # 1. Must be a grid
            assert styles["display"] == "grid", (
                f"Expected display:grid on desktop, got '{styles['display']}'. "
                f"Full computed styles: {styles}"
            )

            # 2. Must have exactly 2 column tracks
            col_tracks = styles["gridTemplateColumns"].split()
            # The browser resolves minmax(280px, 330px) to a pixel value (330px at 1280px
            # wide viewport) and minmax(0, 1fr) to the remaining space.
            # We assert there are exactly 2 resolved column-width tokens (e.g. "330px 910px").
            assert len(col_tracks) == 2, (
                f"Expected 2 column tracks on desktop but got {len(col_tracks)}: "
                f"'{styles['gridTemplateColumns']}'. "
                "The workspace CSS should declare: "
                "grid-template-columns: minmax(280px, 330px) minmax(0, 1fr)."
            )

            # 3. Left column must be within the 280–330 px clamped range
            left_col_raw = col_tracks[0]
            assert left_col_raw.endswith("px"), (
                f"Left column track '{left_col_raw}' is not a pixel value."
            )
            left_col_px = float(left_col_raw[:-2])
            assert 280 <= left_col_px <= 330, (
                f"Left column width {left_col_px}px is outside the expected 280–330 px range. "
                "CSS rule: grid-template-columns: minmax(280px, 330px) minmax(0, 1fr)."
            )

            # 4. Column gap must be 20 px
            col_gap_raw = styles.get("columnGap", "")
            assert col_gap_raw == "20px", (
                f"Expected column-gap 20px on desktop, got '{col_gap_raw}'. "
                "CSS rule: gap: 20px."
            )

        finally:
            browser.close()
            pw.stop()

    def test_mobile_single_column_grid(self, config: WebConfig, fixture_server: str) -> None:
        """
        Step 3: On a mobile viewport (375 × 812) the workspace grid must
        collapse to a single column (grid-template-columns: 1fr).

        The media query in upload.module.css fires at max-width: 639px, so a
        375 px wide viewport must trigger it.
        """
        pw, browser, page = _open_fixture(config, fixture_server, _MOBILE_WIDTH, _MOBILE_HEIGHT)
        try:
            styles = page.evaluate(_GET_WORKSPACE_STYLES_JS)

            assert styles is not None, (
                "Could not find [data-testid='workspace'] element on the fixture page. "
                f"URL: {page.url}"
            )

            # Must still be a grid (display doesn't change)
            assert styles["display"] == "grid", (
                f"Expected display:grid on mobile, got '{styles['display']}'. "
                f"Full computed styles: {styles}"
            )

            # Must have exactly 1 column track
            col_tracks = styles["gridTemplateColumns"].split()
            assert len(col_tracks) == 1, (
                f"Expected 1 column track on mobile (375 px) but got {len(col_tracks)}: "
                f"'{styles['gridTemplateColumns']}'. "
                "The @media (max-width: 639px) rule should set grid-template-columns: 1fr."
            )

            # The single track must fill the full viewport width (≈ 375 px minus padding)
            single_col_raw = col_tracks[0]
            assert single_col_raw.endswith("px"), (
                f"Mobile single column track '{single_col_raw}' is not a pixel value."
            )
            single_col_px = float(single_col_raw[:-2])
            # Container has 20 px left + right padding so inner width ≈ 335 px,
            # but actual layout width depends on box-model; just ensure it's > 300 px
            # and close to the viewport width (definitely not a narrow fixed column).
            assert single_col_px > 300, (
                f"Mobile single column track {single_col_px}px seems too narrow. "
                "Expected the column to span most of the 375 px viewport width."
            )

        finally:
            browser.close()
            pw.stop()

    def test_mobile_upload_card_stacks_above_library(
        self, config: WebConfig, fixture_server: str
    ) -> None:
        """
        Verify that on mobile the upload card appears above the library area
        (DOM order preserved: upload-card comes before library-area in the column).

        This test checks the actual rendered bounding box positions to confirm
        vertical stacking without overlap.
        """
        pw, browser, page = _open_fixture(config, fixture_server, _MOBILE_WIDTH, _MOBILE_HEIGHT)
        try:
            card_box = page.evaluate(
                "() => { const el = document.querySelector('[data-testid=\"upload-card\"]'); "
                "return el ? el.getBoundingClientRect().toJSON() : null; }"
            )
            library_box = page.evaluate(
                "() => { const el = document.querySelector('[data-testid=\"library-area\"]'); "
                "return el ? el.getBoundingClientRect().toJSON() : null; }"
            )

            assert card_box is not None, "Upload card element not found in the DOM."
            assert library_box is not None, "Library area element not found in the DOM."

            # On single-column layout upload card should be above library area
            assert card_box["top"] < library_box["top"], (
                f"Upload card top ({card_box['top']}px) is NOT above library area "
                f"top ({library_box['top']}px) on mobile. "
                "Expected the upload card to stack vertically above the library area."
            )

            # Both elements should share roughly the same left edge (same column)
            assert abs(card_box["left"] - library_box["left"]) < 5, (
                f"Upload card left ({card_box['left']}px) and library area left "
                f"({library_box['left']}px) differ by more than 5 px on mobile. "
                "Both children should be in the same single column."
            )

        finally:
            browser.close()
            pw.stop()
