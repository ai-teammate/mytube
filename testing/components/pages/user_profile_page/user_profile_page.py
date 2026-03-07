"""UserProfilePage — Page Object for /u/:username pages of the MyTube web application.

Encapsulates all interactions with the user profile page, exposing only
high-level state queries to callers.  Raw selectors never leak outside this
class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the base URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

import re
from typing import Optional

from playwright.sync_api import Page


class UserProfilePage:
    """Page Object for the MyTube public user profile page (/u/:username)."""

    _NOT_FOUND_TEXT = "User not found."
    _LOADING_TEXT = "Loading"

    # Selectors for profile content
    _USERNAME_HEADING = "h1"
    _AVATAR_IMAGE = "img[alt*=\"avatar\"]"
    _AVATAR_INITIALS = "[aria-label*=\"avatar\"]"
    _VIDEO_CARD = "a[href*='/v/']"
    _LOADING_SPINNER = "text=Loading\u2026"  # "Loading…"

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, base_url: str, username: str) -> None:
        """Navigate to /u/<username> and wait for the loading spinner to disappear."""
        url = f"{base_url.rstrip('/')}/u/{username}"
        self._page.goto(url)
        try:
            self._page.wait_for_selector(self._LOADING_SPINNER, state="hidden", timeout=15_000)
        except Exception:
            pass  # spinner already gone or never appeared

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_not_found(self, timeout: float = 10_000) -> bool:
        """Return True when the 'User not found.' message is visible."""
        locator = self._page.get_by_text(self._NOT_FOUND_TEXT, exact=True)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def is_loading(self) -> bool:
        """Return True when the loading indicator is visible."""
        return self._page.get_by_text(self._LOADING_TEXT).count() > 0

    def get_not_found_text(self) -> str | None:
        """Return the text content of the not-found paragraph, or None."""
        locator = self._page.get_by_text(self._NOT_FOUND_TEXT, exact=True)
        if locator.count() == 0:
            return None
        return locator.text_content()

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    # ------------------------------------------------------------------
    # Profile content queries
    # ------------------------------------------------------------------

    def get_username_heading(self) -> Optional[str]:
        """Return the text content of the <h1> username heading, or None."""
        el = self._page.query_selector(self._USERNAME_HEADING)
        if el is None:
            return None
        return (el.text_content() or "").strip()

    def is_avatar_visible(self) -> bool:
        """Return True if the avatar element (image or initials div) is visible."""
        img = self._page.query_selector(self._AVATAR_IMAGE)
        if img and img.is_visible():
            return True
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
        pattern = re.compile(r"^(/[^/]+)?/v/.+")
        hrefs = self.get_video_hrefs()
        if not hrefs:
            return False
        return all(pattern.match(href) for href in hrefs)

    # ------------------------------------------------------------------
    # Error state queries
    # ------------------------------------------------------------------

    _ERROR_MESSAGE = "Could not load profile. Please try again later."
    _ERROR_ROLE = "alert"

    def is_error_visible(self, timeout: float = 15_000) -> bool:
        """Return True when the profile-load-failure error message is visible."""
        locator = self._page.get_by_role(self._ERROR_ROLE).first
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def get_error_message(self) -> str | None:
        """Return the text content of the [role=alert] error element, or None."""
        locator = self._page.get_by_role(self._ERROR_ROLE)
        if locator.count() == 0:
            return None
        return (locator.first.text_content() or "").strip()

    # ------------------------------------------------------------------
    # Event monitoring
    # ------------------------------------------------------------------

    def listen_for_js_errors(self) -> list[str]:
        """Attach a pageerror listener and return the shared errors list."""
        errors: list[str] = []
        self._page.on("pageerror", lambda err: errors.append(str(err)))
        return errors
