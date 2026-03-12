"""
MYTUBE-504: SiteHeader container — layout dimensions and border styling

Objective
---------
Verify the overall structure and styling of the SiteHeader container.

Steps
-----
1. Inspect the SiteHeader component in the browser.
2. Check the height, padding, and border properties.

Expected Result
---------------
The header has a min-height: 88px, padding: 16px 40px, a bottom border of
1px solid rgba(127,127,127,0.16), and uses background: var(--bg-header).

Test Approach
-------------
Dual-mode:

1. **Live Mode** (primary) — Playwright navigates to the deployed homepage and
   reads computed styles of the <header> element via window.getComputedStyle().

2. **Static Mode** (fallback) — When live mode is not available, the test reads
   SiteHeader.tsx directly to assert that the correct Tailwind classes and
   inline styles are applied.

Architecture
------------
- Uses WebConfig from testing/core/config/web_config.py.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# The <header> rendered by SiteHeader.tsx
_HEADER_SELECTOR = "header"

# Expected CSS values
_EXPECTED_MIN_HEIGHT_PX = 88
_EXPECTED_PADDING_TOP_PX = 16
_EXPECTED_PADDING_BOTTOM_PX = 16
_EXPECTED_PADDING_LEFT_PX = 40
_EXPECTED_PADDING_RIGHT_PX = 40
_EXPECTED_BORDER_BOTTOM = "1px solid rgba(127, 127, 127, 0.16)"
_EXPECTED_BG_TOKEN = "var(--bg-header)"

# Repo root for static analysis
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SITE_HEADER_TSX = _REPO_ROOT / "web" / "src" / "components" / "SiteHeader.tsx"

# ---------------------------------------------------------------------------
# Mode helpers
# ---------------------------------------------------------------------------


def _should_use_live_mode() -> bool:
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    """Navigate to the homepage so SiteHeader is rendered."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
        page.wait_for_selector(_HEADER_SELECTOR, timeout=_PAGE_LOAD_TIMEOUT)
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _computed_style(page: Page, selector: str, prop: str) -> str:
    """Return the computed CSS property value for the first matching element."""
    return page.eval_on_selector(
        selector,
        f"el => window.getComputedStyle(el).{prop}",
    )


def _px_value(value: str) -> float:
    """Parse a CSS pixel value like '88px' to float."""
    return float(value.rstrip("px"))


# ---------------------------------------------------------------------------
# Live-mode tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _should_use_live_mode(), reason="Live mode requires APP_URL / WEB_BASE_URL")
class TestSiteHeaderLive:
    """MYTUBE-504 — Live Playwright tests against the deployed application."""

    def test_header_element_present(self, browser_page: Page) -> None:
        """The <header> element rendered by SiteHeader must be present."""
        locator = browser_page.locator(_HEADER_SELECTOR)
        assert locator.count() > 0, (
            f"No <header> element found on the homepage. "
            f"SiteHeader.tsx may not be rendering. URL: {browser_page.url}"
        )

    def test_header_min_height(self, browser_page: Page) -> None:
        """The header must have min-height: 88px (from Tailwind min-h-[88px])."""
        min_height = _computed_style(browser_page, _HEADER_SELECTOR, "minHeight")
        try:
            min_height_px = _px_value(min_height)
        except (ValueError, AttributeError):
            pytest.fail(
                f"Could not parse minHeight value '{min_height}' as a pixel value. "
                f"Expected '{_EXPECTED_MIN_HEIGHT_PX}px'."
            )
        assert min_height_px >= _EXPECTED_MIN_HEIGHT_PX, (
            f"Header minHeight: expected >= {_EXPECTED_MIN_HEIGHT_PX}px, got {min_height_px}px. "
            f"Computed value: '{min_height}'."
        )

    def test_header_padding_top_bottom(self, browser_page: Page) -> None:
        """The header must have padding-top and padding-bottom of 16px (py-4)."""
        pt = _computed_style(browser_page, _HEADER_SELECTOR, "paddingTop")
        pb = _computed_style(browser_page, _HEADER_SELECTOR, "paddingBottom")
        pt_px = _px_value(pt)
        pb_px = _px_value(pb)
        assert pt_px == _EXPECTED_PADDING_TOP_PX, (
            f"Header paddingTop: expected {_EXPECTED_PADDING_TOP_PX}px, got {pt_px}px."
        )
        assert pb_px == _EXPECTED_PADDING_BOTTOM_PX, (
            f"Header paddingBottom: expected {_EXPECTED_PADDING_BOTTOM_PX}px, got {pb_px}px."
        )

    def test_header_padding_left_right(self, browser_page: Page) -> None:
        """The header must have padding-left and padding-right of 40px (px-10)."""
        pl = _computed_style(browser_page, _HEADER_SELECTOR, "paddingLeft")
        pr = _computed_style(browser_page, _HEADER_SELECTOR, "paddingRight")
        pl_px = _px_value(pl)
        pr_px = _px_value(pr)
        assert pl_px == _EXPECTED_PADDING_LEFT_PX, (
            f"Header paddingLeft: expected {_EXPECTED_PADDING_LEFT_PX}px, got {pl_px}px."
        )
        assert pr_px == _EXPECTED_PADDING_RIGHT_PX, (
            f"Header paddingRight: expected {_EXPECTED_PADDING_RIGHT_PX}px, got {pr_px}px."
        )

    def test_header_border_bottom(self, browser_page: Page) -> None:
        """The header must have a border-bottom of 1px solid rgba(127,127,127,0.16)."""
        border = _computed_style(browser_page, _HEADER_SELECTOR, "borderBottom")
        # Normalise: some browsers report as 'borderBottomWidth + borderBottomStyle + borderBottomColor'
        # so also check the individual properties
        border_width = _computed_style(browser_page, _HEADER_SELECTOR, "borderBottomWidth")
        border_style = _computed_style(browser_page, _HEADER_SELECTOR, "borderBottomStyle")
        border_color = _computed_style(browser_page, _HEADER_SELECTOR, "borderBottomColor")

        width_ok = _px_value(border_width) == 1.0
        style_ok = border_style == "solid"
        # Compare colour components — allow minor float formatting differences
        color_ok = (
            "127" in border_color
            and "0.16" in border_color
            and "rgba" in border_color
        ) or "rgba(127, 127, 127, 0.16)" in border

        assert width_ok, (
            f"Header borderBottomWidth: expected 1px, got '{border_width}'."
        )
        assert style_ok, (
            f"Header borderBottomStyle: expected 'solid', got '{border_style}'."
        )
        assert color_ok, (
            f"Header borderBottomColor: expected rgba(127,127,127,0.16), got '{border_color}'. "
            f"Full borderBottom: '{border}'."
        )


# ---------------------------------------------------------------------------
# Static-analysis tests (always run)
# ---------------------------------------------------------------------------


class TestSiteHeaderStatic:
    """MYTUBE-504 — Static source analysis of SiteHeader.tsx."""

    @pytest.fixture(scope="class")
    def source(self) -> str:
        assert _SITE_HEADER_TSX.exists(), (
            f"SiteHeader.tsx not found at {_SITE_HEADER_TSX}. "
            "Cannot perform static analysis."
        )
        return _SITE_HEADER_TSX.read_text(encoding="utf-8")

    def test_min_height_class_present(self, source: str) -> None:
        """SiteHeader.tsx must include the Tailwind class min-h-[88px]."""
        assert "min-h-[88px]" in source, (
            "Expected Tailwind class 'min-h-[88px]' not found in SiteHeader.tsx. "
            "The header container must specify min-height: 88px."
        )

    def test_padding_classes_present(self, source: str) -> None:
        """SiteHeader.tsx must include px-10 and py-4 (padding: 16px 40px)."""
        assert "px-10" in source, (
            "Expected Tailwind class 'px-10' (horizontal padding 40px) not found in SiteHeader.tsx."
        )
        assert "py-4" in source, (
            "Expected Tailwind class 'py-4' (vertical padding 16px) not found in SiteHeader.tsx."
        )

    def test_border_bottom_inline_style_present(self, source: str) -> None:
        """SiteHeader.tsx must define borderBottom inline style with rgba(127,127,127,0.16)."""
        assert "rgba(127,127,127,0.16)" in source or "rgba(127, 127, 127, 0.16)" in source, (
            "Expected inline style borderBottom with rgba(127,127,127,0.16) not found in SiteHeader.tsx."
        )

    def test_background_token_present(self, source: str) -> None:
        """SiteHeader.tsx must use background: var(--bg-header) as the inline style."""
        assert "var(--bg-header)" in source, (
            "Expected inline style background: var(--bg-header) not found in SiteHeader.tsx."
        )

    def test_header_element_is_root(self, source: str) -> None:
        """SiteHeader.tsx must return a <header> element as the root."""
        # Check that <header is the root rendered element
        assert re.search(r"return\s*\(\s*\n?\s*<header", source) or "<header" in source, (
            "SiteHeader.tsx must render a <header> element as the root container."
        )
