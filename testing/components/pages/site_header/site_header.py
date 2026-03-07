"""SiteHeader — Page Object for the global site header component.

Encapsulates all interactions with the SiteHeader (logo, search, nav links)
shared across every page of the MyTube web application.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — callers supply the base URL when navigating.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from playwright.sync_api import Page


class SiteHeader:
    """Page Object for the MyTube site header rendered by SiteHeader.tsx.

    The header is present on every page and contains:
      - Logo link: <a href="/" class="…text-red-600…">mytube</a>
      - Search input and button
      - Primary navigation links (Home, Upload, My Videos, Playlists)
    """

    # Logo: the "mytube" branded link that always navigates to /
    _LOGO_LINK = "header a.text-red-600"

    def __init__(self, page: Page) -> None:
        self._page = page

    def click_logo(self) -> None:
        """Click the site logo link in the header."""
        self._page.locator(self._LOGO_LINK).first.click()

    def logo_is_visible(self) -> bool:
        """Return True if the logo link is visible in the header."""
        return self._page.locator(self._LOGO_LINK).first.is_visible()

    def logo_href(self) -> str:
        """Return the href attribute of the logo link."""
        return self._page.locator(self._LOGO_LINK).first.get_attribute("href") or ""

    def logo_text(self) -> str:
        """Return the text content of the logo link."""
        return self._page.locator(self._LOGO_LINK).first.inner_text().strip()
