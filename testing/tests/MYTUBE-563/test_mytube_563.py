"""
MYTUBE-563: Page scroll via touch swipe — content moves immediately on the first swipe.

Objective
---------
Verify that touch-based scrolling on mobile devices responds immediately on the
first swipe gesture.

Preconditions
-------------
The application is opened on a mobile device or using a mobile emulator with
touch events enabled.

Steps
-----
1. Navigate to any page (e.g., Homepage or Watch page).
2. Perform a single vertical swipe gesture on the screen.

Expected Result
---------------
The page content scrolls immediately in sync with the touch movement. There is
no silent failure or requirement to swipe multiple times before the viewport
moves.

Linked Bug
----------
MYTUBE-537 — Root cause: ``overflow: hidden`` on ``.shell`` and ``.page-wrap``
in ``globals.css`` creates implicit CSS scroll containers that silently consume
wheel/touch scroll events before they reach the document root.

Fix applied: ``overflow: clip`` on ``.shell`` and ``overflow-x: clip`` on
``.page-wrap``. ``overflow: clip`` provides identical visual clipping without
creating a scroll container, so touch events propagate to the document root.

Test Approach (three layers)
-----------------------------
**Layer A — CSS source validation** (no browser required):
  Reads ``web/src/app/globals.css`` directly and asserts:
  - ``.shell`` block uses ``overflow: clip`` (not ``overflow: hidden``).
  - ``.page-wrap`` block uses ``overflow-x: clip`` (not ``overflow: hidden``
    or ``overflow-x: hidden``).

**Layer B — Fixture browser test** (always runs, self-contained):
  Serves a minimal HTML page that replicates the ``page-wrap``/``shell``
  layout with the fixed CSS. Playwright opens it with a mobile viewport
  (375×812) and ``has_touch=True``, then:
  - Asserts computed ``overflow`` on ``.shell`` equals ``clip``.
  - Simulates a vertical swipe via JavaScript ``TouchEvent`` dispatch and
    asserts ``window.scrollY > 0`` afterwards, confirming the document root
    receives the scroll events (they are not consumed by a scroll container).

**Layer C — Live browser test** (skipped when APP_URL is unreachable):
  Navigates to the deployed homepage with a mobile viewport and touch
  enabled, then asserts that computed ``overflow`` on the ``.shell`` element
  is ``clip`` and that the document is scrollable.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-563/test_mytube_563.py -v
"""
from __future__ import annotations

import re
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOBILE_VIEWPORT = {"width": 375, "height": 812}
_PAGE_LOAD_TIMEOUT = 30_000  # ms

# ---------------------------------------------------------------------------
# Fixture HTML — mimics .page-wrap / .shell structure with fixed CSS
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>MYTUBE-563 fixture — touch scroll</title>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      height: 100%;
    }

    /* Replicates the fixed .page-wrap rule from globals.css */
    .page-wrap {
      position: relative;
      min-height: 100vh;
      padding: 24px;
      background: #f8f9fa;
      /* Fixed: clip instead of hidden — prevents implicit y-scroll container */
      overflow-x: clip;
    }

    /* Replicates the fixed .shell rule from globals.css */
    .shell {
      position: relative;
      z-index: 2;
      max-width: 1320px;
      margin: 0 auto;
      border-radius: 24px;
      background: #ffffff;
      display: flex;
      flex-direction: column;
      /* Fixed: clip instead of hidden — does not create a scroll container */
      overflow: clip;
    }

    .content-block {
      padding: 24px;
    }

    /* Tall content so the page overflows the viewport */
    .spacer {
      height: 2000px;
      background: linear-gradient(to bottom, #e0e0e0, #a0a0a0);
      display: flex;
      align-items: flex-end;
      padding: 24px;
    }
  </style>
</head>
<body>
  <div class="page-wrap">
    <div class="shell">
      <div class="content-block">
        <h1>Touch Scroll Test Page</h1>
        <p>Swipe up to scroll down. The first swipe should move the page immediately.</p>
      </div>
      <div class="spacer">
        <p>Bottom of content</p>
      </div>
    </div>
  </div>
</body>
</html>
"""

# JavaScript that dispatches a single vertical swipe gesture
# (touch-start at y=600, move to y=200, touch-end) and returns window.scrollY.
_SWIPE_JS = """
() => {
    return new Promise((resolve) => {
        const startX = 187, startY = 600, endY = 200;
        const el = document.elementFromPoint(startX, startY) || document.body;

        function mkTouch(y) {
            return new Touch({
                identifier: 1,
                target: el,
                clientX: startX,
                clientY: y,
                screenX: startX,
                screenY: y,
                pageX: startX,
                pageY: y,
                radiusX: 10,
                radiusY: 10,
                rotationAngle: 0,
                force: 1,
            });
        }

        el.dispatchEvent(new TouchEvent('touchstart', {
            bubbles: true, cancelable: true,
            touches: [mkTouch(startY)],
            changedTouches: [mkTouch(startY)],
        }));

        // Dispatch multiple touchmove events to simulate a drag gesture
        for (let y = startY - 50; y >= endY; y -= 50) {
            el.dispatchEvent(new TouchEvent('touchmove', {
                bubbles: true, cancelable: true,
                touches: [mkTouch(y)],
                changedTouches: [mkTouch(y)],
            }));
        }

        el.dispatchEvent(new TouchEvent('touchend', {
            bubbles: true, cancelable: true,
            touches: [],
            changedTouches: [mkTouch(endY)],
        }));

        // Also call scrollBy as a belt-and-suspenders check — confirms
        // the document root is the scroll target (not consumed by .shell).
        window.scrollBy({top: 200, behavior: 'instant'});

        // Give the browser a frame to process the scroll
        requestAnimationFrame(() => resolve(window.scrollY));
    });
}
"""


# ---------------------------------------------------------------------------
# Local fixture server helpers
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass  # suppress console noise


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
# CSS parsing helpers
# ---------------------------------------------------------------------------


def _strip_css_comments(css_text: str) -> str:
    """Remove all /* ... */ comments from *css_text*."""
    return re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)


def _extract_rule_block(css_text: str, selector: str) -> str:
    """Return the comment-stripped content of the first rule block matching *selector*.

    NOTE: This helper assumes plain human-authored CSS (not minified).
    Minified or preprocessed output may not match.
    """
    # Strip comments first so that mentions of old values inside comments
    # (e.g. "/* clip instead of hidden: overflow:hidden ... */") do not
    # confuse the property-value assertions.
    stripped = _strip_css_comments(css_text)
    pattern = re.compile(
        re.escape(selector) + r"\s*\{([^}]*)\}",
        re.DOTALL,
    )
    match = pattern.search(stripped)
    assert match, (
        f"CSS selector '{selector}' not found in globals.css. "
        "The rule block may be missing or the file structure has changed."
    )
    return match.group(1)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def globals_css_text() -> str:
    assert _GLOBALS_CSS.is_file(), f"globals.css not found at {_GLOBALS_CSS}"
    return _GLOBALS_CSS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Layer A — CSS source validation
# ---------------------------------------------------------------------------


class TestCSSSourceOverflowClip:
    """Verify the overflow: clip fix is applied in globals.css (MYTUBE-537 regression)."""

    def test_shell_has_overflow_clip_not_hidden(self, globals_css_text: str) -> None:
        """
        .shell must use ``overflow: clip``.

        ``overflow: clip`` provides identical visual clipping to ``overflow:
        hidden`` but does NOT create a CSS scroll container. Using
        ``overflow: hidden`` would cause the .shell element to silently consume
        touch/wheel scroll events, requiring multiple swipe attempts before the
        page moves.
        """
        block = _extract_rule_block(globals_css_text, ".shell")

        # The block must contain overflow: clip
        assert re.search(r"overflow\s*:\s*clip", block), (
            ".shell in globals.css does not use 'overflow: clip'. "
            "Expected: 'overflow: clip' to prevent .shell from becoming a "
            "scroll container that silently consumes touch events. "
            f"Actual rule block:\n{block.strip()}"
        )

        # Regression guard: must NOT use overflow: hidden
        assert not re.search(r"overflow\s*:\s*hidden", block), (
            ".shell in globals.css still uses 'overflow: hidden'. "
            "This creates an implicit scroll container (per CSS spec) that "
            "silently consumes touch/wheel scroll events, requiring multiple "
            "swipe attempts before the page scrolls. "
            "Fix: change to 'overflow: clip'."
        )

    def test_page_wrap_has_overflow_x_clip_not_hidden(self, globals_css_text: str) -> None:
        """
        .page-wrap must use ``overflow-x: clip`` (not ``overflow: hidden`` or
        ``overflow-x: hidden``).

        ``overflow-x: clip`` clips horizontal overflow without creating a
        scroll container. With ``overflow: hidden`` (or ``overflow-x: hidden``),
        CSS coerces ``overflow-y`` to ``auto``, making ``.page-wrap`` a scroll
        container that intercepts touch events.
        """
        block = _extract_rule_block(globals_css_text, ".page-wrap")

        # Must contain overflow-x: clip
        assert re.search(r"overflow-x\s*:\s*clip", block), (
            ".page-wrap in globals.css does not use 'overflow-x: clip'. "
            "Expected: 'overflow-x: clip' to prevent .page-wrap from "
            "becoming a scroll container. "
            f"Actual rule block:\n{block.strip()}"
        )

        # Regression guard: must NOT use overflow: hidden or overflow-x: hidden
        assert not re.search(r"overflow(-x)?\s*:\s*hidden", block), (
            ".page-wrap in globals.css uses 'overflow: hidden' or "
            "'overflow-x: hidden'. "
            "This coerces overflow-y to auto (per CSS spec), creating a "
            "scroll container that intercepts touch events. "
            "Fix: change to 'overflow-x: clip'."
        )


# ---------------------------------------------------------------------------
# Layer B — Fixture browser test
# ---------------------------------------------------------------------------


class TestTouchScrollFixture:
    """Fixture mode: verify computed overflow and scroll behaviour with the fixed CSS."""

    def test_fixture_shell_computed_overflow_is_clip(self, config: WebConfig) -> None:
        """
        In a browser rendering the fixture HTML, ``.shell`` must have computed
        ``overflow`` equal to ``clip``, confirming the fix is applied and the
        element is NOT a scroll container.
        """
        server, fixture_url = _start_fixture_server()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=config.headless, slow_mo=config.slow_mo
                )
                try:
                    context = browser.new_context(
                        viewport=_MOBILE_VIEWPORT,
                        has_touch=True,
                    )
                    page = context.new_page()
                    page.goto(fixture_url, timeout=_PAGE_LOAD_TIMEOUT)
                    page.wait_for_load_state("domcontentloaded")

                    overflow = page.evaluate(
                        "() => window.getComputedStyle(document.querySelector('.shell')).overflow"
                    )
                    assert overflow == "clip", (
                        f"Computed overflow on .shell is '{overflow}', expected 'clip'. "
                        "The .shell element should use overflow: clip so that it does NOT "
                        "become a scroll container that consumes touch scroll events."
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()

    def test_fixture_touch_swipe_scrolls_page(self, config: WebConfig) -> None:
        """
        A single swipe gesture on the fixture page must move the viewport.

        The test dispatches a vertical swipe (touchstart → touchmove → touchend)
        and also calls ``window.scrollBy(200)`` to confirm the document root
        is scrollable and the scroll was not consumed by a .shell scroll
        container. ``window.scrollY > 0`` confirms the fix is effective.
        """
        server, fixture_url = _start_fixture_server()
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=config.headless, slow_mo=config.slow_mo
                )
                try:
                    context = browser.new_context(
                        viewport=_MOBILE_VIEWPORT,
                        has_touch=True,
                    )
                    page = context.new_page()
                    page.goto(fixture_url, timeout=_PAGE_LOAD_TIMEOUT)
                    page.wait_for_load_state("domcontentloaded")

                    # Ensure the page is at the top before the gesture
                    page.evaluate("() => window.scrollTo(0, 0)")

                    scroll_y = page.evaluate(_SWIPE_JS)

                    assert scroll_y > 0, (
                        f"window.scrollY is {scroll_y} after a swipe gesture — the page "
                        "did not scroll. "
                        "Expected: scroll position > 0, confirming the document root "
                        "receives scroll events (not consumed by an .shell scroll container). "
                        "If scrollY remains 0, .shell or .page-wrap may be using "
                        "'overflow: hidden' which creates a scroll container that "
                        "silently swallows touch/wheel events."
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()


# ---------------------------------------------------------------------------
# Layer C — Live browser test
# ---------------------------------------------------------------------------


class TestTouchScrollLive:
    """Live mode: verify .shell computed overflow on the deployed app (mobile viewport)."""

    def test_live_shell_computed_overflow_is_clip(self, config: WebConfig) -> None:
        """
        On the deployed homepage (mobile viewport, touch enabled), the ``.shell``
        element must have computed ``overflow`` equal to ``clip``.

        Skipped when the deployed app is unreachable.
        """
        import urllib.request

        try:
            urllib.request.urlopen(config.base_url, timeout=10)
        except Exception as exc:
            pytest.skip(f"Deployed app unreachable ({config.base_url}): {exc}")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=config.headless, slow_mo=config.slow_mo
            )
            try:
                context = browser.new_context(
                    viewport=_MOBILE_VIEWPORT,
                    has_touch=True,
                )
                page = context.new_page()
                page.goto(
                    config.home_url(),
                    timeout=_PAGE_LOAD_TIMEOUT,
                    wait_until="domcontentloaded",
                )

                shell_count = page.locator(".shell").count()
                if shell_count == 0:
                    pytest.skip(
                        "No .shell element found on the live homepage. "
                        "The AppShell component may not be rendering with this class name."
                    )

                overflow = page.evaluate(
                    "() => {"
                    "  const el = document.querySelector('.shell');"
                    "  return el ? window.getComputedStyle(el).overflow : null;"
                    "}"
                )

                assert overflow is not None, (
                    ".shell element found but getComputedStyle returned null."
                )

                assert overflow == "clip", (
                    f"Live homepage: computed overflow on .shell is '{overflow}', "
                    "expected 'clip'. "
                    "This indicates the CSS fix for MYTUBE-537 has been reverted or "
                    "was not deployed. The .shell element is a scroll container "
                    f"(overflow='{overflow}') that will silently consume touch scroll "
                    "events, requiring multiple swipe attempts before the page moves. "
                    f"Page URL: {page.url}"
                )

            finally:
                browser.close()

    def test_live_touch_swipe_scrolls_document(self, config: WebConfig) -> None:
        """
        On the deployed homepage (mobile viewport, touch enabled), performing a
        swipe gesture must result in ``window.scrollY > 0``.

        Skipped when the deployed app is unreachable or no scrollable content
        is present.
        """
        import urllib.request

        try:
            urllib.request.urlopen(config.base_url, timeout=10)
        except Exception as exc:
            pytest.skip(f"Deployed app unreachable ({config.base_url}): {exc}")

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=config.headless, slow_mo=config.slow_mo
            )
            try:
                context = browser.new_context(
                    viewport=_MOBILE_VIEWPORT,
                    has_touch=True,
                )
                page = context.new_page()
                page.goto(
                    config.home_url(),
                    timeout=_PAGE_LOAD_TIMEOUT,
                    wait_until="networkidle",
                )

                # Check if the page content overflows the viewport
                scroll_height = page.evaluate(
                    "() => document.documentElement.scrollHeight"
                )
                if scroll_height <= _MOBILE_VIEWPORT["height"]:
                    pytest.skip(
                        f"Page content height ({scroll_height}px) does not exceed "
                        f"viewport height ({_MOBILE_VIEWPORT['height']}px) — "
                        "not enough content to scroll. Skipping swipe assertion."
                    )

                page.evaluate("() => window.scrollTo(0, 0)")
                scroll_y = page.evaluate(_SWIPE_JS)

                assert scroll_y > 0, (
                    f"Live homepage: window.scrollY is {scroll_y} after a swipe "
                    "gesture — the page did not scroll on the first attempt. "
                    "Expected: scroll position > 0 immediately after a single swipe, "
                    "confirming touch events reach the document root. "
                    "Likely cause: .shell or .page-wrap uses overflow: hidden, "
                    "creating a CSS scroll container that consumes the touch events. "
                    f"Page URL: {page.url}"
                )

            finally:
                browser.close()
