"""LibraryToolbarPage — Page Object for the library toolbar area on /upload.

Encapsulates all interactions with the search/filter toolbar in the right-hand
library area of the /upload page.  Exposes high-level query methods so that
test files do not interact with raw Playwright types directly.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs or selectors outside this class.
- All JS evaluation helpers live here; the test file contains only assertions.
"""
from __future__ import annotations

from playwright.sync_api import Page


class LibraryToolbarPage:
    """Page Object for the library toolbar grid on the /upload page."""

    _SEARCH_INPUT_SELECTOR = '[aria-label="search videos"]'
    _CATEGORY_SELECT_SELECTOR = '[aria-label="filter by category"]'

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Presence queries
    # ------------------------------------------------------------------

    def search_input_count(self) -> int:
        """Return the number of search input elements matching the selector."""
        return self._page.locator(self._SEARCH_INPUT_SELECTOR).count()

    def category_select_count(self) -> int:
        """Return the number of category select elements matching the selector."""
        return self._page.locator(self._CATEGORY_SELECT_SELECTOR).count()

    def reset_button_in_toolbar(self) -> bool:
        """Return True if a 'Reset' button exists inside the toolbar row."""
        return self._page.evaluate(
            """([searchSel]) => {
                const searchInput = document.querySelector(searchSel);
                if (!searchInput) return false;
                const row = searchInput.parentElement;
                const buttons = row ? Array.from(row.querySelectorAll('button')) : [];
                return buttons.some(btn => (btn.textContent || '').trim() === 'Reset');
            }""",
            [self._SEARCH_INPUT_SELECTOR],
        )

    # ------------------------------------------------------------------
    # Layout queries
    # ------------------------------------------------------------------

    def search_and_select_share_parent(self) -> bool:
        """Return True if the search input and category select share the same parent."""
        return self._page.evaluate(
            """([selA, selB]) => {
                const a = document.querySelector(selA);
                const b = document.querySelector(selB);
                return a !== null && b !== null && a.parentElement === b.parentElement;
            }""",
            [self._SEARCH_INPUT_SELECTOR, self._CATEGORY_SELECT_SELECTOR],
        )

    def get_toolbar_css(self) -> dict:
        """Return key computed CSS values for the toolbar row element."""
        return self._page.eval_on_selector(
            self._SEARCH_INPUT_SELECTOR,
            """el => {
                const row = el.parentElement;
                const cs = window.getComputedStyle(row);
                return {
                    display: cs.display,
                    gridTemplateColumns: cs.gridTemplateColumns,
                    gap: cs.gap,
                    columnGap: cs.columnGap,
                    alignItems: cs.alignItems,
                    childCount: row.children.length,
                    tagName: row.tagName.toLowerCase(),
                };
            }""",
        )
