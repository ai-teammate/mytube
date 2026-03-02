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
from playwright.sync_api import Page


class WatchPage:
    """Page Object for the MyTube video watch page (/v/:id)."""

    _LOADING_TEXT = "Loading"
    _NOT_FOUND_TEXT = "Video not found."
    _DEFAULT_LOAD_TIMEOUT = 15_000  # ms

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_video(self, base_url: str, video_id: str) -> None:
        """Navigate to the watch page for *video_id* and wait for DOM load."""
        url = f"{base_url.rstrip('/')}/v/{video_id}"
        self._page.goto(url, wait_until="domcontentloaded")

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

    def is_not_found(self, timeout: float = _DEFAULT_LOAD_TIMEOUT) -> bool:
        """Return True when the 'Video not found.' message is visible."""
        locator = self._page.get_by_text(self._NOT_FOUND_TEXT, exact=True)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url
