"""
MYTUBE-503: SiteHeader utility area — theme toggle button dimensions and icons.

Objective
---------
Ensure the theme toggle button matches the specific circular dimensions and
utilises the correct icons for each theme state.

Steps
-----
1. Navigate to the homepage and locate the theme toggle button (.btn.theme) in
   the header utility area.
2. Inspect the button's dimensions and shape (must be 40×40 px, circular).
3. Toggle the theme and observe the icon change:
   - Light mode → MoonIcon is displayed (indicates "switch to dark").
   - Dark mode  → SunIcon is displayed (indicates "switch to light").

Expected Result
---------------
* The button is a circle with dimensions 40×40 pixels.
* In light mode the button contains a MoonIcon (crescent moon SVG path).
* In dark mode  the button contains a SunIcon  (circle + rays SVG).
* After toggling, the icon swaps accordingly.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- SiteHeader from testing/components/pages/site_header/site_header.py is
  extended here with theme-toggle-specific helpers via a thin subclass so the
  original component is not modified.
- Tests use only semantic methods from the component; no raw Playwright APIs in
  the test body.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms

# Tailwind w-10 / h-10 = 2.5 rem.  At the default 16 px base that is 40 px.
_EXPECTED_WIDTH_PX  = 40
_EXPECTED_HEIGHT_PX = 40

# Tolerance for sub-pixel rounding (getBoundingClientRect can return .5 values)
_DIMENSION_TOLERANCE = 1.0


# ---------------------------------------------------------------------------
# Page-Object: SiteHeaderThemePage
# ---------------------------------------------------------------------------

class SiteHeaderThemePage:
    """Thin page-object layer for the theme toggle section of SiteHeader.

    Wraps all selectors and JavaScript evaluation so test assertions remain
    framework-agnostic and readable.
    """

    # The theme toggle button is the only <button> inside the header's
    # utility area that carries a `aria-label` starting with "Switch to".
    _TOGGLE_BTN = "header button[aria-label^='Switch to']"

    def __init__(self, page: Page) -> None:
        self._page = page

    def navigate(self, base_url: str) -> None:
        url = f"{base_url.rstrip('/')}/"
        self._page.goto(url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        self._page.wait_for_selector(self._TOGGLE_BTN, timeout=_PAGE_LOAD_TIMEOUT)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def button_bounding_box(self) -> dict:
        """Return {width, height} of the toggle button via getBoundingClientRect."""
        return self._page.evaluate(
            """() => {
                const btn = document.querySelector("header button[aria-label^='Switch to']");
                if (!btn) return null;
                const r = btn.getBoundingClientRect();
                return { width: r.width, height: r.height };
            }"""
        )

    def button_is_circular(self) -> bool:
        """Return True when computed border-radius makes the button a circle."""
        return self._page.evaluate(
            """() => {
                const btn = document.querySelector("header button[aria-label^='Switch to']");
                if (!btn) return false;
                const cs = window.getComputedStyle(btn);
                // rounded-full produces border-radius: 9999px (or 50%).
                // A circle requires all four corners to be >= half the element size.
                const radius = parseFloat(cs.borderTopLeftRadius);
                const size   = parseFloat(cs.width);
                return radius >= size / 2;
            }"""
        )

    # ------------------------------------------------------------------
    # Icon presence helpers
    # ------------------------------------------------------------------

    def _svg_inside_button(self) -> str | None:
        """Return the innerHTML of the <svg> inside the toggle button."""
        return self._page.evaluate(
            """() => {
                const btn = document.querySelector("header button[aria-label^='Switch to']");
                if (!btn) return null;
                const svg = btn.querySelector('svg');
                return svg ? svg.innerHTML : null;
            }"""
        )

    def current_theme(self) -> str:
        """Return the value of body[data-theme], defaulting to 'light'."""
        return self._page.evaluate(
            "() => document.body.getAttribute('data-theme') || 'light'"
        )

    def has_moon_icon(self) -> bool:
        """Return True when the MoonIcon crescent-path SVG is inside the button."""
        inner = self._svg_inside_button()
        if not inner:
            return False
        # MoonIcon uses a single <path d="M21 12.79…">
        return "M21 12.79" in inner

    def has_sun_icon(self) -> bool:
        """Return True when the SunIcon (central circle + rays) is inside the button."""
        inner = self._svg_inside_button()
        if not inner:
            return False
        # SunIcon uses <circle cx="12" cy="12" r="4" /> plus line rays.
        return 'cx="12"' in inner and 'cy="12"' in inner

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------

    def toggle_theme(self) -> None:
        """Click the theme toggle button."""
        self._page.locator(self._TOGGLE_BTN).click()
        # Wait for React re-render (icon swap is synchronous but we give the
        # browser one animation frame to apply the DOM update).
        self._page.wait_for_timeout(300)

    def force_light_theme(self) -> None:
        """Set localStorage + body attribute to light and reload if needed."""
        self._page.evaluate(
            """() => {
                localStorage.setItem('theme', 'light');
                document.body.setAttribute('data-theme', 'light');
            }"""
        )
        self._page.wait_for_timeout(200)

    def force_dark_theme(self) -> None:
        """Set localStorage + body attribute to dark and reload if needed."""
        self._page.evaluate(
            """() => {
                localStorage.setItem('theme', 'dark');
                document.body.setAttribute('data-theme', 'dark');
            }"""
        )
        self._page.wait_for_timeout(200)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        yield page
        browser.close()


@pytest.fixture(scope="module")
def header_page(browser_page: Page, config: WebConfig) -> SiteHeaderThemePage:
    theme_page = SiteHeaderThemePage(browser_page)
    theme_page.navigate(config.base_url)
    return theme_page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestThemeToggleButtonDimensions:
    """Verify the theme toggle button is 40×40 px and circular."""

    def test_button_width_is_40px(self, header_page: SiteHeaderThemePage) -> None:
        bb = header_page.button_bounding_box()
        assert bb is not None, "Theme toggle button not found in the header."
        assert abs(bb["width"] - _EXPECTED_WIDTH_PX) <= _DIMENSION_TOLERANCE, (
            f"Expected button width {_EXPECTED_WIDTH_PX}px, got {bb['width']}px."
        )

    def test_button_height_is_40px(self, header_page: SiteHeaderThemePage) -> None:
        bb = header_page.button_bounding_box()
        assert bb is not None, "Theme toggle button not found in the header."
        assert abs(bb["height"] - _EXPECTED_HEIGHT_PX) <= _DIMENSION_TOLERANCE, (
            f"Expected button height {_EXPECTED_HEIGHT_PX}px, got {bb['height']}px."
        )

    def test_button_is_circular(self, header_page: SiteHeaderThemePage) -> None:
        assert header_page.button_is_circular(), (
            "Theme toggle button does not have a fully-rounded (circular) shape."
        )


class TestThemeToggleIcons:
    """Verify MoonIcon ↔ SunIcon swap when the theme is toggled."""

    def test_light_mode_shows_moon_icon(self, header_page: SiteHeaderThemePage) -> None:
        """In light mode the MoonIcon (switch-to-dark indicator) must be present."""
        header_page.force_light_theme()
        # Reload so ThemeProvider picks up the localStorage value.
        header_page._page.reload(wait_until="networkidle")
        header_page._page.wait_for_selector(
            "header button[aria-label^='Switch to']",
            timeout=_PAGE_LOAD_TIMEOUT,
        )
        assert header_page.current_theme() == "light", (
            "Expected body[data-theme]='light' after forcing light mode."
        )
        assert header_page.has_moon_icon(), (
            "In light mode the theme toggle button should display the MoonIcon "
            "(crescent moon path 'M21 12.79…') but it was not found."
        )

    def test_dark_mode_shows_sun_icon(self, header_page: SiteHeaderThemePage) -> None:
        """In dark mode the SunIcon (switch-to-light indicator) must be present."""
        header_page.force_dark_theme()
        # Reload so ThemeProvider picks up the localStorage value.
        header_page._page.reload(wait_until="networkidle")
        header_page._page.wait_for_selector(
            "header button[aria-label^='Switch to']",
            timeout=_PAGE_LOAD_TIMEOUT,
        )
        assert header_page.current_theme() == "dark", (
            "Expected body[data-theme]='dark' after forcing dark mode."
        )
        assert header_page.has_sun_icon(), (
            "In dark mode the theme toggle button should display the SunIcon "
            "(SVG circle cx=12 cy=12 + rays) but it was not found."
        )

    def test_toggle_from_light_swaps_to_sun_icon(
        self, header_page: SiteHeaderThemePage
    ) -> None:
        """Clicking the toggle in light mode must switch to dark and show SunIcon."""
        # Start from a known light state.
        header_page.force_light_theme()
        header_page._page.reload(wait_until="networkidle")
        header_page._page.wait_for_selector(
            "header button[aria-label^='Switch to']",
            timeout=_PAGE_LOAD_TIMEOUT,
        )
        assert header_page.has_moon_icon(), (
            "Pre-condition failed: expected MoonIcon before toggle."
        )
        header_page.toggle_theme()
        assert header_page.has_sun_icon(), (
            "After toggling from light mode, expected SunIcon but it was not found."
        )

    def test_toggle_from_dark_swaps_to_moon_icon(
        self, header_page: SiteHeaderThemePage
    ) -> None:
        """Clicking the toggle in dark mode must switch to light and show MoonIcon."""
        # Start from a known dark state.
        header_page.force_dark_theme()
        header_page._page.reload(wait_until="networkidle")
        header_page._page.wait_for_selector(
            "header button[aria-label^='Switch to']",
            timeout=_PAGE_LOAD_TIMEOUT,
        )
        assert header_page.has_sun_icon(), (
            "Pre-condition failed: expected SunIcon before toggle."
        )
        header_page.toggle_theme()
        assert header_page.has_moon_icon(), (
            "After toggling from dark mode, expected MoonIcon but it was not found."
        )
