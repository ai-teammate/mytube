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
- SiteHeaderThemePage from
  testing/components/pages/site_header/site_header_theme_page.py encapsulates
  all theme-toggle interactions as a standalone page object.
- Tests use only semantic methods from the component; no raw Playwright APIs in
  the test body.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.site_header.site_header_theme_page import SiteHeaderThemePage

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
