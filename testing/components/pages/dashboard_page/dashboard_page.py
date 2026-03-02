"""DashboardPage — Page Object for the /dashboard page of the MyTube web application.

Encapsulates all interactions with the video management dashboard, exposing
only high-level actions and state queries to callers.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the full dashboard URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class DashboardPage:
    """Page Object for the MyTube video management dashboard at /dashboard."""

    # Selectors — these reflect the expected dashboard UI
    _HEADING = "h1"
    _VIDEO_LIST_ITEM = "[data-testid='video-item'], .video-item, [class*='video']"
    _PROCESSING_STATUS = "text=Processing"
    _NOT_FOUND = "text=404"

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> None:
        """Navigate to the dashboard URL and wait for page to load."""
        self._page.goto(url, wait_until="domcontentloaded")
        self._page.wait_for_load_state("networkidle", timeout=15_000)

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def is_on_dashboard(self) -> bool:
        """Return True if the current URL contains /dashboard."""
        return "/dashboard" in self._page.url

    def get_page_title(self) -> Optional[str]:
        """Return the text of the page <h1> heading, or None."""
        heading = self._page.locator(self._HEADING)
        if heading.count() == 0:
            return None
        return (heading.first.text_content() or "").strip()

    def has_processing_status(self, timeout: int = 5_000) -> bool:
        """Return True if any element showing 'Processing' status is visible."""
        try:
            self._page.wait_for_selector(self._PROCESSING_STATUS, timeout=timeout)
            return True
        except Exception:
            return False

    def has_video_with_id(self, video_id: str) -> bool:
        """Return True if any element containing *video_id* is present on the page."""
        try:
            self._page.wait_for_selector(f"text={video_id}", timeout=3_000)
            return True
        except Exception:
            # Also check page source for the video ID
            return video_id in self._page.content()

    def is_404_page(self) -> bool:
        """Return True if the page shows a 404 not-found indicator."""
        content = self._page.content().lower()
        url = self._page.url
        return "404" in content or "not found" in content or "page not found" in content

    def get_uploaded_video_id_from_url(self) -> Optional[str]:
        """Extract the ?uploaded=<videoId> query param from the current URL."""
        import urllib.parse
        parsed = urllib.parse.urlparse(self._page.url)
        params = urllib.parse.parse_qs(parsed.query)
        values = params.get("uploaded", [])
        return values[0] if values else None

    def wait_for_load(self, timeout: int = 15_000) -> None:
        """Wait for the dashboard content to load."""
        self._page.wait_for_load_state("networkidle", timeout=timeout)
