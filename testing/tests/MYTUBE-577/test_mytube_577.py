"""
MYTUBE-577: Logo scaling across breakpoints — aspect ratio is maintained without distortion

Objective
---------
Ensure the logo renders correctly without stretching or distortion when the
viewport size changes.

Steps (per test spec)
---------------------
1. Load the application on a desktop browser.
2. Use browser developer tools to toggle various device resolutions
   (mobile, tablet, desktop).
3. Observe the rendered dimensions and aspect ratio of the logo in the
   SiteHeader.

Expected Result
---------------
The logo maintains its original aspect ratio and visual clarity at all sizes
used across breakpoints — no distortion.

Architecture
------------
- Dual-mode: static source-code analysis (always runs) + live Playwright
  (when APP_URL / WEB_BASE_URL is reachable).
- WebConfig (testing/core/config/web_config.py) centralises env-var access.
- SiteHeader page object (testing/components/pages/site_header/site_header.py)
  wraps header DOM queries.
- No hardcoded URLs; no time.sleep (Playwright auto-wait).

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-577/test_mytube_577.py -v
"""
from __future__ import annotations

import os
import sys
import urllib.request
from pathlib import Path
from typing import Generator

import pytest
from playwright.sync_api import Browser, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.site_header.site_header import SiteHeader
from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SITE_HEADER_TSX = _REPO_ROOT / "web" / "src" / "components" / "SiteHeader.tsx"
_LOGO_ICON_TSX = _REPO_ROOT / "web" / "src" / "components" / "icons" / "LogoIcon.tsx"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_VIEWPORT_HEIGHT = 900

# Breakpoints to test: (label, width)
_BREAKPOINTS = [
    ("desktop", 1280),
    ("tablet", 768),
    ("mobile", 375),
]

# Maximum allowed deviation from a perfect 1:1 aspect ratio (unitless ratio)
# e.g. 0.05 means we accept width/height between 0.95 and 1.05
_ASPECT_RATIO_TOLERANCE = 0.05

# CSS selector for the LogoIcon SVG inside the site header
# SiteHeader.tsx: <Link href="/" className="flex items-center gap-2 shrink-0">
#                   <LogoIcon className="w-11 h-11" …>
_LOGO_SVG_SELECTOR = "header a.shrink-0 svg"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _is_url_reachable(url: str, timeout: int = 10) -> bool:
    try:
        res = urllib.request.urlopen(url, timeout=timeout)
        return res.status < 500
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def playwright_browser(config: WebConfig) -> Generator[Browser, None, None]:
    """Chromium browser for the duration of the test module."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless, slow_mo=config.slow_mo
        )
        yield browser
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLogoAspectRatioBreakpoints:
    """MYTUBE-577 — Logo maintains 1:1 aspect ratio across all breakpoints."""

    # ──────────────────────────────────────────────────────────────────────
    # Static analysis (always runs — no browser required)
    # ──────────────────────────────────────────────────────────────────────

    def test_static_logo_icon_has_square_viewbox(self) -> None:
        """LogoIcon.tsx must declare a square viewBox (equal width and height).

        A square viewBox (e.g. '0 0 40 40') is the SVG-level guarantee that
        the intrinsic aspect ratio is 1:1 before any CSS is applied.
        """
        tsx = _read_file(_LOGO_ICON_TSX)
        assert tsx, f"LogoIcon.tsx not found at {_LOGO_ICON_TSX}"

        import re

        # Match viewBox="0 0 W H" and check W == H
        match = re.search(r'viewBox=["\']0 0 (\d+(?:\.\d+)?) (\d+(?:\.\d+)?)["\']', tsx)
        assert match, (
            "No viewBox attribute found in LogoIcon.tsx SVG element. "
            "The SVG must declare a viewBox to guarantee intrinsic aspect ratio."
        )
        vb_w, vb_h = float(match.group(1)), float(match.group(2))
        assert vb_w == vb_h, (
            f"LogoIcon.tsx viewBox is not square: width={vb_w}, height={vb_h}. "
            f"The viewBox must be square (e.g. '0 0 40 40') to ensure a 1:1 "
            "intrinsic aspect ratio without distortion at any rendered size."
        )

    def test_static_site_header_logo_has_equal_width_height_classes(self) -> None:
        """SiteHeader.tsx must apply equal Tailwind width and height to the LogoIcon.

        The logo is rendered as:
            <LogoIcon className="w-11 h-11" …>
        Equal w-X and h-X classes guarantee a 1:1 rendered aspect ratio at
        every breakpoint — the CSS does not allow asymmetric scaling.
        """
        tsx = _read_file(_SITE_HEADER_TSX)
        assert tsx, f"SiteHeader.tsx not found at {_SITE_HEADER_TSX}"

        import re

        # Find the LogoIcon element and its className prop
        logo_match = re.search(
            r"<LogoIcon[^>]*className=[\"']([^\"']*)[\"']",
            tsx,
            re.DOTALL,
        )
        assert logo_match, (
            "No LogoIcon element with a className prop found in SiteHeader.tsx. "
            "Ensure the logo icon is rendered with explicit size classes."
        )

        class_str = logo_match.group(1)
        tokens = class_str.split()

        # Collect w-* and h-* tokens (plain and responsive variants)
        w_tokens = [t for t in tokens if re.match(r"(sm:|md:|lg:|xl:)?w-\w+", t)]
        h_tokens = [t for t in tokens if re.match(r"(sm:|md:|lg:|xl:)?h-\w+", t)]

        assert w_tokens, (
            f"LogoIcon in SiteHeader.tsx has no width class (w-*) in className='{class_str}'. "
            "Add explicit width and height classes (e.g. w-11 h-11) to fix the aspect ratio."
        )
        assert h_tokens, (
            f"LogoIcon in SiteHeader.tsx has no height class (h-*) in className='{class_str}'. "
            "Add explicit width and height classes (e.g. w-11 h-11) to fix the aspect ratio."
        )

        # Strip responsive prefix for value comparison
        def _strip_prefix(tok: str) -> str:
            return tok.split(":")[-1]

        plain_w = {_strip_prefix(t) for t in w_tokens}
        plain_h = {_strip_prefix(t) for t in h_tokens}

        # e.g. plain_w={'w-11'}, plain_h={'h-11'}; sizes must match
        w_sizes = {t[2:] for t in plain_w}   # e.g. {'11'}
        h_sizes = {t[2:] for t in plain_h}   # e.g. {'11'}

        assert w_sizes == h_sizes, (
            f"LogoIcon width and height classes differ in SiteHeader.tsx: "
            f"width classes={plain_w}, height classes={plain_h}. "
            "They must be equal (e.g. both w-11 h-11) to preserve the 1:1 aspect ratio."
        )

    def test_static_logo_link_has_shrink_0(self) -> None:
        """The logo <Link> in SiteHeader.tsx must have shrink-0.

        Without shrink-0, the flex container can compress the logo at narrow
        widths, causing the rendered height/width to diverge and distorting
        the aspect ratio.
        """
        tsx = _read_file(_SITE_HEADER_TSX)
        assert tsx, f"SiteHeader.tsx not found at {_SITE_HEADER_TSX}"

        assert "shrink-0" in tsx, (
            "Expected 'shrink-0' on the logo <Link> in SiteHeader.tsx. "
            "Without shrink-0 the flex container may compress the logo at "
            "narrow viewports, distorting the aspect ratio."
        )

    # ──────────────────────────────────────────────────────────────────────
    # Live Playwright (skipped when app unreachable)
    # ──────────────────────────────────────────────────────────────────────

    def test_live_logo_aspect_ratio_desktop(
        self, config: WebConfig, playwright_browser: Browser
    ) -> None:
        """Desktop (1280px): logo bounding box must be square (aspect ratio ≈ 1:1)."""
        self._assert_logo_aspect_ratio(config, playwright_browser, label="desktop", width=1280)

    def test_live_logo_aspect_ratio_tablet(
        self, config: WebConfig, playwright_browser: Browser
    ) -> None:
        """Tablet (768px): logo bounding box must be square (aspect ratio ≈ 1:1)."""
        self._assert_logo_aspect_ratio(config, playwright_browser, label="tablet", width=768)

    def test_live_logo_aspect_ratio_mobile(
        self, config: WebConfig, playwright_browser: Browser
    ) -> None:
        """Mobile (375px): logo bounding box must be square (aspect ratio ≈ 1:1)."""
        self._assert_logo_aspect_ratio(config, playwright_browser, label="mobile", width=375)

    def test_live_logo_visible_at_all_breakpoints(
        self, config: WebConfig, playwright_browser: Browser
    ) -> None:
        """The logo must be visible in the header at every breakpoint.

        Visual clarity requires the logo to be rendered and not hidden, clipped,
        or zero-sized at any of the target viewport widths.
        """
        if not _is_url_reachable(config.base_url):
            pytest.skip(f"Deployed app unreachable ({config.base_url})")

        for label, width in _BREAKPOINTS:
            page = playwright_browser.new_page(
                viewport={"width": width, "height": _VIEWPORT_HEIGHT}
            )
            try:
                page.goto(
                    config.home_url(),
                    timeout=_PAGE_LOAD_TIMEOUT,
                    wait_until="domcontentloaded",
                )
                page.wait_for_selector("header", timeout=10_000)

                site_header = SiteHeader(page)
                assert site_header.logo_is_visible(), (
                    f"Logo link is not visible in the header at {label} viewport "
                    f"(width={width}px). The logo must be rendered and visible at "
                    "all breakpoints."
                )

                # Also verify the SVG inside the logo is rendered
                svg_locator = page.locator(_LOGO_SVG_SELECTOR)
                assert svg_locator.count() > 0, (
                    f"LogoIcon SVG not found inside the header logo link at "
                    f"{label} (width={width}px). Selector: {_LOGO_SVG_SELECTOR!r}."
                )

                box = svg_locator.first.bounding_box()
                assert box is not None, (
                    f"LogoIcon SVG has no bounding box at {label} (width={width}px) — "
                    "it may be hidden or have zero dimensions."
                )
                assert box["width"] > 0 and box["height"] > 0, (
                    f"LogoIcon SVG has zero dimensions at {label} (width={width}px): "
                    f"width={box['width']}px, height={box['height']}px. "
                    "The logo must be rendered with positive dimensions."
                )
            finally:
                page.close()

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _assert_logo_aspect_ratio(
        self,
        config: WebConfig,
        browser: Browser,
        label: str,
        width: int,
    ) -> None:
        """Navigate to the app at *width* px and assert the logo SVG aspect ratio ≈ 1:1."""
        if not _is_url_reachable(config.base_url):
            pytest.skip(f"Deployed app unreachable ({config.base_url})")

        page = browser.new_page(
            viewport={"width": width, "height": _VIEWPORT_HEIGHT}
        )
        try:
            page.goto(
                config.home_url(),
                timeout=_PAGE_LOAD_TIMEOUT,
                wait_until="domcontentloaded",
            )
            page.wait_for_selector("header", timeout=10_000)

            svg_locator = page.locator(_LOGO_SVG_SELECTOR)
            assert svg_locator.count() > 0, (
                f"LogoIcon SVG not found in header at {label} (width={width}px). "
                f"Selector: {_LOGO_SVG_SELECTOR!r}. "
                "The SiteHeader must render the LogoIcon inside the logo link."
            )

            box = svg_locator.first.bounding_box()
            assert box is not None, (
                f"LogoIcon SVG bounding box is null at {label} (width={width}px). "
                "The element may be hidden or detached."
            )

            svg_w = box["width"]
            svg_h = box["height"]

            assert svg_w > 0 and svg_h > 0, (
                f"LogoIcon has zero/negative dimensions at {label} (width={width}px): "
                f"rendered width={svg_w}px, height={svg_h}px."
            )

            aspect_ratio = svg_w / svg_h
            assert abs(aspect_ratio - 1.0) <= _ASPECT_RATIO_TOLERANCE, (
                f"LogoIcon aspect ratio is {aspect_ratio:.4f} at {label} viewport "
                f"(width={width}px) — expected 1.0 ± {_ASPECT_RATIO_TOLERANCE}. "
                f"Rendered dimensions: width={svg_w:.1f}px, height={svg_h:.1f}px. "
                "The logo is distorted (stretching or squashing). "
                "Ensure LogoIcon in SiteHeader.tsx uses equal width and height "
                "classes (e.g. w-11 h-11) and the logo link has shrink-0 so the "
                "flex container does not compress the icon at narrow viewports."
            )
        finally:
            page.close()
