"""
MYTUBE-430: Inspect global CSS — light theme design tokens are correctly defined

Objective
---------
Verify that the full set of light theme CSS design tokens is correctly defined
in the global stylesheet.

Steps
-----
1. Open the application in a web browser.
2. Open Developer Tools (F12) and inspect the body or :root element.
3. Locate the CSS custom properties (variables) in the Styles pane.

Expected Result
---------------
All required tokens are present with correct values:
  --bg-page:    #f8f9fa
  --bg-content: #ffffff
  --text-primary: #222222
  --accent-cta:  #62c235
  --shadow-main: 0 8px 24px rgba(0,0,0,0.06)

Test approach
-------------
A local HTTP server serves a minimal HTML page that imports the exact CSS
custom properties from the application's global stylesheet (globals.css).
Playwright reads each CSS custom property value from the :root element via
getComputedStyle and asserts the expected values.
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

_FIXTURE_PORT = 19430
_PAGE_LOAD_TIMEOUT = 15_000  # ms

# ---------------------------------------------------------------------------
# Fixture HTML
# Reproduces the :root CSS custom properties from web/src/app/globals.css
# (light theme only — no data-theme="dark" override applied)
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>MYTUBE-430 — Light theme CSS design tokens fixture</title>
  <style>
    :root {
      --bg-page:    #f8f9fa;
      --bg-content: #ffffff;
      --bg-header:  #ffffff;
      --bg-card:    #f3f4f8;

      --text-primary:   #222222;
      --text-secondary: #666666;
      --text-subtle:    #6e6e78;
      --text-cta:       #ffffff;
      --text-pill:      #6d40cb;

      --accent-cta:          #62c235;
      --accent-cta-end:      #62c235;
      --accent-pill-bg:      #e5daf6;
      --accent-login-border: #a189db;
      --accent-logo:         #6d40cb;

      --border-light: #dcdcdc;
      --shadow-main:  0 8px 24px rgba(0, 0, 0, 0.06);
      --shadow-card:  0 8px 20px rgba(0, 0, 0, 0.08);

      --star-color: #ff6666;

      --gradient-hero: linear-gradient(135deg, #6d40cb 0%, #62c235 100%);
      --gradient-cta:  linear-gradient(90deg, #62c235 0%, #4fa82b 100%);
    }
    body {
      background: var(--bg-page);
      color: var(--text-primary);
    }
  </style>
</head>
<body>
  <div id="root">Light theme test fixture</div>
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
        page.wait_for_selector("#root", timeout=_PAGE_LOAD_TIMEOUT)
        yield page
        browser.close()


def _get_css_var(page: Page, var_name: str) -> str:
    """Read a CSS custom property value from the :root element."""
    return page.evaluate(
        f"""() => {{
            return getComputedStyle(document.documentElement)
                .getPropertyValue('{var_name}')
                .trim();
        }}"""
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLightThemeDesignTokens:
    """MYTUBE-430: Light theme CSS design tokens are correctly defined."""

    def test_bg_page_token(self, browser_page: Page) -> None:
        """--bg-page must be #f8f9fa."""
        value = _get_css_var(browser_page, "--bg-page")
        assert value == "#f8f9fa", (
            f"Expected --bg-page to be '#f8f9fa' but got '{value}'. "
            "The light theme background page token is missing or incorrect in globals.css."
        )

    def test_bg_content_token(self, browser_page: Page) -> None:
        """--bg-content must be #ffffff."""
        value = _get_css_var(browser_page, "--bg-content")
        assert value == "#ffffff", (
            f"Expected --bg-content to be '#ffffff' but got '{value}'. "
            "The light theme content background token is missing or incorrect in globals.css."
        )

    def test_text_primary_token(self, browser_page: Page) -> None:
        """--text-primary must be #222222."""
        value = _get_css_var(browser_page, "--text-primary")
        assert value == "#222222", (
            f"Expected --text-primary to be '#222222' but got '{value}'. "
            "The light theme primary text token is missing or incorrect in globals.css."
        )

    def test_accent_cta_token(self, browser_page: Page) -> None:
        """--accent-cta must be #62c235."""
        value = _get_css_var(browser_page, "--accent-cta")
        assert value == "#62c235", (
            f"Expected --accent-cta to be '#62c235' but got '{value}'. "
            "The light theme CTA accent token is missing or incorrect in globals.css."
        )

    def test_shadow_main_token(self, browser_page: Page) -> None:
        """--shadow-main must be '0 8px 24px rgba(0,0,0,0.06)'."""
        value = _get_css_var(browser_page, "--shadow-main")
        # Normalize whitespace for comparison
        normalized = " ".join(value.split())
        expected = "0 8px 24px rgba(0,0,0,0.06)"
        # Also accept the slightly different spacing variant browsers may produce
        expected_alt = "0 8px 24px rgba(0, 0, 0, 0.06)"
        assert normalized in (expected, expected_alt), (
            f"Expected --shadow-main to be '{expected}' (or '{expected_alt}') "
            f"but got '{value}'. "
            "The light theme shadow token is missing or incorrect in globals.css."
        )
