"""
MYTUBE-522: Dashboard video grid layout — responsive grid configuration verified

Objective
---------
Verify the CSS grid configuration for the redesigned video dashboard.
Specifically, the video grid container below the toolbar must use:
  - grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))
  - gap: 16px

Steps
-----
1. Navigate to the Dashboard.
2. Inspect the video grid container below the toolbar.

Expected Result
---------------
The grid uses ``grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))``
and has a ``gap: 16px``.

Test Approach
-------------
Primary mode (live): Navigates to the deployed dashboard URL and scans the
loaded document stylesheets for the CSS rule that defines the video grid layout.
This works even without authentication because Next.js loads the page's CSS
chunks before the RequireAuth redirect takes effect.

Fixture mode (fallback): Spins up a local HTTP server that serves a minimal
HTML page replicating the dashboard video grid container with the exact CSS
from ``_content.module.css``. Playwright checks computed styles directly on
the rendered element.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- DashboardPage from testing/components/pages/dashboard_page/dashboard_page.py
  encapsulates all locators and CSS-inspection logic (get_video_grid_styles,
  get_live_grid_rule, is_video_grid_present, is_toolbar_present).
- Local fixture server used as fallback to guarantee deterministic results.
- Fixture HTML loads the actual CSS from web/src/app/dashboard/_content.module.css
  at import time, so changes to the real CSS file propagate to fixture tests.

Environment Variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
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
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_FIXTURE_PORT = 19522

# The exact CSS values mandated by the design spec.
_EXPECTED_GRID_TEMPLATE_COLUMNS = "repeat(auto-fill, minmax(220px, 1fr))"
_EXPECTED_GAP = "16px"

# ---------------------------------------------------------------------------
# Fixture HTML — injects the *actual* CSS from _content.module.css so that
# fixture tests reflect real application styles rather than a hardcoded copy.
# ---------------------------------------------------------------------------

def _build_fixture_html() -> str:
    """Load the real dashboard CSS from disk and embed it in the fixture HTML.

    Loading from disk (rather than copying CSS as a string literal) means that
    if a developer changes or removes the grid rule in _content.module.css, the
    fixture tests will detect the regression immediately.
    """
    css_path = os.path.normpath(
        os.path.join(
            os.path.dirname(__file__),
            "..", "..", "..",
            "web", "src", "app", "dashboard", "_content.module.css",
        )
    )
    with open(css_path, encoding="utf-8") as f:
        css = f.read()

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <title>MYTUBE-522 Fixture — Dashboard Video Grid</title>
  <style>
{css}
  </style>
</head>
<body>
  <!-- Toolbar above the grid (mirrors the dashboard layout) -->
  <div class="toolbar" data-testid="dashboard-toolbar">
    <div class="toolbarGrid">
      <input type="text" placeholder="Search videos"/>
      <select><option>All</option></select>
      <button>Reset</button>
    </div>
  </div>

  <!-- Video grid container below the toolbar -->
  <div class="videoGrid" data-testid="video-grid">
    <div style="background:#2a2a3e;height:160px;border-radius:8px;">Card 1</div>
    <div style="background:#2a2a3e;height:160px;border-radius:8px;">Card 2</div>
    <div style="background:#2a2a3e;height:160px;border-radius:8px;">Card 3</div>
  </div>
</body>
</html>
"""


_FIXTURE_HTML = _build_fixture_html()


# ---------------------------------------------------------------------------
# Local fixture server
# ---------------------------------------------------------------------------

class _FixtureHandler(BaseHTTPRequestHandler):
    """Serves the fixture HTML and suppresses access log noise."""

    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:  # silence request logs
        pass


def _start_fixture_server() -> tuple[HTTPServer, int]:
    server = HTTPServer(("127.0.0.1", _FIXTURE_PORT), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, _FIXTURE_PORT


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def fixture_server():
    server, port = _start_fixture_server()
    yield f"http://127.0.0.1:{port}/"
    server.shutdown()


@pytest.fixture(scope="module")
def pages(fixture_server: str, config: WebConfig):
    """
    Single playwright context yielding both ``fixture_page`` and ``live_page``.

    Using one sync_playwright() context avoids the asyncio loop conflict that
    occurs when two module-scoped fixtures each open their own context.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)

        # Fixture page: local HTML with exact dashboard grid CSS
        fp = browser.new_page(viewport={"width": 1280, "height": 800})
        fp.goto(fixture_server, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

        # Live page: deployed dashboard URL (CSS loads before auth redirect)
        lp = browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            lp.goto(
                config.dashboard_url(),
                wait_until="networkidle",
                timeout=_PAGE_LOAD_TIMEOUT,
            )
        except Exception:
            pass

        yield {"fixture": fp, "live": lp}
        browser.close()


@pytest.fixture(scope="module")
def fixture_page(pages) -> Page:
    return pages["fixture"]


@pytest.fixture(scope="module")
def live_page(pages) -> Page:
    return pages["live"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDashboardVideoGridLayout:
    """MYTUBE-522: Dashboard video grid — CSS grid configuration verified."""

    # ------------------------------------------------------------------
    # Fixture-based tests (deterministic, no auth required)
    # ------------------------------------------------------------------

    def test_fixture_video_grid_is_present(self, fixture_page: Page) -> None:
        """
        Step 2 (fixture): The video grid container must be present in the DOM
        below the toolbar element.
        """
        dashboard = DashboardPage(fixture_page)
        assert dashboard.is_video_grid_present(), (
            "Video grid container ([data-testid='video-grid']) not found in the "
            "fixture page. Expected the grid to be rendered below the toolbar."
        )
        dashboard.wait_for_video_grid_visible()

        assert dashboard.is_toolbar_present(), (
            "Dashboard toolbar ([data-testid='dashboard-toolbar']) not found. "
            "Expected the toolbar to be present above the video grid."
        )

    def test_fixture_grid_template_columns(self, fixture_page: Page) -> None:
        """
        Step 2 (fixture): The video grid container must use
        ``grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))``.
        """
        dashboard = DashboardPage(fixture_page)
        styles = dashboard.get_video_grid_styles()
        assert styles is not None, (
            "Could not retrieve computed styles for the video grid element. "
            "Selector '[data-testid=\"video-grid\"]' did not match any element."
        )

        actual_gtc = styles.get("gridTemplateColumns", "")
        assert "220px" in actual_gtc and "auto-fill" in actual_gtc, (
            f"grid-template-columns mismatch on the video grid container.\n"
            f"  Expected (contains): {_EXPECTED_GRID_TEMPLATE_COLUMNS!r}\n"
            f"  Actual computed:     {actual_gtc!r}\n"
            "The CSS rule `.videoGrid {{ grid-template-columns: repeat(auto-fill, "
            "minmax(220px, 1fr)); }}` was not applied."
        )

    def test_fixture_grid_gap(self, fixture_page: Page) -> None:
        """
        Step 2 (fixture): The video grid container must have ``gap: 16px``.
        """
        dashboard = DashboardPage(fixture_page)
        styles = dashboard.get_video_grid_styles()
        assert styles is not None, (
            "Could not retrieve computed styles for the video grid element."
        )

        actual_gap = styles.get("gap", "")
        assert "16px" in actual_gap, (
            f"gap mismatch on the video grid container.\n"
            f"  Expected (contains): {_EXPECTED_GAP!r}\n"
            f"  Actual computed:     {actual_gap!r}\n"
            "The CSS rule `.videoGrid {{ gap: 16px; }}` was not applied."
        )

    # ------------------------------------------------------------------
    # Live-mode stylesheet scan (deployed app)
    # ------------------------------------------------------------------

    def test_live_stylesheet_contains_grid_rule(self, live_page: Page) -> None:
        """
        Step 2 (live): The deployed dashboard page's loaded stylesheets must
        contain a CSS rule with
        ``grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))``
        and ``gap: 16px``.

        This scan works regardless of authentication state because Next.js loads
        the page's CSS bundle before RequireAuth redirects the user.
        """
        dashboard = DashboardPage(live_page)
        result = dashboard.get_live_grid_rule()
        assert result is not None, (
            "No CSS rule containing "
            "'grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))' "
            "was found in any loaded stylesheet on the dashboard page.\n"
            f"Dashboard URL: {live_page.url}\n"
            "The `.videoGrid` CSS rule from `_content.module.css` was not "
            "included in the page's CSS bundle. Verify that the rule "
            "`.videoGrid {{ grid-template-columns: repeat(auto-fill, "
            "minmax(220px, 1fr)); gap: 16px; }}` exists in the deployed CSS."
        )

        gtc = result.get("gridTemplateColumns", "")
        assert "auto-fill" in gtc and "220px" in gtc, (
            f"Stylesheet rule found, but grid-template-columns is incorrect.\n"
            f"  Expected (contains): 'auto-fill' and '220px'\n"
            f"  Actual:              {gtc!r}"
        )

        gap = result.get("gap", "")
        assert "16px" in gap, (
            f"Stylesheet rule found, but gap is not 16px.\n"
            f"  Expected (contains): '16px'\n"
            f"  Actual:              {gap!r}"
        )
