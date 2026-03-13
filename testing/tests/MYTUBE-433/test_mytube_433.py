"""
MYTUBE-433: Check body element styling — background and text consume design tokens

Objective
---------
Verify that the main body element uses the established design tokens instead of
hardcoded color values.

Steps
-----
1. Open the application and inspect the ``body`` element.
2. Review the CSS rules for ``background-color`` and ``color``.

Expected Result
---------------
The ``body`` element has ``background-color: var(--bg-page)`` and
``color: var(--text-primary)`` applied.

Test Approach
-------------
A local HTTP server serves a minimal HTML page that embeds the CSS from
globals.css (stripped of the Tailwind import which is not needed here).
Playwright inspects the CSSStyleSheet rules to confirm that the body rule
uses ``var(--bg-page)`` (via the ``background`` shorthand) and
``var(--text-primary)``, rather than any hardcoded hex / rgb value.

Additionally the test verifies the computed values of the CSS custom properties
``--bg-page`` and ``--text-primary`` are defined on ``:root`` and that the
browser resolves the body's computed ``background-color`` and ``color`` to the
token values.

Architecture
------------
- Playwright sync API with pytest fixtures.
- Standalone fixture server — no live deployment required.
- PLAYWRIGHT_HEADLESS env var controls headless mode (default: true).
"""
from __future__ import annotations

import os
import re
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import pytest
from playwright.sync_api import sync_playwright, Page

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURE_PORT = 19433
_PAGE_LOAD_TIMEOUT = 15_000  # ms

_GLOBALS_CSS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "web", "src", "app", "globals.css"
)


def _load_globals_css() -> str:
    with open(_GLOBALS_CSS_PATH, encoding="utf-8") as f:
        css = f.read()
    # Strip Tailwind import — not needed for fixture and would fail offline
    css = re.sub(r'@import\s+"tailwindcss"\s*;', "", css)
    return css


# ---------------------------------------------------------------------------
# Fixture HTML
# Loads the actual globals.css (stripping the @import "tailwindcss" line
# which is not needed for this assertion and would fail in an offline server).
# ---------------------------------------------------------------------------

_FIXTURE_HTML = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>MYTUBE-433 — body design-token fixture</title>
  <style id="globals-css">
{_load_globals_css()}
  </style>
</head>
<body id="test-body">
  <p>MYTUBE-433 fixture page</p>
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
        page.wait_for_selector("#test-body", timeout=_PAGE_LOAD_TIMEOUT)
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBodyDesignTokens:
    """MYTUBE-433: body element uses CSS design tokens for background and text."""

    def test_body_background_uses_var_bg_page(self, browser_page: Page) -> None:
        """Step 2: The CSS rule for body must reference var(--bg-page) for background.

        Inspects the CSSStyleSheet rules to find the rule targeting 'body' and
        confirms it uses 'var(--bg-page)' in the background property declaration
        rather than a hardcoded colour value.
        """
        css_text: str = browser_page.evaluate(
            """() => {
                for (const sheet of document.styleSheets) {
                    try {
                        for (const rule of sheet.cssRules) {
                            if (rule.selectorText === 'body') {
                                return rule.cssText;
                            }
                        }
                    } catch (e) {
                        // cross-origin sheets are not accessible
                    }
                }
                return '';
            }"""
        )

        assert css_text, (
            "No CSS rule with selector 'body' was found in any accessible stylesheet. "
            "The globals.css body rule may be missing or the stylesheet was not loaded."
        )

        assert "var(--bg-page)" in css_text, (
            f"Expected the body CSS rule to contain 'var(--bg-page)' for background, "
            f"but the rule was:\n\n  {css_text}\n\n"
            "The body element must use the --bg-page design token instead of a "
            "hardcoded background-color value."
        )

    def test_body_color_uses_var_text_primary(self, browser_page: Page) -> None:
        """Step 2: The CSS rule for body must reference var(--text-primary) for color.

        Inspects the CSSStyleSheet rules to find the rule targeting 'body' and
        confirms it uses 'var(--text-primary)' in the color property declaration
        rather than a hardcoded colour value.
        """
        css_text: str = browser_page.evaluate(
            """() => {
                for (const sheet of document.styleSheets) {
                    try {
                        for (const rule of sheet.cssRules) {
                            if (rule.selectorText === 'body') {
                                return rule.cssText;
                            }
                        }
                    } catch (e) {
                        // cross-origin sheets are not accessible
                    }
                }
                return '';
            }"""
        )

        assert css_text, (
            "No CSS rule with selector 'body' was found in any accessible stylesheet."
        )

        assert "var(--text-primary)" in css_text, (
            f"Expected the body CSS rule to contain 'var(--text-primary)' for color, "
            f"but the rule was:\n\n  {css_text}\n\n"
            "The body element must use the --text-primary design token instead of a "
            "hardcoded color value."
        )

    def test_bg_page_token_resolves_to_expected_computed_color(self, browser_page: Page) -> None:
        """Step 1: The --bg-page token is defined on :root and the browser's
        computed background-color for body matches its resolved value."""
        bg_page_token: str = browser_page.evaluate(
            "() => getComputedStyle(document.documentElement)"
            ".getPropertyValue('--bg-page').trim()"
        )
        assert bg_page_token, (
            "CSS custom property '--bg-page' is not defined on :root. "
            "The design token must be declared in globals.css."
        )

        computed_bg: str = browser_page.evaluate(
            "() => getComputedStyle(document.body).backgroundColor"
        )

        # The token value is #f8f9fa — convert to rgb for comparison
        expected_rgb = "rgb(248, 249, 250)"
        assert computed_bg == expected_rgb, (
            f"Expected body computed background-color to equal '{expected_rgb}' "
            f"(resolved from --bg-page: {bg_page_token.strip()}) "
            f"but got '{computed_bg}'."
        )

    def test_text_primary_token_resolves_to_expected_computed_color(self, browser_page: Page) -> None:
        """Step 1: The --text-primary token is defined on :root and the browser's
        computed color for body matches its resolved value."""
        text_primary_token: str = browser_page.evaluate(
            "() => getComputedStyle(document.documentElement)"
            ".getPropertyValue('--text-primary').trim()"
        )
        assert text_primary_token, (
            "CSS custom property '--text-primary' is not defined on :root. "
            "The design token must be declared in globals.css."
        )

        computed_color: str = browser_page.evaluate(
            "() => getComputedStyle(document.body).color"
        )

        # The token value is #222222 — convert to rgb for comparison
        expected_rgb = "rgb(34, 34, 34)"
        assert computed_color == expected_rgb, (
            f"Expected body computed color to equal '{expected_rgb}' "
            f"(resolved from --text-primary: {text_primary_token.strip()}) "
            f"but got '{computed_color}'."
        )
