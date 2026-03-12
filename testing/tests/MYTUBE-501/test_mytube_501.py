"""
MYTUBE-501: SiteHeader search input — pill shape and focus ring styling.

Objective
---------
Verify the search input styling is updated to match the new template design:
  - The input field has a pill shape.
  - Upon focus, a ring appears with a purple accent color.

Steps
-----
1. Navigate to the homepage (SiteHeader is present on every page).
2. Locate the search form in the SiteHeader (input[type="search"] inside <header>).
3. Inspect the shape of the input field — border-radius on the left side must be
   fully rounded (Tailwind rounded-l-full → 9999px).
4. Click into the input to trigger the focus state.
5. Inspect the computed border color and verify it is the purple --accent-logo value.

Expected Result
---------------
- Input has fully-rounded left border-radius (pill shape: ≥ 9999 px for TL/BL corners).
- After focus, border color resolves to the purple accent (#6d40cb light / #9370db dark).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- SiteHeader page object from testing/components/pages/site_header/site_header.py
  exposes search_input_locator(); all locator access is encapsulated there.
- Tests use computed CSS values obtained via element.evaluate() to avoid
  Tailwind class-name brittleness.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.site_header.site_header import SiteHeader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Purple accent shades used by --accent-logo (light & dark modes).
# We check that the computed border color matches one of these.
_PURPLE_ACCENT_HEX = {"#6d40cb", "#9370db"}

# Minimum border-radius (px) that qualifies as "pill shaped" for left corners.
# Tailwind's rounded-l-full maps to 9999 px; we accept anything ≥ 500 px to be
# robust against sub-pixel rounding.
_MIN_PILL_RADIUS_PX = 500


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rgb_to_hex(rgb_str: str) -> str | None:
    """Convert 'rgb(r, g, b)' or 'rgba(r, g, b, a)' to lowercase '#rrggbb'.

    Returns None if the string cannot be parsed.
    """
    import re
    m = re.match(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", rgb_str)
    if not m:
        return None
    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    return f"#{r:02x}{g:02x}{b:02x}"


def _parse_radius_px(value: str) -> float:
    """Parse a CSS length value like '9999px' to a float. Returns 0.0 on failure."""
    try:
        return float(value.replace("px", "").strip())
    except (ValueError, AttributeError):
        return 0.0


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
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        yield page
        browser.close()


@pytest.fixture(scope="module")
def site_header(browser_page: Page) -> SiteHeader:
    return SiteHeader(browser_page)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSiteHeaderSearchInputStyling:
    """MYTUBE-501: Search input has pill shape and purple focus ring."""

    # ------------------------------------------------------------------
    # Step 2: locate the search input
    # ------------------------------------------------------------------

    def test_search_input_is_visible(self, browser_page: Page, site_header: SiteHeader) -> None:
        """
        Step 2: The search input inside <header> must be present and visible.
        """
        search_input = site_header.search_input_locator()
        assert search_input.count() > 0, (
            "No search input (input[type='search']) found inside <header>. "
            "The search form was not rendered in the SiteHeader. "
            f"Page URL: {browser_page.url}"
        )
        search_input.first.wait_for(state="visible", timeout=5_000)

    # ------------------------------------------------------------------
    # Step 3: pill shape — left border-radius
    # ------------------------------------------------------------------

    def test_search_input_has_pill_shape(self, site_header: SiteHeader) -> None:
        """
        Step 3: The input must have fully-rounded left corners (pill shape).

        Tailwind class 'rounded-l-full' computes to
        border-top-left-radius: 9999px; border-bottom-left-radius: 9999px.
        We assert each is at least _MIN_PILL_RADIUS_PX (500 px) to be robust
        against sub-pixel rounding by the browser.
        """
        search_input = site_header.search_input_locator().first
        search_input.wait_for(state="visible", timeout=5_000)

        radii: dict = search_input.evaluate(
            """(el) => {
                const s = window.getComputedStyle(el);
                return {
                    borderTopLeftRadius: s.borderTopLeftRadius,
                    borderBottomLeftRadius: s.borderBottomLeftRadius,
                    borderTopRightRadius: s.borderTopRightRadius,
                    borderBottomRightRadius: s.borderBottomRightRadius,
                };
            }"""
        )

        tl = _parse_radius_px(radii.get("borderTopLeftRadius", "0px"))
        bl = _parse_radius_px(radii.get("borderBottomLeftRadius", "0px"))

        assert tl >= _MIN_PILL_RADIUS_PX, (
            f"Search input does not have a pill-shaped left border-radius. "
            f"Expected border-top-left-radius ≥ {_MIN_PILL_RADIUS_PX}px (from rounded-l-full). "
            f"Actual: borderTopLeftRadius='{radii.get('borderTopLeftRadius')}' "
            f"({tl}px). Full radii: {radii}"
        )
        assert bl >= _MIN_PILL_RADIUS_PX, (
            f"Search input does not have a pill-shaped left border-radius. "
            f"Expected border-bottom-left-radius ≥ {_MIN_PILL_RADIUS_PX}px (from rounded-l-full). "
            f"Actual: borderBottomLeftRadius='{radii.get('borderBottomLeftRadius')}' "
            f"({bl}px). Full radii: {radii}"
        )

    # ------------------------------------------------------------------
    # Steps 4 & 5: focus ring with purple accent color
    # ------------------------------------------------------------------

    def test_search_input_focus_ring_is_purple(self, browser_page: Page, site_header: SiteHeader) -> None:
        """
        Steps 4–5: Clicking the input triggers focus, and the border color
        changes to the purple --accent-logo value.

        SiteHeader.tsx applies 'focus:border-[color:var(--accent-logo)]'.
        --accent-logo is #6d40cb (light mode) or #9370db (dark mode).
        We click the input, then read the computed border-color and convert
        it to hex for a deterministic comparison.
        """
        search_input = site_header.search_input_locator().first
        search_input.wait_for(state="visible", timeout=5_000)

        # Step 4: click into the input to trigger focus
        search_input.click()
        # Allow Tailwind focus styles to apply
        browser_page.wait_for_timeout(200)

        styles: dict = search_input.evaluate(
            """(el) => {
                const s = window.getComputedStyle(el);
                return {
                    borderColor: s.borderColor,
                    outlineWidth: s.outlineWidth,
                    outlineStyle: s.outlineStyle,
                    outlineColor: s.outlineColor,
                };
            }"""
        )

        border_color_raw = styles.get("borderColor", "")
        border_hex = _rgb_to_hex(border_color_raw)

        assert border_hex in _PURPLE_ACCENT_HEX, (
            f"Focus ring color is not the expected purple accent. "
            f"Expected one of {_PURPLE_ACCENT_HEX} (--accent-logo). "
            f"Actual computed borderColor: '{border_color_raw}' → hex: '{border_hex}'. "
            f"Full computed styles: {styles}. "
            "SiteHeader.tsx should apply 'focus:border-[color:var(--accent-logo)]' "
            "when the search input is focused."
        )
