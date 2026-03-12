"""PlaylistFilterChipsPage — Page Object for the playlist filter chip row.

Encapsulates all interactions with the `.playlist-row` section rendered by
the dashboard's _content.tsx component, exposing only high-level state queries
and actions to test callers.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller navigates before using this object.
- CSS variable resolution is handled via JS ``getComputedStyle`` calls.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class PlaylistFilterChipsPage:
    """Interactions and assertions for the playlist filter chip row."""

    # Selector matching the group container rendered by _content.tsx:
    #   <div role="group" aria-label="Filter by playlist" ...>
    _PLAYLIST_ROW = "[role='group'][aria-label='Filter by playlist']"

    # Chip buttons inside the row
    _CHIP_BUTTONS = f"{_PLAYLIST_ROW} button"
    _ALL_CHIP = f"{_PLAYLIST_ROW} button:has-text('All')"

    _ROW_VISIBLE_TIMEOUT = 15_000  # ms

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Visibility / layout
    # ------------------------------------------------------------------

    def wait_for_playlist_row(self, timeout: int = _ROW_VISIBLE_TIMEOUT) -> None:
        """Block until the playlist row is visible in the DOM."""
        self._page.wait_for_selector(self._PLAYLIST_ROW, timeout=timeout)

    def is_playlist_row_visible(self) -> bool:
        """Return True if the playlist row container is present and visible."""
        locator = self._page.locator(self._PLAYLIST_ROW)
        return locator.count() > 0 and locator.first.is_visible()

    def get_row_overflow_x(self) -> str:
        """Return the computed overflow-x value of the playlist row container."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector("[role='group'][aria-label='Filter by playlist']");
                if (!el) return '';
                return window.getComputedStyle(el).overflowX;
            }"""
        )

    def get_chip_count(self) -> int:
        """Return the number of chip buttons (includes 'All' + playlist chips)."""
        return self._page.locator(self._CHIP_BUTTONS).count()

    # ------------------------------------------------------------------
    # CSS style queries (computed, resolves CSS variables at runtime)
    # ------------------------------------------------------------------

    def get_all_chip_bg_color(self) -> str:
        """Return the computed background-color of the 'All' chip."""
        return self._page.evaluate(
            """() => {
                const row = document.querySelector("[role='group'][aria-label='Filter by playlist']");
                if (!row) return '';
                const el = row.querySelector("button");
                if (!el) return '';
                return window.getComputedStyle(el).backgroundColor;
            }"""
        )

    def get_all_chip_text_color(self) -> str:
        """Return the computed color of the 'All' chip."""
        return self._page.evaluate(
            """() => {
                const row = document.querySelector("[role='group'][aria-label='Filter by playlist']");
                if (!row) return '';
                const el = row.querySelector("button");
                if (!el) return '';
                return window.getComputedStyle(el).color;
            }"""
        )

    def get_chip_bg_color(self, index: int) -> str:
        """Return the computed background-color of the chip at *index* (0-based)."""
        return self._page.evaluate(
            f"""() => {{
                const row = document.querySelector("[role='group'][aria-label='Filter by playlist']");
                if (!row) return '';
                const buttons = row.querySelectorAll("button");
                const el = buttons[{index}];
                if (!el) return '';
                return window.getComputedStyle(el).backgroundColor;
            }}"""
        )

    def get_chip_text_color(self, index: int) -> str:
        """Return the computed color of the chip at *index* (0-based)."""
        return self._page.evaluate(
            f"""() => {{
                const row = document.querySelector("[role='group'][aria-label='Filter by playlist']");
                if (!row) return '';
                const buttons = row.querySelectorAll("button");
                const el = buttons[{index}];
                if (!el) return '';
                return window.getComputedStyle(el).color;
            }}"""
        )

    def get_chip_border_color(self, index: int) -> str:
        """Return the computed border-top-color of the chip at *index* (0-based)."""
        return self._page.evaluate(
            f"""() => {{
                const row = document.querySelector("[role='group'][aria-label='Filter by playlist']");
                if (!row) return '';
                const buttons = row.querySelectorAll("button");
                const el = buttons[{index}];
                if (!el) return '';
                return window.getComputedStyle(el).borderTopColor;
            }}"""
        )

    def get_chip_border_width(self, index: int) -> str:
        """Return the computed border-top-width of the chip at *index* (0-based)."""
        return self._page.evaluate(
            f"""() => {{
                const row = document.querySelector("[role='group'][aria-label='Filter by playlist']");
                if (!row) return '';
                const buttons = row.querySelectorAll("button");
                const el = buttons[{index}];
                if (!el) return '';
                return window.getComputedStyle(el).borderTopWidth;
            }}"""
        )

    def get_resolved_css_var(self, var_name: str) -> str:
        """Return the resolved value of a CSS custom property from the document root.

        Example: ``get_resolved_css_var('--accent-logo')`` → ``'#6d40cb'``
        """
        return self._page.evaluate(
            f"() => getComputedStyle(document.documentElement)"
            f".getPropertyValue('{var_name}').trim()"
        )

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def click_chip(self, index: int) -> None:
        """Click the chip button at *index* (0-based) in the playlist row."""
        self._page.locator(self._CHIP_BUTTONS).nth(index).click()

    def get_chip_text(self, index: int) -> str:
        """Return the text content of the chip at *index* (0-based)."""
        btn = self._page.locator(self._CHIP_BUTTONS).nth(index)
        return (btn.text_content() or "").strip()

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def css_var_bg_matches_chip(self, var_name: str, chip_index: int) -> bool:
        """Return True if the chip at *chip_index* has a background-color equal to
        the resolved value of the CSS custom property *var_name*.

        Uses a temporary DOM element to resolve the CSS variable inside the
        browser's own rendering context, avoiding hex-to-rgb conversion
        precision issues.
        """
        return bool(self._page.evaluate(
            """({idx, varName}) => {
                const row = document.querySelector(
                    "[role='group'][aria-label='Filter by playlist']"
                );
                if (!row) return false;
                const buttons = row.querySelectorAll("button");
                const chip = buttons[idx];
                if (!chip) return false;
                const chipBg = window.getComputedStyle(chip).backgroundColor;
                const tmp = document.createElement('span');
                tmp.style.backgroundColor = 'var(' + varName + ')';
                tmp.style.position = 'absolute';
                tmp.style.visibility = 'hidden';
                document.body.appendChild(tmp);
                const varBg = window.getComputedStyle(tmp).backgroundColor;
                document.body.removeChild(tmp);
                return chipBg === varBg;
            }""",
            {"idx": chip_index, "varName": var_name},
        ))

    def css_var_color_matches_chip(self, var_name: str, chip_index: int) -> bool:
        """Return True if the chip at *chip_index* has a ``color`` equal to the
        resolved value of *var_name*.
        """
        return bool(self._page.evaluate(
            """({idx, varName}) => {
                const row = document.querySelector(
                    "[role='group'][aria-label='Filter by playlist']"
                );
                if (!row) return false;
                const buttons = row.querySelectorAll("button");
                const chip = buttons[idx];
                if (!chip) return false;
                const chipColor = window.getComputedStyle(chip).color;
                const tmp = document.createElement('span');
                tmp.style.color = 'var(' + varName + ')';
                tmp.style.position = 'absolute';
                tmp.style.visibility = 'hidden';
                document.body.appendChild(tmp);
                const varColor = window.getComputedStyle(tmp).color;
                document.body.removeChild(tmp);
                return chipColor === varColor;
            }""",
            {"idx": chip_index, "varName": var_name},
        ))

    def all_chip_bg_matches_var(self, var_name: str) -> bool:
        """Return True if the 'All' chip's background matches *var_name*."""
        return self.css_var_bg_matches_chip(var_name, 0)

    def all_chip_color_matches_white(self) -> bool:
        """Return True if the 'All' chip's computed color is white (#fff)."""
        actual = self.get_all_chip_text_color()
        return actual in ("rgb(255, 255, 255)", "rgba(255, 255, 255, 1)")

    @staticmethod
    def hex_to_rgb(hex_color: str) -> str:
        """Convert a hex color string to ``rgb(r, g, b)`` notation.

        Supports 3-digit and 6-digit hex with or without the leading ``#``.
        Example: ``hex_to_rgb('#6d40cb')`` → ``'rgb(109, 64, 203)'``
        """
        hex_color = hex_color.lstrip("#")
        if len(hex_color) == 3:
            hex_color = "".join(c * 2 for c in hex_color)
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"rgb({r}, {g}, {b})"
