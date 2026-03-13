"""
HeroSectionComponent — Page Object for the hero section on the homepage.

Encapsulates selectors and interactions for the hero section responsive grid:
  - grid-template-columns computed-style inspection
  - bounding-box geometry assertions (stacked vs side-by-side layout)
  - CTA button ("Upload Your First Video") styling and navigation
"""
from __future__ import annotations

from playwright.sync_api import Locator, Page


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

    # Hero CTA — "Upload Your First Video" link rendered as .btn.cta
    _UPLOAD_CTA = "a.btn.cta, a:has-text('Upload Your First Video')"

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

    # ------------------------------------------------------------------
    # Upload CTA button — "Upload Your First Video"
    # ------------------------------------------------------------------

    def upload_cta_button(self) -> Locator:
        """Return a Playwright Locator for the 'Upload Your First Video' CTA button."""
        return self._page.locator(self._UPLOAD_CTA).first

    def is_upload_cta_visible(self) -> bool:
        """Return True if the Upload CTA button is visible on the page."""
        btn = self.upload_cta_button()
        return btn.count() > 0 and btn.is_visible()

    def upload_cta_computed_styles(self) -> dict:
        """Return computed CSS properties for the Upload CTA button.

        Inspects backgroundImage, boxShadow, borderRadius, and color so that
        tests can assert green-gradient pill styling without accessing Playwright directly.
        """
        btn = self.upload_cta_button()
        btn.wait_for(state="visible", timeout=10_000)
        return btn.evaluate(
            """(el) => {
                const s = window.getComputedStyle(el);
                return {
                    backgroundImage:     s.backgroundImage,
                    backgroundColor:     s.backgroundColor,
                    boxShadow:           s.boxShadow,
                    borderTopLeftRadius: s.borderTopLeftRadius,
                    color:               s.color,
                };
            }"""
        )

    def upload_cta_href(self) -> str:
        """Return the href attribute of the Upload CTA button."""
        return self.upload_cta_button().get_attribute("href") or ""

    def click_upload_cta(self) -> None:
        """Click the 'Upload Your First Video' CTA button."""
        self.upload_cta_button().click()

    # ------------------------------------------------------------------
    # Landing image — selectors and helpers for MYTUBE-573
    # ------------------------------------------------------------------

    _LANDING_IMAGE_SELECTORS = [
        "img[alt='Personal Playback Preview']",
        "img[src*='landing_image']",
    ]

    _VISUAL_CANVAS_SELECTORS = [
        "[class*='visualCanvas']",
        ".visualCanvas",
    ]

    _VISUAL_PANEL_SELECTORS = [
        "[class*='visualPanel']",
        ".visualPanel",
    ]

    def _find_locator(self, selectors: list[str]) -> "Locator | None":
        """Return the first locator that matches any of *selectors*, or None."""
        for selector in selectors:
            loc = self._page.locator(selector)
            try:
                if loc.count() > 0:
                    return loc.first
            except Exception:
                continue
        return None

    def get_landing_image_box(self, timeout: int = 10_000) -> "dict | None":
        """Return the bounding box of the landing image element.

        Waits for the element to become visible before measuring it.
        Returns None only if the element cannot be found.
        """
        loc = self._find_locator(self._LANDING_IMAGE_SELECTORS)
        if loc is None:
            return None
        loc.wait_for(state="visible", timeout=timeout)
        return loc.bounding_box()

    def get_landing_image_object_fit(self) -> str:
        """Return the computed ``object-fit`` CSS value of the landing image."""
        for selector in self._LANDING_IMAGE_SELECTORS:
            result: str = self._page.evaluate(
                """(sel) => {
                    const el = document.querySelector(sel);
                    if (!el) return '';
                    return window.getComputedStyle(el).objectFit || '';
                }""",
                selector,
            )
            if result:
                return result
        return ""

    def get_visual_canvas_box(self) -> "dict | None":
        """Return the bounding box of the visual canvas container.

        Tries ``_VISUAL_CANVAS_SELECTORS`` first, then falls back to
        ``_VISUAL_PANEL_SELECTORS``.  Returns ``None`` only if nothing is found.
        """
        for selectors in (self._VISUAL_CANVAS_SELECTORS, self._VISUAL_PANEL_SELECTORS):
            loc = self._find_locator(selectors)
            if loc is not None:
                return loc.bounding_box()
        return None

    def is_landing_image_visible(self, timeout: int = 10_000) -> bool:
        """Return True if the landing image is present and visible."""
        loc = self._find_locator(self._LANDING_IMAGE_SELECTORS)
        if loc is None:
            return False
        try:
            loc.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Grid layout
    # ------------------------------------------------------------------

    def get_grid_template_columns(self, selector: str | None = None) -> str:
        """Return the computed grid-template-columns value for the hero grid.

        Note: the default selector was changed from ``_HERO_GRID``
        (``[data-testid='hero-grid']``) to ``_HERO_SECTION``
        (``section[aria-label='Hero']``) because the ``data-testid="hero-grid"``
        attribute does not exist in the live DOM — the ``<section aria-label="Hero">``
        element is the actual CSS grid container.
        """
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
