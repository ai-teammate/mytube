"""HeaderPage — Page Object for the site-wide header of the MyTube web application.

Encapsulates all interactions with the search input and search submit button
rendered by SiteHeader.tsx.  Raw selectors never leak outside this class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — callers provide the full URL for navigation.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from playwright.sync_api import Page


class HeaderPage:
    """Page Object for the MyTube site header — search bar and search button."""

    # Selectors (private — callers use the query/action methods below)
    _SEARCH_INPUT = 'input[type="search"]'
    _SEARCH_BUTTON = 'button[aria-label="Submit search"]'

    _PAGE_LOAD_TIMEOUT = 30_000  # ms

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to(self, url: str) -> None:
        """Navigate to *url* and wait for the search input to be present."""
        self._page.goto(url, wait_until="domcontentloaded")
        self._page.wait_for_selector(self._SEARCH_INPUT, timeout=self._PAGE_LOAD_TIMEOUT)

    # ------------------------------------------------------------------
    # Search input visibility queries
    # ------------------------------------------------------------------

    def is_search_input_visible(self) -> bool:
        """Return True if the search input element is visible on the page."""
        return self._page.locator(self._SEARCH_INPUT).is_visible()

    def get_search_placeholder(self) -> str:
        """Return the placeholder attribute of the search input, or empty string."""
        return self._page.locator(self._SEARCH_INPUT).get_attribute("placeholder") or ""

    def is_search_input_text_color_visible(self) -> str:
        """Return False if the search input's computed text colour is fully transparent."""
        color: str | None = self._page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                return window.getComputedStyle(el).color;
            }""",
            self._SEARCH_INPUT,
        )
        if color is None:
            return False
        return color != "rgba(0, 0, 0, 0)"

    # ------------------------------------------------------------------
    # Search button visibility queries
    # ------------------------------------------------------------------

    def is_search_button_visible(self) -> bool:
        """Return True if the search submit button is visible on the page."""
        return self._page.locator(self._SEARCH_BUTTON).is_visible()

    def get_search_button_label(self) -> str:
        """Return the accessible text / aria-label of the search button."""
        label: str = self._page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return '';
                return (
                    el.innerText ||
                    el.textContent ||
                    el.getAttribute('aria-label') ||
                    ''
                ).trim();
            }""",
            self._SEARCH_BUTTON,
        )
        return label or ""
