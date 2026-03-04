"""SaveToPlaylistWidget — Page Object for the SaveToPlaylist dropdown on the watch page.

Encapsulates all interactions with the "Save to playlist" button and its
dropdown menu, exposing only high-level actions and state queries to callers.
Raw selectors never leak outside this class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
- This component reflects the SaveToPlaylist React component
  (web/src/components/SaveToPlaylist.tsx) rendered inside the watch page.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class SaveToPlaylistWidget:
    """Page Object for the SaveToPlaylist dropdown on the watch page (/v/:id)."""

    # Selectors — mirror the aria roles and labels in SaveToPlaylist.tsx
    _SAVE_BUTTON = 'button[aria-label="Save to playlist"]'
    _DROPDOWN = 'div[role="menu"]'
    _MENU_ITEM = 'button[role="menuitem"]'
    _LOADING_TEXT = 'div[role="menu"] p:has-text("Loading")'
    _SAVED_INDICATOR = 'span[aria-label="Saved"]'
    _ERROR_ALERT = 'div[role="menu"] p[role="alert"]'

    # Timeouts (ms)
    _AUTH_RESOLVE_TIMEOUT = 20_000   # Firebase auth resolves asynchronously
    _DROPDOWN_TIMEOUT = 10_000       # dropdown appears on click
    _LOADING_TIMEOUT = 10_000        # playlists fetch from API
    _SAVE_FEEDBACK_TIMEOUT = 5_000   # checkmark after successful save

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_save_button_visible(
        self, timeout: int = _AUTH_RESOLVE_TIMEOUT
    ) -> bool:
        """Return True when the 'Save to playlist' button is visible.

        The button is hidden while Firebase auth is resolving or when the user
        is not authenticated.  This method waits up to *timeout* ms for it to
        appear, which covers the Firebase auth resolution delay.
        """
        try:
            self._page.wait_for_selector(
                self._SAVE_BUTTON, state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def is_dropdown_visible(self) -> bool:
        """Return True if the dropdown menu is currently visible."""
        el = self._page.query_selector(self._DROPDOWN)
        return bool(el and el.is_visible())

    def get_playlist_titles(self) -> list[str]:
        """Return the text of every menu item currently shown in the dropdown.

        Includes both playlist items and the 'New playlist' entry.
        """
        items = self._page.query_selector_all(self._MENU_ITEM)
        return [(item.text_content() or "").strip() for item in items]

    def get_error_text(self) -> Optional[str]:
        """Return the error message shown inside the dropdown, or None."""
        el = self._page.query_selector(self._ERROR_ALERT)
        if el is None:
            return None
        return (el.text_content() or "").strip() or None

    def is_save_indicator_visible(self) -> bool:
        """Return True if the ✓ 'Saved' checkmark is currently visible."""
        el = self._page.query_selector(self._SAVED_INDICATOR)
        return bool(el and el.is_visible())

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def open_dropdown(self) -> None:
        """Wait for the Save button, click it, and wait for the dropdown to appear.

        Also waits for the loading spinner inside the dropdown to disappear so
        that playlist items are fully rendered before the caller proceeds.
        """
        self._page.wait_for_selector(
            self._SAVE_BUTTON, state="visible", timeout=self._AUTH_RESOLVE_TIMEOUT
        )
        self._page.click(self._SAVE_BUTTON)
        self._page.wait_for_selector(
            self._DROPDOWN, state="visible", timeout=self._DROPDOWN_TIMEOUT
        )
        # Wait for the loading indicator to disappear (playlists fetched from API)
        try:
            self._page.wait_for_selector(
                self._LOADING_TEXT, state="hidden", timeout=self._LOADING_TIMEOUT
            )
        except Exception:
            pass  # loading indicator may not appear if response is instant

    def click_playlist(self, title: str) -> None:
        """Click the menu item whose text contains *title*.

        Assumes the dropdown is already open (call ``open_dropdown`` first).
        """
        self._page.click(
            f'{self._DROPDOWN} {self._MENU_ITEM}:has-text("{title}")'
        )

    def wait_for_save_indicator(
        self, timeout: int = _SAVE_FEEDBACK_TIMEOUT
    ) -> bool:
        """Wait for the ✓ checkmark to appear; return True if it did."""
        try:
            self._page.wait_for_selector(
                self._SAVED_INDICATOR, state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    def wait_for_dropdown_close(self, timeout: int = 3_000) -> None:
        """Wait until the dropdown closes (e.g. after a successful save)."""
        self._page.wait_for_selector(
            self._DROPDOWN, state="hidden", timeout=timeout
        )
