"""
MYTUBE-533: Hero section desktop layout — grid structure follows 2-column specification.

Objective
---------
Verify the hero section uses the specified CSS grid proportions on desktop viewports.

Preconditions
-------------
Browser window width is 768px or greater.

Steps
-----
1. Navigate to the homepage.
2. Inspect the hero container element.
3. Verify the CSS grid properties in the computed styles.

Expected Result
---------------
The grid configuration is ``grid-template-columns: 1.05fr 0.95fr`` with a ``gap: 30px``.

Test Approach
-------------
Playwright navigates to the deployed homepage at a desktop viewport (1280×800) and:

  1. Waits for the hero section (``<section aria-label="Hero">``) to be visible.
  2. Reads the declared CSS rule for grid-template-columns by scanning document.styleSheets
     for a rule that applies to the hero element — this gives the authored ``fr`` values,
     not browser-resolved pixel values.
  3. Verifies the declared value is ``1.05fr 0.95fr``.
  4. Verifies the computed ``column-gap`` (resolved from ``gap: 30px``) equals ``30px``.
  5. As a geometric sanity check, verifies the ratio of the two rendered column widths
     matches the 1.05 : 0.95 proportion within a 2 % tolerance.

Architecture
------------
- Uses HeroSectionComponent from testing/components/pages/hero_section/.
- Uses WebConfig from testing/core/config/web_config.py.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.hero_section.hero_section_component import HeroSectionComponent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Expected declared values (as authored in HeroSection.module.css)
_EXPECTED_GAP_PX = "30px"
# Ratio expected: 1.05 / 0.95 ≈ 1.1053
_EXPECTED_COL_RATIO = 1.05 / 0.95
_COL_RATIO_TOLERANCE = 0.02  # ±2 %

# Desktop viewport — must be ≥ 768 px to trigger 2-column grid
_VIEWPORT = {"width": 1280, "height": 800}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    """Launch Chromium at a desktop viewport and load the homepage."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo,
        )
        page = browser.new_page(viewport=_VIEWPORT)
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        yield page
        browser.close()


@pytest.fixture(scope="module")
def hero(browser_page) -> HeroSectionComponent:
    component = HeroSectionComponent(browser_page)
    component.is_hero_visible(timeout=_PAGE_LOAD_TIMEOUT)
    return component


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHeroDesktopGridLayout:
    """MYTUBE-533: Verify the hero grid uses 1.05fr 0.95fr columns with 30px gap."""

    def test_hero_section_is_visible(self, hero: HeroSectionComponent) -> None:
        """
        Step 1 / Pre-condition: the hero section must be rendered and visible
        at a desktop viewport (width ≥ 768 px).
        """
        assert hero.is_hero_visible(), (
            "Hero section element not found or not visible on the homepage. "
            f"Selector: '{HeroSectionComponent._HERO_SECTION}'"
        )

    def test_declared_grid_template_columns(self, hero: HeroSectionComponent) -> None:
        """
        Step 3 (primary assertion): the CSS rule applied to the hero element
        must declare ``grid-template-columns: 1.05fr 0.95fr``.

        This check reads the authored stylesheet value — not the browser's
        resolved pixel representation — so it faithfully validates the design
        specification.
        """
        declared = hero.get_declared_grid_template_columns()

        assert declared is not None, (
            f"No CSS rule with 'grid-template-columns' found for "
            f"'{HeroSectionComponent._HERO_SECTION}'. "
            "Either the hero section is not using a CSS-grid layout or the "
            "stylesheet could not be read (cross-origin restriction)."
        )

        assert declared == "1.05fr 0.95fr", (
            f"Expected declared grid-template-columns to be '1.05fr 0.95fr', "
            f"but got: {declared!r}. "
            "The hero section CSS does not match the 2-column specification."
        )

    def test_computed_column_gap_is_30px(self, hero: HeroSectionComponent) -> None:
        """
        Step 3: the computed column-gap of the hero grid must be 30 px.

        ``gap: 30px`` in the CSS resolves to ``column-gap: 30px`` and
        ``row-gap: 30px``; we assert the column gap specifically.
        """
        gap = hero.get_computed_column_gap()

        assert gap == _EXPECTED_GAP_PX, (
            f"Expected computed column-gap to be '{_EXPECTED_GAP_PX}', "
            f"but got: {gap!r}. "
            "The hero section 'gap' CSS property may not be set to 30px."
        )

    def test_column_width_ratio_matches_specification(self, hero: HeroSectionComponent) -> None:
        """
        Step 3 (geometric sanity): the rendered column widths must reflect the
        1.05 : 0.95 ratio within a ±2 % tolerance.

        This test complements the stylesheet check and catches cases where an
        inline style or a more-specific rule overrides the module CSS.
        """
        widths = hero.get_computed_column_widths()

        assert widths is not None, (
            "Could not parse computed grid-template-columns as two pixel values. "
            "The grid may not be active at this viewport width."
        )

        w1, w2 = widths
        assert w2 > 0, (
            f"Second column width is zero or negative ({w2}). "
            "The grid may not be rendering two columns at this viewport width."
        )

        actual_ratio = w1 / w2
        assert abs(actual_ratio - _EXPECTED_COL_RATIO) <= _COL_RATIO_TOLERANCE, (
            f"Expected column-width ratio ≈ {_EXPECTED_COL_RATIO:.4f} (1.05fr / 0.95fr), "
            f"but got ratio {actual_ratio:.4f} (col1={w1:.1f}px, col2={w2:.1f}px). "
            "The hero grid proportions do not match the 2-column specification."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
