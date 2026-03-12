"""Page Object for the hero section visual panel.

Encapsulates all selectors and computed-style queries for the ``.visual-panel``
element so that tests remain free of inline DOM logic.

Architecture layer: Components (Tests → Components → Frameworks → Core).
"""
from __future__ import annotations

import re
from typing import List

from playwright.sync_api import Page

# Compiled regex for robustly extracting the alpha channel from an rgba()
# colour string.  Handles both integer (``rgba(r,g,b,0)``) and decimal
# (``rgba(r,g,b,0.15)``) alpha values and arbitrary whitespace.
_ALPHA_RE = re.compile(
    r"rgba\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*([01](?:\.\d+)?)\s*\)"
)


class VisualPanelPage:
    """Encapsulates selectors and queries for the hero section visual panel."""

    _PANEL = ".visual-panel"
    _TITLE = ".visual-panel__title, .visual-panel [class*='title']"
    _THUMBNAIL = ".visual-panel__thumbnail, .visual-panel [class*='thumbnail']"
    _BADGE = ".quality-badge, .visual-panel [class*='badge'], .visual-panel [class*='pill']"

    def __init__(self, page: Page) -> None:
        self._page = page

    def panel_locator(self):
        return self._page.locator(self._PANEL)

    def title_text(self) -> str:
        """Return the text of the panel title, searching broadly."""
        loc = self._page.locator(self._TITLE)
        if loc.count() > 0:
            return loc.first.inner_text().strip()
        panel = self._page.locator(self._PANEL)
        return panel.inner_text().strip()

    def badge_texts(self) -> List[str]:
        badges = self._page.locator(self._BADGE)
        count = badges.count()
        return [badges.nth(i).inner_text().strip() for i in range(count)]

    def thumbnail_locator(self):
        return self._page.locator(self._THUMBNAIL)

    def panel_has_title_text(self, expected: str) -> bool:
        """Return True if the panel contains *expected* title text anywhere."""
        panel = self._page.locator(self._PANEL)
        try:
            return expected in panel.inner_text(timeout=5_000)
        except Exception:
            return False

    def panel_backdrop_filter(self) -> str:
        """Return the computed backdropFilter style of the .visual-panel element."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('.visual-panel');
                if (!el) return '';
                const style = window.getComputedStyle(el);
                return style.backdropFilter || style.webkitBackdropFilter || '';
            }"""
        )

    def panel_background(self) -> str:
        """Return the computed background / backgroundColor of the visual panel."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('.visual-panel');
                if (!el) return '';
                const style = window.getComputedStyle(el);
                return style.background || style.backgroundColor || '';
            }"""
        )

    def panel_border(self) -> str:
        """Return the computed border of the visual panel."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('.visual-panel');
                if (!el) return '';
                const style = window.getComputedStyle(el);
                return style.border || '';
            }"""
        )

    def panel_has_semi_transparent_background(self) -> bool:
        """Return True if the panel background has an rgba alpha < 1.

        Uses a compiled regex to correctly handle both integer and decimal
        alpha values (e.g. ``rgba(r,g,b,0)`` and ``rgba(r,g,b,0.15)``),
        avoiding the edge-case false-positives of a simple string suffix check.
        """
        background = self.panel_background()
        match = _ALPHA_RE.search(background)
        return bool(match) and float(match.group(1)) < 1.0
