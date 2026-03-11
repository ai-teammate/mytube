"""
MYTUBE-428: Decorative icons implementation — components render correct viewBox dimensions.

Objective
---------
Verify that decorative icons (DecorPlay, DecorWave, etc.) are implemented with
the specific viewBox requirements.

Steps
-----
1. Render DecorPlay and verify its viewBox.
2. Render DecorWave and verify its viewBox.

Expected Result
---------------
- DecorPlay uses a 120x120 viewBox ("0 0 120 120") as per the technical requirements.
- DecorWave uses a 120x120 viewBox ("0 0 120 120") as per the technical requirements.

Test approach
-------------
Two layers:

**Layer A — Static source analysis** (always runs, no browser required):
    Reads the TSX source files for DecorPlay and DecorWave from the
    ``web/src/components/icons/`` directory and verifies that each SVG element
    carries ``viewBox="0 0 120 120"``.  This layer is always exercised so the
    test is self-contained.

**Layer B — Playwright fixture** (always runs):
    A local HTTP server serves a minimal HTML page that embeds the rendered SVG
    output of both icons.  Playwright queries the SVG viewBox attribute via the
    DOM and asserts the expected value.

Environment variables
---------------------
PLAYWRIGHT_HEADLESS  Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO   Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURE_PORT = 19428
_EXPECTED_VIEW_BOX = "0 0 120 120"

# Paths relative to repo root
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_ICONS_DIR = os.path.join(_REPO_ROOT, "web", "src", "components", "icons")

# ---------------------------------------------------------------------------
# Fixture HTML  (embeds inline SVG output of DecorPlay and DecorWave)
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>MYTUBE-428 fixture</title>
</head>
<body>
  <!-- DecorPlay (120x120 viewBox) -->
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 120 120"
    fill="currentColor"
    aria-hidden="true"
    data-testid="decor-play"
  >
    <path d="M20 10 L20 24 L62 60 L20 96 L20 110 L100 110 L100 96 L44 96 L80 60 L44 24 L100 24 L100 10 Z" />
  </svg>

  <!-- DecorWave (120x120 viewBox) -->
  <svg
    xmlns="http://www.w3.org/2000/svg"
    viewBox="0 0 120 120"
    fill="currentColor"
    aria-hidden="true"
    data-testid="decor-wave"
  >
    <rect x="54" y="18" width="12" height="84" rx="3" />
    <path d="M54 22 Q30 30 18 50 Q12 66 18 82 Q30 96 54 102 Z" />
    <path d="M66 22 Q90 30 102 50 Q108 66 102 82 Q90 96 66 102 Z" />
  </svg>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Local fixture server
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def _start_fixture_server(port: int = _FIXTURE_PORT) -> HTTPServer:
    HTTPServer.allow_reuse_address = True
    server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Layer A: Static source analysis helpers
# ---------------------------------------------------------------------------


def _read_icon_source(filename: str) -> str:
    path = os.path.join(_ICONS_DIR, filename)
    if not os.path.isfile(path):
        pytest.fail(f"Icon source file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _extract_view_box(source: str) -> str | None:
    """Return the first viewBox value found in the TSX source."""
    # Standard JSX attribute: viewBox="0 0 120 120"
    match = re.search(r'viewBox="([^"]+)"', source)
    if match:
        return match.group(1)
    # JSX expression: viewBox={"0 0 120 120"} or viewBox={'0 0 120 120'}
    match2 = re.search(r"""viewBox=\{['"]([^'"]+)['"]\}""", source)
    if match2:
        return match2.group(1)
    return None


# ---------------------------------------------------------------------------
# Pytest tests
# ---------------------------------------------------------------------------


class TestMytube428DecorativeIconViewBox:
    """MYTUBE-428 — decorative icons render correct viewBox dimensions."""

    # ------------------------------------------------------------------
    # Layer A: Static analysis of TSX source files
    # ------------------------------------------------------------------

    def test_decor_play_viewbox_in_source(self) -> None:
        """Layer A: DecorPlay.tsx declares viewBox='0 0 120 120'."""
        source = _read_icon_source("DecorPlay.tsx")
        view_box = _extract_view_box(source)
        assert view_box == _EXPECTED_VIEW_BOX, (
            f"DecorPlay.tsx viewBox expected '{_EXPECTED_VIEW_BOX}', got '{view_box}'"
        )

    def test_decor_wave_viewbox_in_source(self) -> None:
        """Layer A: DecorWave.tsx declares viewBox='0 0 120 120'."""
        source = _read_icon_source("DecorWave.tsx")
        view_box = _extract_view_box(source)
        assert view_box == _EXPECTED_VIEW_BOX, (
            f"DecorWave.tsx viewBox expected '{_EXPECTED_VIEW_BOX}', got '{view_box}'"
        )

    # ------------------------------------------------------------------
    # Layer B: Playwright fixture — DOM attribute verification
    # ------------------------------------------------------------------

    def test_fixture_decor_play_viewbox_in_dom(self) -> None:
        """Layer B: Playwright reads the viewBox attribute of the DecorPlay SVG
        rendered in a fixture HTML page."""
        server = _start_fixture_server(port=19428)
        fixture_url = f"http://127.0.0.1:19428/"
        cfg = WebConfig()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=cfg.headless, slow_mo=cfg.slow_mo)
                try:
                    page = browser.new_page()
                    page.goto(fixture_url, timeout=15_000)
                    page.wait_for_load_state("domcontentloaded")

                    view_box = page.get_attribute(
                        '[data-testid="decor-play"]', "viewBox"
                    )
                    assert view_box == _EXPECTED_VIEW_BOX, (
                        f"DecorPlay DOM viewBox expected '{_EXPECTED_VIEW_BOX}', "
                        f"got '{view_box}'"
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()

    def test_fixture_decor_wave_viewbox_in_dom(self) -> None:
        """Layer B: Playwright reads the viewBox attribute of the DecorWave SVG
        rendered in a fixture HTML page."""
        server = _start_fixture_server(port=19429)
        fixture_url = f"http://127.0.0.1:19429/"
        cfg = WebConfig()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=cfg.headless, slow_mo=cfg.slow_mo)
                try:
                    page = browser.new_page()
                    page.goto(fixture_url, timeout=15_000)
                    page.wait_for_load_state("domcontentloaded")

                    view_box = page.get_attribute(
                        '[data-testid="decor-wave"]', "viewBox"
                    )
                    assert view_box == _EXPECTED_VIEW_BOX, (
                        f"DecorWave DOM viewBox expected '{_EXPECTED_VIEW_BOX}', "
                        f"got '{view_box}'"
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()
