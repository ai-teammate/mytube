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
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.hero_section.hero_section_component import HeroSectionComponent

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_HERO_SELECTOR = "section[aria-label='Hero']"

# Expected declared values (as authored in HeroSection.module.css)
_EXPECTED_GAP_PX = "30px"
# Ratio  expected: 1.05 / 0.95 ≈ 1.1053
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
        page.wait_for_selector(_HERO_SELECTOR, timeout=_PAGE_LOAD_TIMEOUT)
        yield page
        browser.close()


@pytest.fixture(scope="module")
def hero(browser_page: Page) -> HeroSectionComponent:
    return HeroSectionComponent(browser_page)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_declared_grid_template_columns(page: Page, element_selector: str) -> str | None:
    """
    Scan all loaded CSS style sheets for a rule whose selector matches the
    hero element and that declares a ``grid-template-columns`` property.

    Returns the raw declared value (e.g. ``"1.05fr 0.95fr"``) or ``None``
    if no matching rule is found.

    Because Next.js CSS Modules mangle class names at build time we cannot
    know the exact class name ahead of time.  Instead we look for a rule
    that applies to the element by testing each rule's selector against
    the element using ``element.matches()``.
    """
    return page.evaluate(
        """
        (selector) => {
            const el = document.querySelector(selector);
            if (!el) return null;

            for (const sheet of document.styleSheets) {
                let rules;
                try {
                    rules = sheet.cssRules || sheet.rules;
                } catch (e) {
                    // Cross-origin stylesheet — skip
                    continue;
                }
                if (!rules) continue;

                for (const rule of rules) {
                    if (rule.type !== 1) continue;  // CSSStyleRule only
                    let matches = false;
                    try {
                        matches = el.matches(rule.selectorText);
                    } catch (e) {
                        continue;
                    }
                    if (matches && rule.style.gridTemplateColumns) {
                        return rule.style.gridTemplateColumns.trim();
                    }
                }
            }
            return null;
        }
        """,
        element_selector,
    )


def _get_computed_column_gap(page: Page, element_selector: str) -> str:
    """Return the computed column-gap of the hero grid element."""
    return page.eval_on_selector(
        element_selector,
        "el => window.getComputedStyle(el).columnGap",
    )


def _get_computed_column_widths(page: Page, element_selector: str) -> tuple[float, float] | None:
    """
    Return the computed pixel widths of the two grid columns by reading the
    ``grid-template-columns`` resolved value (e.g. ``"672px 608px"``) and
    splitting it into two floats.  Returns ``None`` if the value cannot be
    parsed as two pixel measurements.
    """
    raw: str = page.eval_on_selector(
        element_selector,
        "el => window.getComputedStyle(el).gridTemplateColumns",
    )
    parts = raw.strip().split()
    if len(parts) != 2:
        return None
    try:
        w1 = float(parts[0].rstrip("px"))
        w2 = float(parts[1].rstrip("px"))
        return w1, w2
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHeroDesktopGridLayout:
    """MYTUBE-533: Verify the hero grid uses 1.05fr 0.95fr columns with 30px gap."""

    def test_hero_section_is_visible(self, browser_page: Page) -> None:
        """
        Step 1 / Pre-condition: the hero section must be rendered and visible
        at a desktop viewport (width ≥ 768 px).
        """
        hero_loc = browser_page.locator(_HERO_SELECTOR)
        assert hero_loc.count() > 0, (
            f"Hero section element ('{_HERO_SELECTOR}') not found on the homepage. "
            f"URL: {browser_page.url!r}"
        )
        hero_loc.first.wait_for(state="visible", timeout=10_000)

    def test_declared_grid_template_columns(self, browser_page: Page) -> None:
        """
        Step 3 (primary assertion): the CSS rule applied to the hero element
        must declare ``grid-template-columns: 1.05fr 0.95fr``.

        This check reads the authored stylesheet value — not the browser's
        resolved pixel representation — so it faithfully validates the design
        specification.
        """
        declared = _get_declared_grid_template_columns(browser_page, _HERO_SELECTOR)

        assert declared is not None, (
            f"No CSS rule with 'grid-template-columns' found for '{_HERO_SELECTOR}'. "
            "Either the hero section is not using a CSS-grid layout or the "
            "stylesheet could not be read (cross-origin restriction)."
        )

        assert declared == "1.05fr 0.95fr", (
            f"Expected declared grid-template-columns to be '1.05fr 0.95fr', "
            f"but got: {declared!r}. "
            "The hero section CSS does not match the 2-column specification."
        )

    def test_computed_column_gap_is_30px(self, browser_page: Page) -> None:
        """
        Step 3: the computed column-gap of the hero grid must be 30 px.

        ``gap: 30px`` in the CSS resolves to ``column-gap: 30px`` and
        ``row-gap: 30px``; we assert the column gap specifically.
        """
        gap = _get_computed_column_gap(browser_page, _HERO_SELECTOR)

        assert gap == _EXPECTED_GAP_PX, (
            f"Expected computed column-gap to be '{_EXPECTED_GAP_PX}', "
            f"but got: {gap!r}. "
            "The hero section 'gap' CSS property may not be set to 30px."
        )

    def test_column_width_ratio_matches_specification(self, browser_page: Page) -> None:
        """
        Step 3 (geometric sanity): the rendered column widths must reflect the
        1.05 : 0.95 ratio within a ±2 % tolerance.

        This test complements the stylesheet check and catches cases where an
        inline style or a more-specific rule overrides the module CSS.
        """
        widths = _get_computed_column_widths(browser_page, _HERO_SELECTOR)

        assert widths is not None, (
            "Could not parse computed grid-template-columns as two pixel values. "
            f"Raw value: {browser_page.eval_on_selector(_HERO_SELECTOR, 'el => window.getComputedStyle(el).gridTemplateColumns')!r}"
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
