"""Page Object for the public user profile page (/u/<username>)."""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class ProfilePage:
    """Encapsulates interactions with the public user profile page.

    The profile page at /u/<username> displays:
    - The user's avatar (image or initials fallback)
    - The user's username as an <h1>
    - A grid of video cards, each linking to /v/<id>

    Usage
    -----
    page_obj = ProfilePage(page)
    page_obj.navigate(base_url, "tester")
    assert page_obj.get_username_heading() == "tester"
    """

    # -----------------------------------------------------------------
    # Selectors
    # -----------------------------------------------------------------
    _USERNAME_HEADING = "h1"
    # Avatar image rendered by Next.js <Image> — has a meaningful alt attribute
    _AVATAR_IMAGE = "img[alt*=\"avatar\"]"
    # Initials-fallback div carries the same aria-label pattern
    _AVATAR_INITIALS = "[aria-label*=\"avatar\"]"
    # Each video card is an <a> whose href starts with /v/
    _VIDEO_CARD = "a[href^='/v/']"
    _LOADING_TEXT = "text=Loading…"

    def __init__(self, page: Page) -> None:
        self._page = page

    # -----------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------

    def navigate(self, base_url: str, username: str) -> None:
        """Navigate to /u/<username> and wait for the page to settle."""
        url = f"{base_url.rstrip('/')}/u/{username}"
        self._page.goto(url)
        # Wait until the loading spinner disappears — profile data has loaded
        self._page.wait_for_selector(self._LOADING_TEXT, state="hidden", timeout=15_000)

    # -----------------------------------------------------------------
    # Queries
    # -----------------------------------------------------------------

    def get_username_heading(self) -> Optional[str]:
        """Return the text content of the <h1> username heading, or None."""
        el = self._page.query_selector(self._USERNAME_HEADING)
        if el is None:
            return None
        return (el.text_content() or "").strip()

    def is_avatar_visible(self) -> bool:
        """Return True if the avatar element (image or initials div) is visible."""
        # Try image avatar first
        img = self._page.query_selector(self._AVATAR_IMAGE)
        if img and img.is_visible():
            return True
        # Fall back to initials div
        div = self._page.query_selector(self._AVATAR_INITIALS)
        return bool(div and div.is_visible())

    def get_video_card_count(self) -> int:
        """Return the number of video cards visible in the grid."""
        return len(self._page.query_selector_all(self._VIDEO_CARD))

    def get_video_hrefs(self) -> list[str]:
        """Return the href values for all video cards on the page."""
        cards = self._page.query_selector_all(self._VIDEO_CARD)
        hrefs: list[str] = []
        for card in cards:
            href = card.get_attribute("href") or ""
            if href:
                hrefs.append(href)
        return hrefs

    def all_video_hrefs_match_pattern(self) -> bool:
        """Return True if every video card href matches the /v/<id> pattern."""
        import re
        pattern = re.compile(r"^/v/.+")
        hrefs = self.get_video_hrefs()
        if not hrefs:
            return False
        return all(pattern.match(href) for href in hrefs)

    def is_not_found(self) -> bool:
        """Return True if the 'User not found.' message is displayed."""
        return self._page.locator("text=User not found.").count() > 0

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    # -----------------------------------------------------------------
    # Playlists tab
    # -----------------------------------------------------------------

    _PLAYLISTS_TAB_BTN = "nav button:has-text('Playlists')"
    _PLAYLIST_CARD = "a[href^='/pl/']"
    _PLAYLISTS_LOADING = "text=Loading playlists…"
    _NO_PLAYLISTS = "text=No playlists yet."

    def click_playlists_tab(self) -> None:
        """Click the 'Playlists' tab button to activate the playlists view."""
        self._page.click(self._PLAYLISTS_TAB_BTN)

    def wait_for_playlists_loaded(self, timeout: int = 15_000) -> None:
        """Wait until the 'Loading playlists…' spinner disappears."""
        try:
            self._page.wait_for_selector(
                self._PLAYLISTS_LOADING, state="hidden", timeout=timeout
            )
        except Exception:
            pass  # spinner already gone or never appeared

    def get_playlist_card_count(self) -> int:
        """Return the number of playlist cards currently in the DOM."""
        return len(self._page.query_selector_all(self._PLAYLIST_CARD))

    def get_playlist_hrefs(self) -> list[str]:
        """Return the href attribute of every playlist card."""
        cards = self._page.query_selector_all(self._PLAYLIST_CARD)
        hrefs: list[str] = []
        for card in cards:
            href = card.get_attribute("href") or ""
            if href:
                hrefs.append(href)
        return hrefs

    def get_playlist_cards_data(self) -> list[dict]:
        """Return structured data (href, title, subtitle) for each playlist card.

        ``subtitle`` is the text below the title inside each card.
        Per the ticket spec this should be the video count (e.g. '3 videos'),
        but the current implementation renders the creation date instead.
        """
        cards = self._page.query_selector_all(self._PLAYLIST_CARD)
        result: list[dict] = []
        for card in cards:
            href = card.get_attribute("href") or ""
            paragraphs = card.query_selector_all("p")
            title = (paragraphs[0].text_content() or "").strip() if paragraphs else ""
            subtitle = (
                (paragraphs[1].text_content() or "").strip()
                if len(paragraphs) > 1
                else ""
            )
            result.append({"href": href, "title": title, "subtitle": subtitle})
        return result

    def all_playlist_hrefs_match_pattern(self) -> bool:
        """Return True if every playlist card href matches /pl/<id>."""
        import re
        pattern = re.compile(r"^/pl/.+")
        hrefs = self.get_playlist_hrefs()
        if not hrefs:
            return False
        return all(pattern.match(href) for href in hrefs)

    def has_no_playlists_message(self) -> bool:
        """Return True when 'No playlists yet.' is visible on the playlists tab."""
        return self._page.locator("text=No playlists yet.").count() > 0

    def is_playlists_tab_visible(self) -> bool:
        """Return True if the 'Playlists' tab button is present in the navigation."""
        return self._page.locator(self._PLAYLISTS_TAB_BTN).count() > 0

    def is_videos_tab_visible(self) -> bool:
        """Return True if the 'Videos' tab button is present in the navigation."""
        return self._page.locator("nav button:has-text('Videos')").count() > 0

    def is_playlists_still_loading(self) -> bool:
        """Return True if the playlists loading spinner is still visible."""
        return self._page.locator(self._PLAYLISTS_LOADING).count() > 0

    def has_react_error_boundary(self) -> bool:
        """Return True if an unhandled React error boundary is rendered."""
        boundary_selectors = [
            "text=Something went wrong",
            "text=Unexpected Application Error",
        ]
        return any(self._page.locator(s).count() > 0 for s in boundary_selectors)

    def has_playlists_graceful_error_message(self) -> bool:
        """Return True if a graceful error or fallback message is visible in the playlists section."""
        graceful_selectors = [
            "text=Failed to load",
            "text=Error loading",
            "text=Unable to load",
            "text=Could not load",
            "[role='alert']",
        ]
        return any(self._page.locator(s).count() > 0 for s in graceful_selectors)
