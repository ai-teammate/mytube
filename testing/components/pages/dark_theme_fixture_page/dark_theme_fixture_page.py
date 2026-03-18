"""DarkThemeFixturePage component — encapsulates Playwright browser interactions
for dark-theme CSS token verification tests.

This component accepts a Playwright ``Browser`` via constructor injection and
exposes high-level methods for querying computed CSS properties.  Test methods
depend only on this interface; they never touch the raw Playwright ``Page``.
"""
from __future__ import annotations

from playwright.sync_api import Browser

from testing.core.utils.css_analysis import build_dark_theme_fixture


class DarkThemeFixturePage:
    """Component that loads a self-contained dark-theme HTML fixture in a browser.

    Usage::

        component = DarkThemeFixturePage(browser)
        component.load()
        bg = component.get_background_color("modal-card")

    The fixture page embeds the real ``globals.css`` and
    ``_content.module.css`` so that CSS custom properties resolve to their
    actual dark-theme values via ``getComputedStyle``.
    """

    def __init__(self, browser: Browser) -> None:
        self._browser = browser
        self._page = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Open a new page and load the dark-theme HTML fixture."""
        self._page = self._browser.new_page()
        self._page.set_content(
            build_dark_theme_fixture(),
            wait_until="domcontentloaded",
        )

    def close(self) -> None:
        """Close the underlying Playwright page."""
        if self._page is not None:
            self._page.close()
            self._page = None

    # ------------------------------------------------------------------
    # High-level queries
    # ------------------------------------------------------------------

    def get_background_color(self, element_id: str) -> str:
        """Return the computed ``background-color`` of the element with *element_id*.

        Returns an empty string when the element is not found.
        """
        assert self._page is not None, "Call load() before querying the page."
        return self._page.evaluate(
            """([id]) => {
                const el = document.getElementById(id);
                if (!el) return '';
                return getComputedStyle(el).getPropertyValue('background-color').trim();
            }""",
            [element_id],
        )

    def get_body_background_color(self) -> str:
        """Return the computed ``background-color`` of the ``<body>`` element."""
        assert self._page is not None, "Call load() before querying the page."
        return self._page.evaluate(
            """() => getComputedStyle(document.body)
                        .getPropertyValue('background-color').trim()"""
        )

    def element_count(self, element_id: str) -> int:
        """Return the number of elements with *element_id* in the DOM."""
        assert self._page is not None, "Call load() before querying the page."
        return self._page.evaluate(
            "([id]) => document.querySelectorAll('#' + id).length",
            [element_id],
        )
