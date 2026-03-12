"""
MYTUBE-466: Decorative background elements — icons are positioned and styled
with correct attributes.

Objective
---------
Ensure the four decorative SVG elements are rendered in the AppShell background
with correct visibility and positioning.

Steps
-----
1. Open the application and inspect the background of the .page-wrap.
2. Verify the presence of .decor.play, .decor.film, .decor.camera, and .decor.wave.
3. Check the CSS properties for these elements.

Expected Result
---------------
Four decorative elements are present with:
  - opacity: 0.12
  - pointer-events: none
  - z-index: 1
Each is positioned absolutely within the outer wrapper (.page-wrap).

Test Approach
-------------
Playwright navigates to the deployed homepage (a non-auth route so AppShell
renders) and reads the computed style of each .decor element via
window.getComputedStyle().

Architecture
------------
- Uses WebConfig from testing/core/config/web_config.py.
- Playwright sync API with pytest module-scoped fixtures.
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

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# The four decorative element selectors as rendered by AppShell.tsx
_DECOR_SELECTORS = {
    "play":   ".decor.play",
    "film":   ".decor.film",
    "camera": ".decor.camera",
    "wave":   ".decor.wave",
}

_EXPECTED_POSITION   = "absolute"
_EXPECTED_OPACITY    = "0.12"
_EXPECTED_POINTER    = "none"
_EXPECTED_Z_INDEX    = "1"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def home_page(config: WebConfig) -> Page:
    """Navigate to the homepage (non-auth route) so AppShell renders."""
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        page = browser.new_page()
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT,
                  wait_until="domcontentloaded")
        # Wait for the page-wrap to be present (confirms AppShell rendered)
        page.wait_for_selector(".page-wrap", timeout=_PAGE_LOAD_TIMEOUT)
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDecorElements:
    """MYTUBE-466 — Decorative background elements are present and styled."""

    @pytest.mark.parametrize("name,selector", list(_DECOR_SELECTORS.items()))
    def test_decor_element_present(self, home_page: Page, name: str, selector: str) -> None:
        """Each .decor element must be present in the DOM."""
        locator = home_page.locator(selector)
        count = locator.count()
        assert count >= 1, (
            f".decor.{name} ({selector}) not found in the DOM. "
            "AppShell may not be rendering decorative icons on this route."
        )

    @pytest.mark.parametrize("name,selector", list(_DECOR_SELECTORS.items()))
    def test_decor_position_absolute(self, home_page: Page, name: str, selector: str) -> None:
        """Each .decor element must be position: absolute."""
        position = _computed_style(home_page, selector, "position")
        assert position == _EXPECTED_POSITION, (
            f".decor.{name}: expected position='{_EXPECTED_POSITION}', got '{position}'"
        )

    @pytest.mark.parametrize("name,selector", list(_DECOR_SELECTORS.items()))
    def test_decor_opacity(self, home_page: Page, name: str, selector: str) -> None:
        """Each .decor element must have opacity: 0.12."""
        opacity = _computed_style(home_page, selector, "opacity")
        # Browsers may return "0.12" or a rounded variant; compare as float
        try:
            opacity_float = float(opacity)
        except ValueError:
            pytest.fail(
                f".decor.{name}: could not parse opacity value '{opacity}' as float"
            )
        assert abs(opacity_float - 0.12) < 0.001, (
            f".decor.{name}: expected opacity≈0.12, got {opacity_float}"
        )

    @pytest.mark.parametrize("name,selector", list(_DECOR_SELECTORS.items()))
    def test_decor_pointer_events_none(self, home_page: Page, name: str, selector: str) -> None:
        """Each .decor element must have pointer-events: none."""
        pointer = _computed_style(home_page, selector, "pointerEvents")
        assert pointer == _EXPECTED_POINTER, (
            f".decor.{name}: expected pointer-events='{_EXPECTED_POINTER}', got '{pointer}'"
        )

    @pytest.mark.parametrize("name,selector", list(_DECOR_SELECTORS.items()))
    def test_decor_z_index(self, home_page: Page, name: str, selector: str) -> None:
        """Each .decor element must have z-index: 1."""
        z_index = _computed_style(home_page, selector, "zIndex")
        assert z_index == _EXPECTED_Z_INDEX, (
            f".decor.{name}: expected z-index='{_EXPECTED_Z_INDEX}', got '{z_index}'"
        )
