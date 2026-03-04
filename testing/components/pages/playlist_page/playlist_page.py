"""PlaylistPage — Page Object for the /pl/:id public playlist page.

Encapsulates all interactions with the playlist page, exposing only
high-level state queries to callers.  Raw selectors never leak outside
this class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the base URL and playlist ID.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class PlaylistPage:
    """Page Object for the MyTube public playlist page (/pl/:id)."""

    # Selectors (pure CSS, no Playwright-specific text= engine in these constants)
    _QUEUE_ITEM = "button[aria-label^='Play ']"
    _PAGE_TITLE = "h1"

    _DEFAULT_LOAD_TIMEOUT = 15_000   # ms
    _QUEUE_VISIBLE_TIMEOUT = 20_000  # ms — wait for queue panel to appear

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, base_url: str, playlist_id: str) -> None:
        """Navigate to the public playlist page for *playlist_id*."""
        url = f"{base_url.rstrip('/')}/pl/{playlist_id}/"
        self._page.goto(url, wait_until="domcontentloaded")

    # ------------------------------------------------------------------
    # Loading / state detection
    # ------------------------------------------------------------------

    def wait_for_loaded(self, timeout: int = _QUEUE_VISIBLE_TIMEOUT) -> None:
        """Wait until the page exits the initial loading state.

        Considers the page "loaded" when one of the following appears:
        - The Queue heading (playlist with videos rendered successfully)
        - "Playlist not found." message (valid 404 from the API)
        - An error alert (API or network failure)
        """
        # Use Playwright's locator.or_() to combine multiple conditions cleanly.
        queue_heading = self._page.locator("h2:has-text('Queue')")
        not_found = self._page.locator("p:has-text('Playlist not found.')")
        error_alert = self._page.locator("[role='alert']")
        queue_heading.or_(not_found).or_(error_alert).first.wait_for(
            state="visible", timeout=timeout
        )

    def is_not_found(self) -> bool:
        """Return True if the 'Playlist not found.' state is visible."""
        return self._page.locator("p:has-text('Playlist not found.')").count() > 0

    def has_error(self) -> bool:
        """Return True if a non-empty error alert is visible on the page.

        The page always contains an empty [role='alert'] element used for
        live-region announcements; only a non-empty visible alert indicates
        an actual error state.
        """
        alerts = self._page.locator("[role='alert']").all()
        return any(
            a.is_visible() and bool((a.text_content() or "").strip())
            for a in alerts
        )

    def is_queue_visible(self) -> bool:
        """Return True if the Queue panel heading is visible."""
        return self._page.locator("h2:has-text('Queue')").count() > 0

    # ------------------------------------------------------------------
    # Queue queries
    # ------------------------------------------------------------------

    def get_page_title(self) -> Optional[str]:
        """Return the playlist title from the <h1> element, or None."""
        el = self._page.query_selector(self._PAGE_TITLE)
        return el.text_content().strip() if el else None

    def get_queue_item_count(self) -> int:
        """Return the number of video items rendered in the queue panel."""
        return self._page.locator(self._QUEUE_ITEM).count()

    def get_queue_item_titles(self) -> list[str]:
        """Return video titles from the queue in display order (top to bottom).

        Titles are extracted from the ``aria-label="Play {title}"`` attribute
        on each queue item button.
        """
        locator = self._page.locator(self._QUEUE_ITEM)
        count = locator.count()
        titles: list[str] = []
        for i in range(count):
            aria_label = locator.nth(i).get_attribute("aria-label") or ""
            # aria-label format is "Play {video.title}"
            title = aria_label.removeprefix("Play ").strip()
            titles.append(title)
        return titles

    def get_first_playing_item_title(self) -> Optional[str]:
        """Return the title of the queue item currently marked as playing.

        Uses ``aria-current="true"`` to identify the active item.
        """
        active = self._page.locator(f"{self._QUEUE_ITEM}[aria-current='true']")
        if active.count() == 0:
            return None
        aria_label = active.first.get_attribute("aria-label") or ""
        return aria_label.removeprefix("Play ").strip() or None
