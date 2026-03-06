"""ProfilePage — extends UserProfilePage with playlist-tab interactions."""
from __future__ import annotations

from playwright.sync_api import Page

from testing.components.pages.user_profile_page.user_profile_page import UserProfilePage


class ProfilePage(UserProfilePage):
    """Extends UserProfilePage with methods for the Playlists tab."""

    _PLAYLIST_CARD = "a[href^='/pl/']"
    _PLAYLISTS_TAB_BUTTON = "button:has-text('Playlists')"

    def __init__(self, page: Page) -> None:
        super().__init__(page)

    def click_playlists_tab(self) -> None:
        """Click the Playlists tab button."""
        btn = self._page.locator(self._PLAYLISTS_TAB_BUTTON)
        if btn.count() > 0:
            btn.first.click()

    def wait_for_playlists_loaded(self, timeout: float = 10_000) -> None:
        """Wait until at least one playlist card is visible, or timeout passes."""
        try:
            self._page.wait_for_selector(self._PLAYLIST_CARD, timeout=timeout)
        except Exception:
            pass

    def get_playlist_card_count(self) -> int:
        """Return the number of playlist cards visible."""
        return self._page.locator(self._PLAYLIST_CARD).count()

    def get_playlist_cards_data(self) -> list[dict]:
        """Return a list of dicts with 'title', 'subtitle', and 'href' for each card."""
        cards = self._page.locator(self._PLAYLIST_CARD).all()
        result = []
        for card in cards:
            href = card.get_attribute("href") or ""
            paragraphs = card.locator("p").all()
            title = paragraphs[0].text_content().strip() if len(paragraphs) > 0 else ""
            subtitle = paragraphs[1].text_content().strip() if len(paragraphs) > 1 else ""
            result.append({"title": title, "subtitle": subtitle, "href": href})
        return result

    def get_playlist_hrefs(self) -> list[str]:
        """Return the href attributes of all playlist cards."""
        cards = self._page.locator(self._PLAYLIST_CARD).all()
        return [card.get_attribute("href") or "" for card in cards]
