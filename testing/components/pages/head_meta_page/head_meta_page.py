"""HeadMetaPage — Page Object for HTML ``<head>`` metadata inspection.

Encapsulates all DOM interactions with ``<link>`` and ``<meta>`` tags inside
the document ``<head>``.  Raw Playwright locators never leak outside this class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — callers provide the full URL for navigation.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from playwright.sync_api import Page


class HeadMetaPage:
    """Page Object for inspecting ``<head>`` metadata (favicon and Open Graph tags)."""

    _PAGE_LOAD_TIMEOUT = 30_000  # ms

    # Selectors
    _FAVICON_ICON = "link[rel='icon']"
    _FAVICON_SHORTCUT = "link[rel='shortcut icon']"
    _OG_IMAGE = "meta[property='og:image']"

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to(self, url: str) -> None:
        """Navigate to *url* and wait until DOM content is loaded."""
        self._page.goto(url, wait_until="domcontentloaded", timeout=self._PAGE_LOAD_TIMEOUT)

    # ------------------------------------------------------------------
    # Favicon
    # ------------------------------------------------------------------

    def get_favicon_href(self) -> str | None:
        """Return the ``href`` of the first ``<link rel='icon'>`` in the document head.

        Falls back to ``<link rel='shortcut icon'>`` when no ``rel='icon'`` is found.
        Returns ``None`` if neither tag is present.
        """
        loc = self._page.locator(self._FAVICON_ICON)
        if loc.count() == 0:
            loc = self._page.locator(self._FAVICON_SHORTCUT)
        if loc.count() == 0:
            return None
        return loc.first.get_attribute("href")

    # ------------------------------------------------------------------
    # Open Graph
    # ------------------------------------------------------------------

    def get_og_image_content(self) -> str | None:
        """Return the ``content`` of ``<meta property='og:image'>``.

        Returns ``None`` if the tag is absent.
        """
        loc = self._page.locator(self._OG_IMAGE)
        if loc.count() == 0:
            return None
        return loc.first.get_attribute("content")
