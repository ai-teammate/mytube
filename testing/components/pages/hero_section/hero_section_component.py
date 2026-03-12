"""
HeroSectionComponent — Page Object for the hero section on the homepage.

Encapsulates selectors and interactions for the hero section responsive grid:
  - grid-template-columns computed-style inspection
  - bounding-box geometry assertions (stacked vs side-by-side layout)
"""
from __future__ import annotations

from playwright.sync_api import Page


class HeroSectionComponent:
    """Page Object for the homepage hero section responsive grid."""

    # Canonical selector for the hero section element (also the grid container).
    # The <section aria-label="Hero"> element carries display:grid directly.
    _HERO_SECTION = "section[aria-label='Hero']"

    _HERO_GRID = "[data-testid='hero-grid']"
    _TEXT_COL = "[data-testid='hero-text-column']"
    _VISUAL = "[data-testid='hero-visual-panel']"

    # Fallback selectors for live app (no data-testid attributes)
    _HERO_GRID_FALLBACK = "[data-testid='hero-grid'], .hero-grid"

    def __init__(self, page: Page) -> None:
        self._page = page

    def is_hero_visible(self, timeout: int = 10_000) -> bool:
        """Return True if the hero section is rendered and visible."""
        loc = self._page.locator(self._HERO_SECTION)
        if loc.count() == 0:
            return False
        loc.first.wait_for(state="visible", timeout=timeout)
        return True

    def get_declared_grid_template_columns(self) -> str | None:
        """
        Scan all loaded CSS stylesheets for a rule applied to the hero section
        that declares ``grid-template-columns``.

        Returns the raw authored value (e.g. ``"1.05fr 0.95fr"``) or ``None``
        if no matching rule is found.  Works with CSS-Modules mangled class names
        by testing each rule's selector via ``element.matches()``.
        """
        return self._page.evaluate(
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
            self._HERO_SECTION,
        )

    def get_computed_column_gap(self) -> str:
        """Return the computed column-gap of the hero grid element."""
        return self._page.eval_on_selector(
            self._HERO_SECTION,
            "el => window.getComputedStyle(el).columnGap",
        )

    def get_computed_column_widths(self) -> "tuple[float, float] | None":
        """
        Return the rendered pixel widths of the two grid columns by reading the
        computed ``grid-template-columns`` value (e.g. ``"672px 608px"``).

        Returns a ``(col1_px, col2_px)`` tuple, or ``None`` if the resolved value
        cannot be parsed as exactly two pixel measurements.
        """
        raw: str = self._page.eval_on_selector(
            self._HERO_SECTION,
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

    def get_grid_template_columns(self, selector: str | None = None) -> str:
        """Return the computed grid-template-columns value for the hero grid."""
        sel = selector or self._HERO_SECTION
        return self._page.eval_on_selector(
            sel,
            "el => window.getComputedStyle(el).gridTemplateColumns",
        )

    def assert_stacked_layout(self) -> None:
        """Assert the visual panel is rendered *below* the text column
        (single-column / stacked layout)."""
        text_box = self._page.locator(self._TEXT_COL).bounding_box()
        panel_box = self._page.locator(self._VISUAL).bounding_box()

        assert text_box is not None, "Text column not found / not visible"
        assert panel_box is not None, "Visual panel not found / not visible"

        text_bottom = text_box["y"] + text_box["height"]
        panel_top = panel_box["y"]

        # Allow 2 px tolerance for sub-pixel rounding
        assert panel_top >= text_bottom - 2, (
            f"Visual panel is NOT stacked below the text column at this viewport.\n"
            f"Text column:  y={text_box['y']:.1f}, height={text_box['height']:.1f}, "
            f"bottom={text_bottom:.1f}\n"
            f"Visual panel: y={panel_top:.1f}\n"
            "Expected the visual panel to start at or after the text column's bottom "
            "(single-column / stacked layout), but the panel appears beside it."
        )

    def assert_side_by_side_layout(self) -> None:
        """Assert that at desktop width the two columns are rendered side-by-side."""
        text_box = self._page.locator(self._TEXT_COL).bounding_box()
        panel_box = self._page.locator(self._VISUAL).bounding_box()

        assert text_box is not None, "Text column not found / not visible"
        assert panel_box is not None, "Visual panel not found / not visible"

        text_mid_y = text_box["y"] + text_box["height"] / 2
        panel_mid_y = panel_box["y"] + panel_box["height"] / 2

        # In a two-column layout both elements share the same grid row; their
        # vertical midpoints should be within ~100 px of each other.
        assert abs(text_mid_y - panel_mid_y) < 100, (
            f"At desktop viewport the columns do not appear side-by-side.\n"
            f"Text column mid-y:  {text_mid_y:.1f}\n"
            f"Visual panel mid-y: {panel_mid_y:.1f}\n"
            "Expected both columns to share the same grid row."
        )
