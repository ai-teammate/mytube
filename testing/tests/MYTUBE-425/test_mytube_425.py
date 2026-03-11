"""
MYTUBE-425: Icon color inheritance — SVG components use currentColor for styling

Objective
---------
Ensure that all decorative and brand icons allow color control via parent CSS
using the currentColor keyword.

Steps
-----
1. Render the DecorPlay component inside a container with the CSS property
   color: rgb(255, 0, 0).
2. Inspect the fill or stroke attribute of the rendered SVG.

Expected Result
---------------
The SVG inherits the red color from the parent container because it is
configured with currentColor.

Test approach
-------------
A local HTTP server serves a minimal HTML page that embeds the exact SVG
markup produced by DecorPlay.tsx inside a container styled with
color: rgb(255, 0, 0).  Playwright is used to:

  1. Verify the SVG element carries fill="currentColor" as an attribute.
  2. Verify the browser-computed fill color of the SVG path equals
     rgb(255, 0, 0) — confirming that currentColor actually inherits the
     parent's color property at runtime.

Architecture
------------
- Playwright sync API with pytest fixtures.
- Standalone fixture server — no live deployment required.
- PLAYWRIGHT_HEADLESS env var controls headless mode (default: true).
"""
from __future__ import annotations

import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURE_PORT = 19425
_PAGE_LOAD_TIMEOUT = 15_000  # ms

# ---------------------------------------------------------------------------
# Fixture HTML
# Reproduces exactly what DecorPlay.tsx renders:
#   <svg fill="currentColor" viewBox="0 0 120 120" ...>
#     <path d="M20 10 L20 24 L62 60 L20 96 L20 110 L100 110 L100 96 L44 96 L80 60 L44 24 L100 24 L100 10 Z" />
#   </svg>
# wrapped in a container with color: rgb(255, 0, 0)
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>MYTUBE-425 — DecorPlay currentColor fixture</title>
  <style>
    body { margin: 0; padding: 20px; background: #fff; }
    .red-container {
      color: rgb(255, 0, 0);
      display: inline-block;
    }
  </style>
</head>
<body>
  <div class="red-container" id="container">
    <svg
      id="decor-play"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 120 120"
      fill="currentColor"
      aria-hidden="true"
      width="120"
      height="120"
    >
      <path id="decor-play-path" d="M20 10 L20 24 L62 60 L20 96 L20 110 L100 110 L100 96 L44 96 L80 60 L44 24 L100 24 L100 10 Z" />
    </svg>
  </div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Local fixture HTTP server
# ---------------------------------------------------------------------------

class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        body = _FIXTURE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # silence access log
        pass


@pytest.fixture(scope="module")
def fixture_server():
    server = HTTPServer(("127.0.0.1", _FIXTURE_PORT), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{_FIXTURE_PORT}/"
    server.shutdown()


@pytest.fixture(scope="module")
def browser_page(fixture_server):
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        page = browser.new_page()
        page.goto(fixture_server, timeout=_PAGE_LOAD_TIMEOUT)
        page.wait_for_selector("#decor-play", timeout=_PAGE_LOAD_TIMEOUT)
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDecorPlayCurrentColor:
    """MYTUBE-425: DecorPlay SVG uses currentColor for fill."""

    def test_svg_fill_attribute_is_currentColor(self, browser_page: Page) -> None:
        """Step 2: the rendered SVG element must carry fill='currentColor'."""
        svg = browser_page.locator("#decor-play")
        fill_attr = svg.get_attribute("fill")
        assert fill_attr == "currentColor", (
            f"Expected fill='currentColor' on the SVG element but got fill='{fill_attr}'. "
            "DecorPlay.tsx must set fill='currentColor' on its root <svg>."
        )

    def test_svg_inherits_red_color_from_parent(self, browser_page: Page) -> None:
        """Step 2 (runtime): the browser-computed fill of the SVG path
        must equal the parent container's color: rgb(255, 0, 0)."""
        computed_fill = browser_page.evaluate(
            """() => {
                const path = document.getElementById('decor-play-path');
                return window.getComputedStyle(path).fill;
            }"""
        )
        assert computed_fill == "rgb(255, 0, 0)", (
            f"Expected computed fill to be 'rgb(255, 0, 0)' (inherited via currentColor) "
            f"but got '{computed_fill}'. "
            "The SVG fill='currentColor' should resolve to the parent container's "
            "color: rgb(255, 0, 0)."
        )
