"""WatchPage — Page Object for the /v/:id watch page of the MyTube web application.

Encapsulates all interactions with the video watch page, exposing only
high-level state queries to callers.  Raw selectors never leak outside this
class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the base URL and video ID.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class WatchPage:
    """Page Object for the MyTube video watch page (/v/:id)."""

    # Selectors
    _LOADING_TEXT = "Loading"
    _TITLE_HEADING = "h1"
    _NOT_FOUND_TEXT = "Video not found."
    _ERROR_ALERT = "[role='alert']"

    _DEFAULT_LOAD_TIMEOUT = 15_000  # ms
    # Timeout for video data to load and OG tags to be set (ms)
    _OG_TAG_TIMEOUT = 15_000

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_video(self, base_url: str, video_id: str) -> None:
        """Navigate to the watch page for *video_id* and wait for DOM load."""
        url = f"{base_url.rstrip('/')}/v/{video_id}"
        self._page.goto(url, wait_until="domcontentloaded")

    def navigate(self, base_url: str, video_id: str) -> None:
        """Navigate to /v/<video_id> and wait for the video to load."""
        url = f"{base_url.rstrip('/')}/v/{video_id}/"
        self._page.goto(url)
        # Wait for loading spinner to disappear — video data has loaded
        self._page.wait_for_selector(
            f"text={self._LOADING_TEXT}", state="hidden", timeout=self._OG_TAG_TIMEOUT
        )

    # ------------------------------------------------------------------
    # Wait helpers
    # ------------------------------------------------------------------

    def wait_for_metadata(self, timeout: float = _DEFAULT_LOAD_TIMEOUT) -> None:
        """Wait until the loading indicator disappears and the h1 title is visible."""
        # Wait for the loading spinner to go away
        loading = self._page.get_by_text(self._LOADING_TEXT)
        try:
            loading.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass  # loading indicator may not appear at all
        # Then wait for the h1 title element to be present
        self._page.locator("h1").wait_for(state="visible", timeout=timeout)

    # ------------------------------------------------------------------
    # State queries — metadata
    # ------------------------------------------------------------------

    def get_title(self) -> str | None:
        """Return the visible video title (h1 text), or None if not present."""
        locator = self._page.locator("h1")
        if locator.count() == 0:
            return None
        return locator.text_content()

    def get_title_heading(self) -> Optional[str]:
        """Return the text content of the <h1> video title heading, or None."""
        el = self._page.query_selector(self._TITLE_HEADING)
        if el is None:
            return None
        return (el.text_content() or "").strip()

    def get_description(self) -> str | None:
        """Return the video description text, or None if not displayed."""
        # Description is rendered in a div with whitespace-pre-wrap class
        locator = self._page.locator("div.whitespace-pre-wrap")
        if locator.count() == 0:
            return None
        text = locator.text_content()
        return text if text else None

    def get_tags(self) -> list[str]:
        """Return a list of tag chip texts shown on the page."""
        # Tags are rendered as <span> elements with rounded-full class inside the tags row
        locator = self._page.locator("span.rounded-full")
        count = locator.count()
        return [locator.nth(i).text_content().strip() for i in range(count)]

    def get_uploader_username(self) -> str | None:
        """Return the uploader username link text, or None if not present."""
        # The uploader link is an <a> with href starting with /u/
        locator = self._page.locator('a[href^="/u/"]')
        if locator.count() == 0:
            return None
        return locator.text_content()

    def get_uploader_href(self) -> str | None:
        """Return the href attribute of the uploader link, or None if not present."""
        locator = self._page.locator('a[href^="/u/"]')
        if locator.count() == 0:
            return None
        return locator.get_attribute("href")

    def click_uploader_link(self) -> None:
        """Click the uploader name link."""
        self._page.locator('a[href^="/u/"]').click()

    # ------------------------------------------------------------------
    # OG Meta Tag Queries
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Page State Queries
    # ------------------------------------------------------------------

    def is_not_found(self, timeout: float = _DEFAULT_LOAD_TIMEOUT) -> bool:
        """Return True when the 'Video not found.' message is visible."""
        locator = self._page.get_by_text(self._NOT_FOUND_TEXT, exact=True)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def is_error_displayed(self) -> bool:
        """Return True if an error alert is visible."""
        el = self._page.query_selector(self._ERROR_ALERT)
        return bool(el and el.is_visible())

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def get_page_title(self) -> str:
        """Return the document.title value."""
        return self._page.title()
