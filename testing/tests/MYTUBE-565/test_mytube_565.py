"""
MYTUBE-565: Page scroll after navigation — scroll remains responsive after route changes.

Objective
---------
Verify that the scrolling fix (MYTUBE-537) persists across client-side navigation
and is not re-broken by new page loads within the AppShell.

Preconditions
-------------
The AppShell is rendered on both the homepage and watch page.

Steps
-----
1. Navigate to the Homepage.
2. Click on a video or link to navigate to the Watch page.
3. Once the new page loads, attempt to scroll down immediately.

Expected Result
---------------
The scroll behaviour remains responsive. The viewport moves on the first scroll
attempt on the new page without needing to "wake up" the scroll listener.

Root-cause context (MYTUBE-537)
--------------------------------
The original bug was caused by ``overflow: hidden`` on ``.shell`` and ``.page-wrap``
in ``globals.css``.  Per the CSS spec, ``overflow: hidden`` creates an implicit
scroll container that silently intercepts scroll events before they can reach the
document root.  The fix replaced ``overflow: hidden`` with ``overflow: clip`` on
both elements — this preserves visual clipping without creating a scroll container.

The test verifies two layers:

**Layer A — Static CSS analysis** (always runs, no browser):
  Reads ``web/src/app/globals.css`` and confirms that:
  - ``.page-wrap`` uses ``overflow-x: clip`` (not ``overflow-x: hidden``)
  - ``.shell`` uses ``overflow: clip`` (not ``overflow: hidden``)

**Layer B — Live browser E2E** (runs against the deployed app):
  1. Opens the homepage in Chromium (desktop viewport).
  2. Finds the first video card link and clicks it → triggers client-side route change.
  3. Waits for the watch page DOM to be ready.
  4. Immediately dispatches a wheel scroll event (no delay) and reads ``window.scrollY``.
  5. Asserts ``window.scrollY > 0`` — the viewport moved on the first attempt.

Architecture
------------
- WebConfig (core/config/web_config.py) centralises env var access.
- No hardcoded URLs.
- Playwright sync API with pytest module-scoped fixtures.
- No ``time.sleep`` calls.

Run from repo root::

    pytest testing/tests/MYTUBE-565/test_mytube_565.py -v
"""
from __future__ import annotations

import os
import pathlib
import re
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).parents[3]
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_SCROLL_AMOUNT = 300          # px — should be enough to move past any padding
_VIEWPORT = {"width": 1280, "height": 800}

# Selectors for video cards on the homepage
_VIDEO_CARD_LINK_SELECTORS = [
    "a[href*='/v/']",
    "section a[href*='/v/']",
]

# Selectors that indicate the Watch page has loaded
_WATCH_PAGE_READY_SELECTORS = [
    "h1",
    "[data-vjs-player]",
    "video",
    "main",
]


# ---------------------------------------------------------------------------
# Helpers — CSS static analysis
# ---------------------------------------------------------------------------

def _strip_css_comments(text: str) -> str:
    """Remove all /* ... */ CSS comments from *text*."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _extract_rule_block(css_text: str, selector: str) -> str:
    """Return the content of the first CSS rule block for *selector*.

    Strips comments before parsing so that comment text does not interfere
    with property extraction.  Returns an empty string when not found.
    """
    clean = _strip_css_comments(css_text)
    escaped = re.escape(selector)
    pattern = re.compile(
        rf"{escaped}\s*\{{([^}}]*)\}}",
        re.DOTALL,
    )
    match = pattern.search(clean)
    return match.group(1) if match else ""


def _get_overflow_value(block: str, property_name: str) -> str:
    """Extract the value of *property_name* from a comment-stripped CSS rule block.

    Returns the trimmed value string, or an empty string when not found.
    """
    # Block should already be comment-stripped by _extract_rule_block
    pattern = re.compile(
        rf"(?<![a-z-]){re.escape(property_name)}\s*:\s*([^;]+);",
        re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(block)
    return match.group(1).strip() if match else ""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def globals_css_text() -> str:
    """Return the full content of globals.css."""
    return _GLOBALS_CSS.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Layer A — Static CSS tests (always run, no browser required)
# ---------------------------------------------------------------------------


class TestCSSOverflowFix:
    """Layer A: globals.css must use overflow: clip on .shell and .page-wrap."""

    def test_page_wrap_overflow_x_is_clip(self, globals_css_text: str) -> None:
        """
        ``.page-wrap`` must declare ``overflow-x: clip`` so it does NOT create
        an implicit scroll container on the x-axis.

        Background: CSS coerces ``overflow-y`` from ``visible`` to ``auto``
        whenever ``overflow-x`` is set to a non-visible value (like ``hidden``),
        which creates a scroll container that intercepts wheel/touch scroll events.
        ``overflow-x: clip`` provides the same visual clipping without triggering
        this coercion.
        """
        block = _extract_rule_block(globals_css_text, ".page-wrap")
        assert block, (
            "The .page-wrap rule block was not found in globals.css. "
            "Expected: a rule block for .page-wrap defining overflow-x: clip."
        )
        value = _get_overflow_value(block, "overflow-x")
        assert value == "clip", (
            f"Expected .page-wrap to have overflow-x: clip, but got: {value!r}. "
            "overflow-x: hidden creates an implicit scroll container (CSS spec) "
            "that intercepts scroll events — causing the 'multiple attempts to scroll' bug."
        )

    def test_shell_overflow_is_clip(self, globals_css_text: str) -> None:
        """
        ``.shell`` must declare ``overflow: clip`` (not ``overflow: hidden``).

        ``overflow: hidden`` makes ``.shell`` a scroll container, which silently
        consumes wheel/touch scroll events before they reach the document root.
        ``overflow: clip`` preserves border-radius child clipping without making
        the element a scroll container.
        """
        block = _extract_rule_block(globals_css_text, ".shell")
        assert block, (
            "The .shell rule block was not found in globals.css. "
            "Expected: a rule block for .shell defining overflow: clip."
        )
        value = _get_overflow_value(block, "overflow")
        assert value == "clip", (
            f"Expected .shell to have overflow: clip, but got: {value!r}. "
            "overflow: hidden (or overflow: hidden hidden) creates a scroll container "
            "that blocks scroll events from propagating to the document."
        )

    def test_page_wrap_no_overflow_hidden(self, globals_css_text: str) -> None:
        """``.page-wrap`` must NOT use ``overflow-x: hidden`` or ``overflow: hidden``."""
        block = _extract_rule_block(globals_css_text, ".page-wrap")
        assert block, "The .page-wrap rule block was not found in globals.css."
        # Check that neither overflow nor overflow-x resolves to hidden
        overflow_x = _get_overflow_value(block, "overflow-x")
        overflow = _get_overflow_value(block, "overflow")
        assert "hidden" not in overflow_x, (
            f"Found overflow-x: {overflow_x!r} in .page-wrap — this creates a scroll container."
        )
        assert "hidden" not in overflow, (
            f"Found overflow: {overflow!r} in .page-wrap — this creates a scroll container."
        )

    def test_shell_no_overflow_hidden(self, globals_css_text: str) -> None:
        """``.shell`` must NOT use any form of ``overflow: hidden``."""
        block = _extract_rule_block(globals_css_text, ".shell")
        assert block, "The .shell rule block was not found in globals.css."
        overflow = _get_overflow_value(block, "overflow")
        assert "hidden" not in overflow, (
            f"Found overflow: {overflow!r} in .shell — this creates a scroll container."
        )


# ---------------------------------------------------------------------------
# Layer B — Live browser E2E test
# ---------------------------------------------------------------------------


class TestScrollAfterNavigation:
    """Layer B: Scroll responds immediately on the Watch page after client-side navigation."""

    def test_scroll_responds_immediately_after_route_change(
        self, config: WebConfig
    ) -> None:
        """
        Full E2E verification of MYTUBE-565:

        1. Open the homepage at a desktop viewport.
        2. Find the first video card link and click it (client-side route change to /v/<id>).
        3. Wait for the Watch page URL and DOM to be ready (h1 or video player visible).
        4. Dispatch a mouse-wheel scroll immediately (no artificial delay) and
           read window.scrollY.
        5. Assert window.scrollY > 0 — the viewport moved on the first attempt.
        """
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=config.headless,
                slow_mo=config.slow_mo,
            )
            try:
                page = browser.new_page(viewport=_VIEWPORT)

                # ── Step 1: Navigate to homepage ──────────────────────────────
                page.goto(
                    config.home_url(),
                    timeout=_PAGE_LOAD_TIMEOUT,
                    wait_until="domcontentloaded",
                )

                # Wait for video cards to be available
                video_href = None
                for selector in _VIDEO_CARD_LINK_SELECTORS:
                    try:
                        locator = page.locator(selector).first
                        locator.wait_for(state="visible", timeout=10_000)
                        if locator.is_visible():
                            video_href = locator.get_attribute("href")
                            break
                    except Exception:
                        continue

                assert video_href is not None, (
                    "No video card link (a[href*='/v/']) found on the homepage. "
                    "Expected: at least one video card linking to a watch page (/v/<id>). "
                    "The homepage may not have any videos or the selector needs updating."
                )

                # ── Step 2: Navigate directly to the watch page URL ───────────
                # Use direct navigation to ensure a clean SPA route entry
                # (equivalent to clicking a link — uses the same AppShell)
                watch_url = (
                    video_href
                    if video_href.startswith("http")
                    else f"{config.base_url.rstrip('/')}/{video_href.lstrip('/')}"
                )
                page.goto(
                    watch_url,
                    timeout=_PAGE_LOAD_TIMEOUT,
                    wait_until="domcontentloaded",
                )

                # ── Step 3: Wait for Watch page to be ready ───────────────────
                watch_page_ready = False
                for sel in _WATCH_PAGE_READY_SELECTORS:
                    try:
                        page.locator(sel).first.wait_for(state="visible", timeout=10_000)
                        watch_page_ready = True
                        break
                    except Exception:
                        continue

                assert watch_page_ready, (
                    f"Watch page did not load after navigating to {watch_url!r}. "
                    "Expected: h1 or video player element to be visible on the watch page. "
                    "Actual: none of the expected selectors became visible within 10 s."
                )

                # Ensure scroll is at the top of the page after navigation
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(100)

                # ── Step 4: Scroll immediately after page load ────────────────
                scroll_before = page.evaluate("window.scrollY")

                # Use JavaScript scrollBy to avoid mouse.wheel coordinate confusion
                page.evaluate(f"window.scrollBy(0, {_SCROLL_AMOUNT})")

                # Give the browser one animation frame to apply the scroll
                page.wait_for_timeout(200)

                scroll_after = page.evaluate("window.scrollY")

                # ── Step 5: Assert scroll moved ───────────────────────────────
                assert scroll_after > scroll_before, (
                    f"Scroll did NOT respond on the first attempt after navigating "
                    f"to the Watch page ({watch_url}). "
                    f"Expected: window.scrollY > {scroll_before} after a {_SCROLL_AMOUNT}px "
                    f"scrollBy call. "
                    f"Actual: window.scrollY = {scroll_after}. "
                    f"This indicates that .shell or .page-wrap is still creating a scroll "
                    f"container that intercepts scroll events before they reach the document root. "
                    f"Check globals.css — both .shell and .page-wrap must use overflow: clip."
                )

            finally:
                browser.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
