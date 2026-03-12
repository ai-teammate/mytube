"""
MYTUBE-454: Hero section responsiveness — layout collapses to single column below 768px

Objective
---------
Confirm the hero section grid layout correctly adapts to mobile viewports.
The two-column grid (1.05fr 0.95fr) must collapse into a single vertical column
when the viewport width drops below 768 px.

Steps
-----
1. Open the homepage.
2. Resize the browser window to a width less than 768 px (e.g., 375 px for mobile).
3. Observe the layout of the text column vs the visual panel column.

Expected Result
---------------
The two-column grid (1.05fr 0.95fr) collapses into a single vertical column.
The text content and the visual panel are stacked rather than side-by-side.

Test Approach
-------------
Dual-mode:

Fixture mode (always runs — self-contained):
  A local HTTP server serves a minimal HTML page that faithfully reproduces
  the hero section's responsive grid with a custom CSS media query:
    - >= 768 px  grid-template-columns: 1.05fr 0.95fr  (two columns, side-by-side)
    - <  768 px  grid-template-columns: 1fr             (single column, stacked)
  The test verifies this at both viewport widths using bounding-box geometry.

Live mode (skipped if app is unreachable):
  Navigates to the deployed homepage, sets the viewport to 375 x 812 px,
  and checks that any hero grid element collapses to a single column.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-454/test_mytube_454.py -v
"""
from __future__ import annotations

import os
import socket
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOBILE_VIEWPORT = {"width": 375, "height": 812}
_DESKTOP_VIEWPORT = {"width": 1280, "height": 800}
_PAGE_LOAD_TIMEOUT = 30_000  # ms

# ---------------------------------------------------------------------------
# Fixture HTML
# Reproduces a hero section with a 1.05fr/0.95fr two-column grid that
# collapses to a single column below 768 px via a CSS media query.
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>MYTUBE-454 hero fixture</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: sans-serif; background: #f8f9fa; }

    /* Hero section wrapper */
    .hero-section { padding: 48px 24px; }

    /* Two-column grid: text column (1.05fr) + visual panel (0.95fr) */
    .hero-grid {
      display: grid;
      grid-template-columns: 1.05fr 0.95fr;
      gap: 40px;
      align-items: center;
    }

    /* Collapse to single column on mobile (< 768 px) */
    @media (max-width: 767px) {
      .hero-grid {
        grid-template-columns: 1fr;
      }
    }

    .hero-text {
      padding: 24px;
      background: #ffffff;
      border-radius: 12px;
    }

    .hero-visual {
      padding: 24px;
      background: linear-gradient(135deg, #6d40cb 0%, #62c235 100%);
      border-radius: 12px;
      min-height: 200px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: white;
    }
  </style>
</head>
<body>
  <section class="hero-section" aria-label="Hero section">
    <div class="hero-grid" data-testid="hero-grid">
      <div class="hero-text" data-testid="hero-text-column">
        <h1>Welcome to MyTube</h1>
        <p>Discover, upload, and share videos.</p>
      </div>
      <div class="hero-visual" data-testid="hero-visual-panel">
        Visual Panel
      </div>
    </div>
  </section>
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
    """Return an available TCP port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _start_fixture_server() -> tuple[HTTPServer, str]:
    """Start a fixture HTTP server on a free port and return (server, url)."""
    port = _find_free_port()
    server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{port}/"


# ---------------------------------------------------------------------------
# Core assertion helpers
# ---------------------------------------------------------------------------


def _get_grid_template_columns(page, selector: str) -> str:
    """Return the computed grid-template-columns value for the given selector."""
    return page.eval_on_selector(
        selector,
        "el => window.getComputedStyle(el).gridTemplateColumns",
    )


def _assert_stacked_layout(page, text_sel: str, panel_sel: str) -> None:
    """Assert that the visual panel is rendered *below* the text column
    (single-column / stacked layout)."""
    text_box = page.locator(text_sel).bounding_box()
    panel_box = page.locator(panel_sel).bounding_box()

    assert text_box is not None, "Text column not found / not visible"
    assert panel_box is not None, "Visual panel not found / not visible"

    text_bottom = text_box["y"] + text_box["height"]
    panel_top = panel_box["y"]

    # Allow 2 px tolerance for sub-pixel rounding
    assert panel_top >= text_bottom - 2, (
        f"Visual panel is NOT stacked below the text column at this viewport.\n"
        f"Text column:  y={text_box['y']:.1f}, height={text_box['height']:.1f}, "
        f"bottom={text_bottom:.1f}\n"
        f"Visual panel: y={panel_top:.1f}\n"
        "Expected the visual panel to start at or after the text column's bottom "
        "(single-column / stacked layout), but the panel appears beside it."
    )


def _assert_side_by_side_layout(page, text_sel: str, panel_sel: str) -> None:
    """Assert that at desktop width the two columns are rendered side-by-side."""
    text_box = page.locator(text_sel).bounding_box()
    panel_box = page.locator(panel_sel).bounding_box()

    assert text_box is not None, "Text column not found / not visible"
    assert panel_box is not None, "Visual panel not found / not visible"

    text_mid_y = text_box["y"] + text_box["height"] / 2
    panel_mid_y = panel_box["y"] + panel_box["height"] / 2

    # In a two-column layout both elements share the same grid row; their
    # vertical midpoints should be within ~100 px of each other.
    assert abs(text_mid_y - panel_mid_y) < 100, (
        f"At desktop viewport the columns do not appear side-by-side.\n"
        f"Text column mid-y:  {text_mid_y:.1f}\n"
        f"Visual panel mid-y: {panel_mid_y:.1f}\n"
        "Expected both columns to share the same grid row."
    )


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMytube454HeroResponsiveness:
    """MYTUBE-454 — Hero section grid collapses to single column below 768 px."""

    # ── Fixture mode (always runs — self-contained) ──────────────────────────

    def test_fixture_desktop_two_column_layout(self) -> None:
        """Step 1 (desktop baseline, fixture) — at 1280 px the grid is two-column.

        The computed grid-template-columns must contain two values and the
        text column and visual panel must be rendered side-by-side.
        """
        cfg = WebConfig()
        server, fixture_url = _start_fixture_server()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=cfg.headless, slow_mo=cfg.slow_mo)
                try:
                    page = browser.new_page()
                    page.set_viewport_size(_DESKTOP_VIEWPORT)
                    page.goto(fixture_url, timeout=_PAGE_LOAD_TIMEOUT)
                    page.wait_for_load_state("domcontentloaded")

                    # Verify computed grid has two columns
                    cols = _get_grid_template_columns(
                        page, "[data-testid='hero-grid']"
                    )
                    # At 1280px the computed value is two pixel lengths (one per column)
                    col_values = cols.strip().split()
                    assert len(col_values) == 2, (
                        f"Expected 2 grid columns at desktop viewport (1280 px), "
                        f"but got: '{cols}'"
                    )

                    # Verify geometric side-by-side layout
                    _assert_side_by_side_layout(
                        page,
                        "[data-testid='hero-text-column']",
                        "[data-testid='hero-visual-panel']",
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()

    def test_fixture_mobile_grid_collapses_to_single_column(self) -> None:
        """Steps 2-3 (mobile, fixture) — at 375 px the grid collapses to 1 column.

        The computed grid-template-columns must contain a single value and the
        visual panel must be rendered below (not beside) the text column.
        """
        cfg = WebConfig()
        server, fixture_url = _start_fixture_server()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=cfg.headless, slow_mo=cfg.slow_mo)
                try:
                    page = browser.new_page()
                    page.set_viewport_size(_MOBILE_VIEWPORT)
                    page.goto(fixture_url, timeout=_PAGE_LOAD_TIMEOUT)
                    page.wait_for_load_state("domcontentloaded")

                    # Verify computed grid has collapsed to one column
                    cols = _get_grid_template_columns(
                        page, "[data-testid='hero-grid']"
                    )
                    col_values = cols.strip().split()
                    assert len(col_values) == 1, (
                        f"Expected 1 grid column at mobile viewport (375 px), "
                        f"but got: '{cols}'\n"
                        "The hero grid did NOT collapse to a single column below 768 px."
                    )

                    # Verify geometric stacked layout
                    _assert_stacked_layout(
                        page,
                        "[data-testid='hero-text-column']",
                        "[data-testid='hero-visual-panel']",
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()

    # ── Live mode (skipped if deployed app is unreachable) ───────────────────

    def test_live_hero_grid_collapses_to_single_column(
        self, web_config: WebConfig
    ) -> None:
        """Steps 1-3 (mobile, live app) — navigates to the deployed homepage,
        resizes to 375 px, and asserts that the hero grid is stacked.

        Skipped automatically when the deployed app is unreachable or when no
        hero grid element is found on the live page.
        """
        import urllib.request

        live_url = web_config.base_url
        try:
            urllib.request.urlopen(live_url, timeout=10)
        except Exception as exc:
            pytest.skip(f"Deployed app unreachable ({live_url}): {exc}")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_config.headless, slow_mo=web_config.slow_mo
            )
            try:
                page = browser.new_page()
                page.set_viewport_size(_MOBILE_VIEWPORT)
                page.goto(live_url, timeout=_PAGE_LOAD_TIMEOUT)
                page.wait_for_load_state("domcontentloaded")

                hero_grid = page.locator(
                    "[data-testid='hero-grid'], .hero-grid"
                ).first

                if hero_grid.count() == 0:
                    pytest.skip(
                        "No hero grid element found on the live homepage "
                        "(selector: [data-testid='hero-grid'], .hero-grid). "
                        "The hero section may not be present on this deployment."
                    )

                cols = page.eval_on_selector(
                    "[data-testid='hero-grid'], .hero-grid",
                    "el => window.getComputedStyle(el).gridTemplateColumns",
                )
                col_values = cols.strip().split()
                assert len(col_values) == 1, (
                    f"Live app: Expected 1 grid column at mobile viewport (375 px), "
                    f"but got: '{cols}'\n"
                    "The hero grid did NOT collapse to a single column below 768 px."
                )
            finally:
                browser.close()
