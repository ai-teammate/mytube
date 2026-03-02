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
