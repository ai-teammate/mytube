"""Page Object for the video watch page (/v/<id>)."""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class WatchPage:
    """Encapsulates interactions with the video watch page at /v/<id>.

    The watch page fetches video data client-side and sets OG meta tags
    in the DOM once the video has loaded.

    Usage
    -----
    page_obj = WatchPage(page)
    page_obj.navigate(base_url, video_id)
    assert page_obj.get_og_title() == "My Video Title"
    assert page_obj.get_og_image() is not None
    """

    # Selectors
    _LOADING_TEXT = "text=Loading…"
    _TITLE_HEADING = "h1"
    _NOT_FOUND_TEXT = "text=Video not found."
    _ERROR_ALERT = "[role='alert']"

    # Timeout for video data to load and OG tags to be set (ms)
    _OG_TAG_TIMEOUT = 15_000

    def __init__(self, page: Page) -> None:
        self._page = page

    # -----------------------------------------------------------------
    # Navigation
    # -----------------------------------------------------------------

    def navigate(self, base_url: str, video_id: str) -> None:
        """Navigate to /v/<video_id> and wait for the video to load."""
        url = f"{base_url.rstrip('/')}/v/{video_id}/"
        self._page.goto(url)
        # Wait for loading spinner to disappear — video data has loaded
        self._page.wait_for_selector(self._LOADING_TEXT, state="hidden", timeout=self._OG_TAG_TIMEOUT)

    # -----------------------------------------------------------------
    # OG Meta Tag Queries
    # -----------------------------------------------------------------

    def get_og_title(self) -> Optional[str]:
        """Return the content of <meta property="og:title">, or None if absent."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('meta[property="og:title"]');
                return el ? el.getAttribute('content') : null;
            }"""
        )

    def get_og_image(self) -> Optional[str]:
        """Return the content of <meta property="og:image">, or None if absent."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('meta[property="og:image"]');
                return el ? el.getAttribute('content') : null;
            }"""
        )

    # -----------------------------------------------------------------
    # Page State Queries
    # -----------------------------------------------------------------

    def get_title_heading(self) -> Optional[str]:
        """Return the text content of the <h1> video title heading, or None."""
        el = self._page.query_selector(self._TITLE_HEADING)
        if el is None:
            return None
        return (el.text_content() or "").strip()

    def is_not_found(self) -> bool:
        """Return True if 'Video not found.' is displayed."""
        return self._page.locator(self._NOT_FOUND_TEXT).count() > 0

    def is_error_displayed(self) -> bool:
        """Return True if an error alert is visible."""
        el = self._page.query_selector(self._ERROR_ALERT)
        return bool(el and el.is_visible())

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def get_page_title(self) -> str:
        """Return the document.title value."""
        return self._page.title()
