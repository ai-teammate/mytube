"""
MYTUBE-562: Page scroll via mouse wheel — content moves immediately on the first attempt

Objective
---------
Verify that scrolling using a mouse wheel or trackpad responds immediately on the
first attempt across pages using the AppShell.

Steps
-----
1. Navigate to the homepage or dashboard.
2. Ensure the page has enough content to require scrolling.
3. Without performing any other interaction, use the mouse wheel or trackpad to
   scroll down once.

Expected Result
---------------
The page content moves vertically in response to the very first scroll event
without delay, lag, or the need for multiple attempts.

Root Cause (MYTUBE-537)
-----------------------
``overflow: hidden`` on ``.shell`` and ``.page-wrap`` in ``globals.css`` creates
implicit CSS scroll containers that silently consume wheel/touch scroll events
before they reach the document root — causing the "multiple attempts needed"
symptom. The fix changes both properties to ``overflow: clip``, which provides
identical visual clipping without creating a scroll container.

Test Approach
-------------
**Static analysis** (always runs):
  - Parse ``web/src/app/globals.css``.
  - Assert that ``.shell`` declares ``overflow: clip`` and does NOT declare
    ``overflow: hidden``.
  - Assert that ``.page-wrap`` declares ``overflow-x: clip`` and does NOT
    declare ``overflow-x: hidden`` or ``overflow: hidden``.

**Live Playwright** (runs when APP_URL is set):
  - Navigate to the deployed homepage with a viewport that forces scrollable content.
  - Record ``scrollY`` before any interaction.
  - Dispatch a single ``wheel`` event (deltaY = 300) on the document body.
  - After a short wait, assert ``scrollY`` has increased — confirming the page
    responded to the very first scroll event.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- HomePage from testing/components/pages/home_page/home_page.py provides
  navigation and scroll helpers.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or environment-specific paths.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-562/test_mytube_562.py -v
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.home_page.home_page import HomePage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_SCROLL_WAIT_MS = 800         # ms — allow the scroll event to propagate

# ---------------------------------------------------------------------------
# CSS parsing helpers
# ---------------------------------------------------------------------------


def _extract_rule_block(css: str, selector: str) -> str | None:
    """Return the declaration block text for *selector* in *css*.

    Handles whitespace variants but assumes plain (non-minified) CSS.
    """
    escaped = re.escape(selector)
    pattern = re.compile(escaped + r"\s*\{([^}]*)\}", re.DOTALL)
    m = pattern.search(css)
    return m.group(1) if m else None


def _strip_comments(css: str) -> str:
    """Remove /* ... */ block comments from CSS text."""
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def _normalize_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


# ---------------------------------------------------------------------------
# Mode helpers
# ---------------------------------------------------------------------------


def _live_mode_available() -> bool:
    url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(url and url.lower() not in ("false", "0", ""))


# ---------------------------------------------------------------------------
# Static analysis tests
# ---------------------------------------------------------------------------


class TestScrollCSSStatic:
    """
    Static regression guard: verify that globals.css uses overflow:clip on the
    AppShell containers so that they do not create implicit scroll containers.
    """

    @pytest.fixture(scope="class")
    def css_text(self) -> str:
        assert _GLOBALS_CSS.exists(), (
            f"globals.css not found at {_GLOBALS_CSS}. "
            "Ensure the repository is checked out correctly."
        )
        return _GLOBALS_CSS.read_text(encoding="utf-8")

    def test_shell_has_overflow_clip(self, css_text: str) -> None:
        """
        .shell must declare ``overflow: clip``.

        overflow:hidden on this element creates an implicit scroll container
        (per CSS Overflow spec level 3) that silently swallows wheel/touch
        scroll events — the root cause of MYTUBE-537.  overflow:clip provides
        identical visual border-radius clipping without becoming a scroll
        container.
        """
        block = _extract_rule_block(css_text, ".shell")
        assert block is not None, (
            "CSS rule '.shell' not found in globals.css. "
            "The AppShell container rule must be defined here."
        )
        norm = _normalize_ws(block)
        assert "overflow: clip" in norm or "overflow:clip" in norm, (
            "'.shell' must declare 'overflow: clip' to prevent the implicit "
            "scroll container that blocks first-attempt mouse-wheel scrolling "
            f"(MYTUBE-537 regression guard).\nActual block:\n{block.strip()}"
        )

    def test_shell_does_not_have_overflow_hidden(self, css_text: str) -> None:
        """
        .shell must NOT declare ``overflow: hidden``.

        This is the forbidden value that triggered MYTUBE-537: it coerces the
        element into a scroll container, silently consuming scroll events.
        """
        block = _extract_rule_block(css_text, ".shell")
        assert block is not None, (
            "CSS rule '.shell' not found in globals.css."
        )
        norm = _normalize_ws(_strip_comments(block))
        # "overflow: hidden" or "overflow:hidden" — must not appear
        assert "overflow: hidden" not in norm and "overflow:hidden" not in norm, (
            "'.shell' must NOT declare 'overflow: hidden'. "
            "This value creates an implicit scroll container that intercepts "
            "wheel/touch scroll events (root cause of MYTUBE-537).\n"
            f"Actual block:\n{block.strip()}"
        )

    def test_page_wrap_has_overflow_x_clip(self, css_text: str) -> None:
        """
        .page-wrap must declare ``overflow-x: clip``.

        Setting overflow-x to a non-visible value while leaving overflow-y as
        visible causes the CSS engine to coerce overflow-y to auto, implicitly
        creating a y-scroll container on .page-wrap.  overflow-x:clip avoids
        that coercion while still clipping decorative overflows.
        """
        block = _extract_rule_block(css_text, ".page-wrap")
        assert block is not None, (
            "CSS rule '.page-wrap' not found in globals.css. "
            "The AppShell outer container rule must be defined here."
        )
        norm = _normalize_ws(block)
        assert "overflow-x: clip" in norm or "overflow-x:clip" in norm, (
            "'.page-wrap' must declare 'overflow-x: clip' to avoid the implicit "
            "y-scroll container created when overflow-x is non-visible "
            f"(MYTUBE-537 regression guard).\nActual block:\n{block.strip()}"
        )

    def test_page_wrap_does_not_have_overflow_x_hidden(self, css_text: str) -> None:
        """
        .page-wrap must NOT declare ``overflow-x: hidden`` (or plain ``overflow: hidden``).
        """
        block = _extract_rule_block(css_text, ".page-wrap")
        assert block is not None, (
            "CSS rule '.page-wrap' not found in globals.css."
        )
        norm = _normalize_ws(_strip_comments(block))
        assert "overflow-x: hidden" not in norm and "overflow-x:hidden" not in norm, (
            "'.page-wrap' must NOT declare 'overflow-x: hidden'. "
            "This value coerces overflow-y to auto, creating an implicit "
            "scroll container (root cause of MYTUBE-537).\n"
            f"Actual block:\n{block.strip()}"
        )
        assert "overflow: hidden" not in norm and "overflow:hidden" not in norm, (
            "'.page-wrap' must NOT declare 'overflow: hidden'. "
            "Use 'overflow-x: clip' instead.\n"
            f"Actual block:\n{block.strip()}"
        )


# ---------------------------------------------------------------------------
# Live Playwright tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _live_mode_available(),
    reason="APP_URL / WEB_BASE_URL not set — skipping live scroll verification",
)
class TestScrollLive:
    """
    Live end-to-end verification: a single wheel event scrolls the page on the
    first attempt (no second event required).
    """

    @pytest.fixture(scope="class")
    def config(self) -> WebConfig:
        return WebConfig()

    @pytest.fixture(scope="class")
    def page_and_home(self, config: WebConfig):
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=config.headless,
                slow_mo=config.slow_mo,
            )
            # Narrow viewport ensures there is content below the fold.
            page = browser.new_page(viewport={"width": 1280, "height": 700})
            page.goto(
                config.home_url(),
                timeout=_PAGE_LOAD_TIMEOUT,
                wait_until="networkidle",
            )
            home = HomePage(page)
            yield page, home
            browser.close()

    def test_single_wheel_event_scrolls_page(self, page_and_home) -> None:
        """
        A single mouse-wheel event dispatched on the document body must cause
        ``scrollY`` to increase — confirming that the AppShell containers no
        longer intercept the event.

        Steps
        -----
        1. Navigate to the homepage (done in fixture).
        2. Ensure scrollY starts at 0.
        3. Dispatch one wheel event (deltaY = 300).
        4. Wait a short period for the event to propagate.
        5. Assert scrollY > 0.
        """
        page, home = page_and_home

        # Scroll back to absolute top for a clean baseline.
        page.evaluate("window.scrollTo(0, 0)")
        page.wait_for_timeout(200)

        initial_y: int = page.evaluate("() => window.scrollY")
        assert initial_y == 0, (
            f"Expected scrollY to be 0 before the test, got {initial_y}. "
            "Could not establish a clean baseline."
        )

        # Dispatch a single wheel event — equivalent to one click of the scroll wheel.
        page.evaluate(
            """() => {
                const evt = new WheelEvent('wheel', {
                    deltaY: 300,
                    deltaMode: 0,
                    bubbles: true,
                    cancelable: true
                });
                document.body.dispatchEvent(evt);
            }"""
        )

        # Wait for the scroll to propagate/animate.
        page.wait_for_timeout(_SCROLL_WAIT_MS)

        final_y: int = page.evaluate("() => window.scrollY")
        assert final_y > initial_y, (
            f"Page did not scroll after a single wheel event. "
            f"scrollY before: {initial_y}, scrollY after: {final_y}. "
            "This indicates an overflow:hidden scroll container on .shell or "
            ".page-wrap is intercepting the wheel event (MYTUBE-537 regression). "
            f"URL: {page.url}"
        )
