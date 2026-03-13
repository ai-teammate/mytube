"""
MYTUBE-558: Resize viewport to mobile width — header elements are aligned without overflow.

Objective
---------
Verify that the SiteHeader elements (logo, search, and utility area) do not overflow or stack
incorrectly on mobile viewports, resolving the regression fixed in MYTUBE-536.

Steps
-----
1. Open the application on the Homepage (AppShell page).
2. Set the browser viewport width to 375px (mobile).
3. Inspect the horizontal alignment of the logo and the utility area.
4. Check the page for any horizontal scrollbars caused by the header.

Expected Result
---------------
All header elements are properly contained within the viewport. No horizontal overflow occurs,
and elements are correctly aligned without overlapping or breaking the flex/grid layout structure.

Fix Context (MYTUBE-536)
------------------------
The mobile header overflow was caused by:
  - Excessive fixed padding/gap: ``px-10 py-4 gap-6 min-h-[88px]``
    → Fixed: ``px-4 sm:px-10 py-3 sm:py-4 gap-3 sm:gap-6 min-h-[56px] sm:min-h-[88px]``
  - Missing ``min-w-0`` on the search ``<form>`` and ``<input>``
    → Prevented flex items from shrinking below intrinsic width, causing overflow.

Architecture
------------
- Dual-mode: live Playwright tests against the deployed app + static source analysis.
- Uses WebConfig from testing/core/config/web_config.py.
- Uses SiteHeader page object from testing/components/pages/site_header/.
- Mobile viewport: 375×812 (iPhone SE/standard mobile size).
- No raw Playwright APIs in test body — helpers encapsulate selector logic.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.site_header.site_header import SiteHeader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Mobile viewport per test spec
_MOBILE_VIEWPORT = {"width": 375, "height": 812}

# SiteHeader source files for static analysis
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SITE_HEADER_TSX = _REPO_ROOT / "web" / "src" / "components" / "SiteHeader.tsx"

# Expected mobile-specific Tailwind classes (from MYTUBE-536 fix)
_EXPECTED_MOBILE_MIN_H = "min-h-[56px]"
_EXPECTED_MOBILE_PX = "px-4"
_EXPECTED_MOBILE_GAP = "gap-3"
_EXPECTED_MIN_W_0_FORM = "min-w-0"       # on the search <form>
_EXPECTED_MIN_W_0_INPUT = "min-w-0"      # on the search <input>


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _should_use_live_mode() -> bool:
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


def _page_has_horizontal_scroll(page: Page) -> bool:
    """Return True if the document has a horizontal scrollbar."""
    return page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )


def _header_bounding_box(page: Page) -> dict:
    """Return the bounding box of the <header> element."""
    return page.evaluate(
        """() => {
            const header = document.querySelector('header');
            if (!header) return null;
            const rect = header.getBoundingClientRect();
            return { x: rect.x, y: rect.y, width: rect.width, height: rect.height };
        }"""
    )


def _header_overflow_info(page: Page) -> dict:
    """Return overflow dimensions for the header element."""
    return page.evaluate(
        """() => {
            const header = document.querySelector('header');
            if (!header) return null;
            return {
                scrollWidth: header.scrollWidth,
                clientWidth: header.clientWidth,
                offsetWidth: header.offsetWidth,
            };
        }"""
    )


def _element_right_edge(page: Page, selector: str) -> float | None:
    """Return the right edge (x + width) of the first matching element."""
    return page.evaluate(
        f"""(sel) => {{
            const el = document.querySelector(sel);
            if (!el) return null;
            const rect = el.getBoundingClientRect();
            return rect.right;
        }}""",
        selector,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def mobile_page(config: WebConfig):
    """Launch Chromium at 375px mobile viewport and load the homepage."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        page = browser.new_page(viewport=_MOBILE_VIEWPORT)
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Live-mode tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _should_use_live_mode(),
    reason="Live mode requires APP_URL / WEB_BASE_URL",
)
class TestMobileHeaderAlignmentLive:
    """MYTUBE-558 — Live Playwright tests at 375px mobile viewport."""

    def test_no_horizontal_scroll_on_homepage(self, mobile_page: Page) -> None:
        """The homepage must not have a horizontal scrollbar at 375px viewport."""
        assert not _page_has_horizontal_scroll(mobile_page), (
            f"Horizontal overflow detected on homepage at 375px viewport. "
            f"URL: {mobile_page.url}"
        )

    def test_header_fits_within_viewport_width(self, mobile_page: Page) -> None:
        """The <header> element width must not exceed the 375px viewport."""
        viewport_width = _MOBILE_VIEWPORT["width"]
        bbox = _header_bounding_box(mobile_page)
        assert bbox is not None, (
            "Could not find <header> element on the page."
        )
        assert bbox["width"] <= viewport_width + 1, (  # +1 for sub-pixel rounding
            f"<header> width {bbox['width']:.1f}px exceeds mobile viewport "
            f"({viewport_width}px). Header is overflowing. URL: {mobile_page.url}"
        )

    def test_header_scroll_width_does_not_overflow(self, mobile_page: Page) -> None:
        """The <header> scrollWidth must equal its clientWidth (no internal overflow)."""
        overflow = _header_overflow_info(mobile_page)
        assert overflow is not None, "Could not find <header> element on the page."
        assert overflow["scrollWidth"] <= overflow["clientWidth"] + 1, (
            f"<header> scrollWidth ({overflow['scrollWidth']}px) > "
            f"clientWidth ({overflow['clientWidth']}px). "
            f"A child element inside the header is overflowing its container. "
            f"URL: {mobile_page.url}"
        )

    def test_logo_is_visible_on_mobile(self, mobile_page: Page) -> None:
        """The logo link must be visible on the mobile viewport."""
        header = SiteHeader(mobile_page)
        assert header.logo_is_visible(), (
            f"Logo link is not visible at 375px viewport. URL: {mobile_page.url}"
        )

    def test_logo_right_edge_within_viewport(self, mobile_page: Page) -> None:
        """The logo element right edge must not exceed the viewport width."""
        viewport_width = _MOBILE_VIEWPORT["width"]
        # Use class-based selector: logo link has 'shrink-0' (Next.js transforms
        # href="/" to the base path, so href value varies by deployment).
        right_edge = _element_right_edge(mobile_page, "header a.shrink-0")
        assert right_edge is not None, (
            "Could not find the logo link element (header a.shrink-0) inside the header."
        )
        assert right_edge <= viewport_width + 1, (
            f"Logo right edge ({right_edge:.1f}px) exceeds mobile viewport "
            f"({viewport_width}px). URL: {mobile_page.url}"
        )

    def test_search_input_is_visible_on_mobile(self, mobile_page: Page) -> None:
        """The search input must be visible and accessible on the mobile viewport."""
        header = SiteHeader(mobile_page)
        assert header.search_input_locator().is_visible(), (
            f"Search input is not visible on 375px viewport. "
            f"The search form should be present and not overflowing. URL: {mobile_page.url}"
        )

    def test_search_form_fits_within_header(self, mobile_page: Page) -> None:
        """The search form right edge must not exceed the viewport width."""
        viewport_width = _MOBILE_VIEWPORT["width"]
        right_edge = _element_right_edge(mobile_page, "header form[role='search']")
        if right_edge is None:
            # Fallback: try without role
            right_edge = _element_right_edge(mobile_page, "header form")
        assert right_edge is not None, (
            "Could not find the search <form> element inside the header."
        )
        assert right_edge <= viewport_width + 1, (
            f"Search form right edge ({right_edge:.1f}px) exceeds mobile viewport "
            f"({viewport_width}px). min-w-0 may be missing on the form. "
            f"URL: {mobile_page.url}"
        )

    def test_utility_area_fits_within_viewport(self, mobile_page: Page) -> None:
        """The utility area (ml-auto div with theme/auth) right edge must not overflow."""
        viewport_width = _MOBILE_VIEWPORT["width"]
        # The utility area is the div with ml-auto inside the header
        right_edge = _element_right_edge(
            mobile_page, "header [aria-label='User navigation']"
        )
        if right_edge is None:
            # Fallback: look for the sign-in link or auth nav container
            right_edge = _element_right_edge(mobile_page, "header nav[aria-label='User navigation']")
        assert right_edge is not None, (
            "Could not locate the utility/auth area (header [aria-label='User navigation']). "
            "Verify the selector matches the rendered DOM."
        )
        assert right_edge <= viewport_width + 1, (
            f"Utility/auth area right edge ({right_edge:.1f}px) exceeds mobile "
            f"viewport ({viewport_width}px). URL: {mobile_page.url}"
        )


# ---------------------------------------------------------------------------
# Static-analysis tests (always run)
# ---------------------------------------------------------------------------


class TestMobileHeaderAlignmentStatic:
    """MYTUBE-558 — Static source analysis of SiteHeader.tsx for MYTUBE-536 fix."""

    @pytest.fixture(scope="class")
    def tsx_source(self) -> str:
        assert _SITE_HEADER_TSX.exists(), (
            f"SiteHeader.tsx not found at {_SITE_HEADER_TSX}."
        )
        return _SITE_HEADER_TSX.read_text(encoding="utf-8")

    def test_header_has_mobile_min_height_56px(self, tsx_source: str) -> None:
        """<header> must have min-h-[56px] (mobile) and sm:min-h-[88px] (desktop)."""
        assert _EXPECTED_MOBILE_MIN_H in tsx_source, (
            f"Expected '{_EXPECTED_MOBILE_MIN_H}' not found in SiteHeader.tsx. "
            f"The <header> must use 'min-h-[56px] sm:min-h-[88px]' for responsive "
            f"height (MYTUBE-536 fix)."
        )

    def test_header_has_mobile_padding_px4(self, tsx_source: str) -> None:
        """<header> must use px-4 (mobile) instead of the old fixed px-10."""
        assert _EXPECTED_MOBILE_PX in tsx_source, (
            f"Expected '{_EXPECTED_MOBILE_PX}' not found in SiteHeader.tsx. "
            f"The <header> must use 'px-4 sm:px-10' for responsive padding "
            f"(MYTUBE-536 fix). Old 'px-10' caused overflow on mobile viewports."
        )

    def test_header_has_mobile_gap_3(self, tsx_source: str) -> None:
        """<header> must use gap-3 (mobile) instead of the old fixed gap-6."""
        assert _EXPECTED_MOBILE_GAP in tsx_source, (
            f"Expected '{_EXPECTED_MOBILE_GAP}' not found in SiteHeader.tsx. "
            f"The <header> must use 'gap-3 sm:gap-6' for responsive gap "
            f"(MYTUBE-536 fix). Old 'gap-6' caused flex items to overflow on mobile."
        )

    def test_search_form_has_min_w_0(self, tsx_source: str) -> None:
        """The search <form> must have min-w-0 to allow shrinking in flex layout."""
        # Look for min-w-0 in the form className
        # The form tag is identifiable by role="search"
        import re
        form_match = re.search(
            r'<form[^>]*role="search"[^>]*className="([^"]*)"',
            tsx_source,
        )
        if form_match:
            form_classes = form_match.group(1)
            assert _EXPECTED_MIN_W_0_FORM in form_classes, (
                f"Search <form> className does not include 'min-w-0'. "
                f"Found classes: '{form_classes}'. "
                f"'min-w-0' is required to allow the form to shrink in the flex "
                f"header layout on mobile (MYTUBE-536 fix)."
            )
        else:
            # Fallback: just check the file contains min-w-0
            assert _EXPECTED_MIN_W_0_FORM in tsx_source, (
                f"'min-w-0' not found anywhere in SiteHeader.tsx. "
                f"The search form or input must have 'min-w-0' to prevent "
                f"overflow on mobile viewports (MYTUBE-536 fix)."
            )

    def test_search_input_has_min_w_0(self, tsx_source: str) -> None:
        """The search <input> must have min-w-0 to allow shrinking below intrinsic width."""
        import re
        input_match = re.search(
            r'<input[^>]*type="search"[^>]*className="([^"]*)"',
            tsx_source,
        )
        if not input_match:
            # JSX may have attributes on multiple lines — try multiline
            input_match = re.search(
                r'type="search".*?className="([^"]*)"',
                tsx_source,
                re.DOTALL,
            )
        if input_match:
            input_classes = input_match.group(1)
            assert _EXPECTED_MIN_W_0_INPUT in input_classes, (
                f"Search <input type='search'> className does not include 'min-w-0'. "
                f"Found classes: '{input_classes}'. "
                f"'min-w-0' is required to prevent the input from overflowing "
                f"the flex container on mobile (MYTUBE-536 fix)."
            )
        else:
            # Final fallback: count occurrences of min-w-0 — expect at least 2
            count = tsx_source.count("min-w-0")
            assert count >= 2, (
                f"Expected at least 2 occurrences of 'min-w-0' in SiteHeader.tsx "
                f"(one for the form, one for the input), found {count}. "
                f"Both form and input need 'min-w-0' to prevent overflow on mobile "
                f"(MYTUBE-536 fix)."
            )

    def test_responsive_sm_prefix_on_padding(self, tsx_source: str) -> None:
        """The header must use sm:px-10 so desktop padding is preserved."""
        assert "sm:px-10" in tsx_source, (
            "Expected 'sm:px-10' not found in SiteHeader.tsx. "
            "The responsive breakpoint prefix 'sm:' must be used for desktop "
            "padding so mobile gets the narrower 'px-4' value."
        )

    def test_responsive_sm_prefix_on_gap(self, tsx_source: str) -> None:
        """The header must use sm:gap-6 so desktop gap is preserved."""
        assert "sm:gap-6" in tsx_source, (
            "Expected 'sm:gap-6' not found in SiteHeader.tsx. "
            "The responsive breakpoint prefix 'sm:' must be used for desktop "
            "gap so mobile gets the narrower 'gap-3' value."
        )
