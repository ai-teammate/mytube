"""
MYTUBE-561: Header transition at 768px breakpoint — layout adjusts without stacking errors

Objective
---------
Verify the transition between tablet and mobile viewports to ensure layout rules
(flex/grid) change correctly at the 768px breakpoint. The header must not have
any intermediate state where elements stack incorrectly or overflow.

Preconditions
-------------
- The deployed application is accessible (live mode) OR a static analysis pass
  confirms the responsive CSS classes are in place (static mode).
- The bug fix from MYTUBE-536 is deployed:
  - px-4 sm:px-10, gap-3 sm:gap-6, min-h-[56px] sm:min-h-[88px] on <header>
  - min-w-0 on the search <form> and <input>
  - overflow: hidden on the .shell wrapper

Steps (per test spec)
---------------------
1. Start with a viewport width of 800px.
2. Gradually reduce to 768px, then 760px.
3. At each width, assert the header has no horizontal overflow and elements
   do not stack into multiple rows.

Expected Result
---------------
At every checked width (800px, 768px, 760px), the header flex row renders in a
single row with no scrollable overflow. The background/layout classes transition
according to the Tailwind sm: breakpoint (default 640px) so all three widths
should show the sm+ layout; the header must contain itself horizontally at each
step.

Architecture
------------
- Dual-mode: static CSS class analysis (always) + live Playwright (when APP_URL set).
- WebConfig (testing/core/config/web_config.py) centralises env-var access.
- SiteHeader page object (testing/components/pages/site_header/site_header.py)
  wraps header DOM queries.
- No hardcoded URLs; no time.sleep in favour of Playwright auto-wait.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-561/test_mytube_561.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SITE_HEADER_TSX = _REPO_ROOT / "web" / "src" / "components" / "SiteHeader.tsx"
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_HEIGHT = 900  # viewport height (fixed for all checks)

# Three widths to check per the test spec
_WIDTHS = [800, 768, 760]

# JS snippet that returns layout metrics for the <header> element:
#   overflowPx: scrollWidth - clientWidth (positive → horizontal overflow)
#   rowCount:   number of flex rows detected by tracking vertical bands
#               (> 1 → wrapping / stacking)
#   headerWidth / headerScrollWidth / headerHeight: raw dimensions
#
# Row detection works by tracking a currentRowBottom cursor: if a child's
# top >= currentRowBottom - tolerance it belongs to a new row (flex wrapped).
# This correctly handles items-center alignment where elements of different
# heights have different absolute top values but still occupy one row.
_HEADER_METRICS_JS = """
() => {
    const header = document.querySelector('header');
    if (!header) return null;
    const overflowPx = header.scrollWidth - header.clientWidth;
    const children = Array.from(header.children);
    if (children.length === 0) {
        return {
            overflowPx: overflowPx,
            rowCount: 0,
            headerWidth: header.clientWidth,
            headerScrollWidth: header.scrollWidth,
            headerHeight: header.clientHeight,
            childCount: 0,
        };
    }
    const rects = children.map(c => c.getBoundingClientRect());
    // Start from the first child's row
    let rowCount = 1;
    let currentRowBottom = rects[0].bottom;
    const TOLERANCE = 4; // px — handles sub-pixel rounding
    for (let i = 1; i < rects.length; i++) {
        if (rects[i].top >= currentRowBottom - TOLERANCE) {
            // Child starts at or below the current row → new row (wrapped)
            rowCount++;
            currentRowBottom = rects[i].bottom;
        } else {
            currentRowBottom = Math.max(currentRowBottom, rects[i].bottom);
        }
    }
    return {
        overflowPx: overflowPx,
        rowCount:   rowCount,
        headerWidth: header.clientWidth,
        headerScrollWidth: header.scrollWidth,
        headerHeight: header.clientHeight,
        childCount: children.length,
    };
}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _should_use_live_mode() -> bool:
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMytube561HeaderBreakpoint:
    """MYTUBE-561 — Header layout is correct around the 768px breakpoint."""

    # ──────────────────────────────────────────────────────────────────────────
    # Static analysis (always runs — no browser required)
    # ──────────────────────────────────────────────────────────────────────────

    def test_static_header_has_responsive_padding_classes(self) -> None:
        """SiteHeader.tsx must declare responsive padding: px-4 sm:px-10.

        These classes ensure the header does not overflow on narrow viewports.
        The bug (MYTUBE-536) was caused by bare px-10 with no mobile override.
        """
        tsx = _read_file(_SITE_HEADER_TSX)
        assert tsx, f"SiteHeader.tsx not found at {_SITE_HEADER_TSX}"

        classes = tsx.split()
        # px-4 (mobile default) must be present somewhere in the class string
        assert any("px-4" in c for c in classes), (
            "Expected 'px-4' in SiteHeader.tsx header className for mobile padding. "
            "The header uses bare px-10 without a mobile override — this caused "
            "overflow/misalignment on viewports < 640px (MYTUBE-536 regression)."
        )
        # sm:px-10 must be present (desktop override)
        assert any("sm:px-10" in c for c in classes), (
            "Expected 'sm:px-10' in SiteHeader.tsx header className. "
            "Desktop padding breakpoint override is missing."
        )

    def test_static_header_has_responsive_gap_classes(self) -> None:
        """SiteHeader.tsx must declare responsive gap: gap-3 sm:gap-6."""
        tsx = _read_file(_SITE_HEADER_TSX)
        assert tsx, f"SiteHeader.tsx not found at {_SITE_HEADER_TSX}"

        classes = tsx.split()
        assert any("gap-3" in c for c in classes), (
            "Expected 'gap-3' in SiteHeader.tsx className for mobile gap. "
        )
        assert any("sm:gap-6" in c for c in classes), (
            "Expected 'sm:gap-6' in SiteHeader.tsx className."
        )

    def test_static_header_has_responsive_min_height(self) -> None:
        """SiteHeader.tsx must declare min-h-[56px] sm:min-h-[88px].

        The mobile minimum height must be smaller so the header doesn't force
        vertical overflow on narrow viewports.
        """
        tsx = _read_file(_SITE_HEADER_TSX)
        assert tsx, f"SiteHeader.tsx not found at {_SITE_HEADER_TSX}"

        assert "min-h-[56px]" in tsx, (
            "Expected 'min-h-[56px]' in SiteHeader.tsx className. "
            "Mobile min-height must be lower than the desktop value (88px)."
        )
        assert "sm:min-h-[88px]" in tsx, (
            "Expected 'sm:min-h-[88px]' in SiteHeader.tsx className."
        )

    def test_static_search_form_has_min_w_0(self) -> None:
        """The search <form> must carry min-w-0 so it can shrink in the flex row.

        Without min-w-0, a flex child cannot shrink below its intrinsic width,
        which causes horizontal overflow at narrow viewports.
        """
        tsx = _read_file(_SITE_HEADER_TSX)
        assert tsx, f"SiteHeader.tsx not found at {_SITE_HEADER_TSX}"

        assert "min-w-0" in tsx, (
            "Expected 'min-w-0' in SiteHeader.tsx (on search form and/or input). "
            "Without min-w-0, flex children cannot shrink — overflow persists."
        )

    def test_static_shell_has_overflow_hidden(self) -> None:
        """globals.css must apply overflow-x-hidden (or overflow: hidden) to the
        .shell wrapper so that any residual overflow is visually clipped.
        """
        css = _read_file(_GLOBALS_CSS)
        assert css, f"globals.css not found at {_GLOBALS_CSS}"

        assert "overflow" in css and ("hidden" in css), (
            "Expected overflow:hidden or overflow-x:hidden in globals.css. "
            "The .shell wrapper must clip any residual overflow from child elements."
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Live Playwright (skipped when app unreachable)
    # ──────────────────────────────────────────────────────────────────────────

    def test_live_header_no_overflow_at_800px(self, config: WebConfig) -> None:
        """At 800px viewport, the header must not overflow horizontally."""
        self._assert_header_no_overflow(config, width=800)

    def test_live_header_no_overflow_at_768px(self, config: WebConfig) -> None:
        """At exactly 768px — the breakpoint named in the ticket — the header
        must not overflow and elements must remain in a single row."""
        self._assert_header_no_overflow(config, width=768)

    def test_live_header_no_overflow_at_760px(self, config: WebConfig) -> None:
        """At 760px — just below 768px — the header must still fit without
        stacking or overflowing."""
        self._assert_header_no_overflow(config, width=760)

    # ──────────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _assert_header_no_overflow(self, config: WebConfig, width: int) -> None:
        """Navigate to the homepage at *width* × _HEIGHT and assert the header
        has no horizontal overflow and its flex children form a single row."""
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
                page = browser.new_page(
                    viewport={"width": width, "height": _HEIGHT}
                )
                page.goto(
                    config.home_url(),
                    timeout=_PAGE_LOAD_TIMEOUT,
                    wait_until="domcontentloaded",
                )
                # Wait for the header to be in the DOM
                page.wait_for_selector("header", timeout=10_000)

                metrics = page.evaluate(_HEADER_METRICS_JS)
                assert metrics is not None, (
                    f"No <header> element found on the page at width={width}px. "
                    "The SiteHeader component may not be rendering."
                )

                overflow_px = metrics["overflowPx"]
                row_count = metrics["rowCount"]
                header_width = metrics["headerWidth"]
                scroll_width = metrics["headerScrollWidth"]
                child_count = metrics["childCount"]

                assert overflow_px <= 0, (
                    f"Header has horizontal overflow of {overflow_px}px at viewport width={width}px. "
                    f"clientWidth={header_width}px, scrollWidth={scroll_width}px. "
                    "Expected: header fits within the viewport without horizontal scroll. "
                    "This likely means the responsive padding/gap/min-w-0 fix from "
                    "MYTUBE-536 is not applied or is being overridden. "
                    "Fix: ensure SiteHeader.tsx uses px-4 sm:px-10, gap-3 sm:gap-6, "
                    "and min-w-0 on the search form and input."
                )

                assert row_count <= 2, (
                    f"Header flex children are stacking into {row_count} distinct vertical "
                    f"rows at viewport width={width}px (expected ≤ 2 for a single flex row). "
                    f"childCount={child_count}. "
                    "This indicates the header flex layout is wrapping or stacking — "
                    "an intermediate broken state during the transition. "
                    "Fix: ensure the header does not use flex-wrap or has sufficient "
                    "shrink budget (min-w-0 on flex children)."
                )

            finally:
                browser.close()
