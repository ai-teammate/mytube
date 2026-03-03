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

import re
from typing import Optional

from playwright.sync_api import Page


class DashboardPage:
    """Page Object for the MyTube video management dashboard at /dashboard."""

    # Selectors — these reflect the expected dashboard UI
    _HEADING = "h1"
    _VIDEO_LIST_ITEM = "[data-testid='video-item'], .video-item, [class*='video']"
    _PROCESSING_STATUS = "text=Processing"
    _NOT_FOUND = "text=404"
    _TABLE = "table"
    _TABLE_ROWS = "table tbody tr"
    _UPLOAD_CTA_TEXT = "Upload new video"
    _UPLOAD_CTA_LINK = "a[href*='upload']"

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

    # ------------------------------------------------------------------
    # Table inspection — video list
    # ------------------------------------------------------------------

    def wait_for_videos_table(self, timeout: int = 20_000) -> None:
        """Wait until at least one video row is visible in the table body."""
        self._page.wait_for_selector(self._TABLE_ROWS, timeout=timeout)

    def is_table_visible(self) -> bool:
        """Return True if the video <table> element is present in the DOM."""
        return self._page.locator(self._TABLE).count() > 0

    def get_row_count(self) -> int:
        """Return the number of video rows currently visible in the table body."""
        return self._page.locator(self._TABLE_ROWS).count()

    def get_all_titles(self) -> list[str]:
        """Return a list of all video title strings from the table body rows.

        The title is taken from the second ``<td>`` of each row, which may
        contain a plain-text string or a ``<a>`` link element.
        """
        rows = self._page.locator(self._TABLE_ROWS)
        count = rows.count()
        titles: list[str] = []
        for i in range(count):
            cell = rows.nth(i).locator("td:nth-child(2)")
            text = (cell.text_content() or "").strip()
            titles.append(text)
        return titles

    def get_status_badge_for_title(self, title: str) -> Optional[str]:
        """Return the status badge text for the first row whose title contains *title*.

        The badge is the ``<span>`` inside the third ``<td>`` of each row.
        Returns None if no row matches or the badge element is absent.
        """
        rows = self._page.locator(self._TABLE_ROWS).filter(has_text=title)
        if rows.count() == 0:
            return None
        badge = rows.first.locator("td:nth-child(3) span")
        if badge.count() == 0:
            return None
        return (badge.text_content() or "").strip()

    def get_view_count_for_title(self, title: str) -> Optional[str]:
        """Return the formatted view count text for the first row matching *title*.

        The view count is the text of the fourth ``<td>`` (right-aligned).
        Returns None if no row matches or the cell is absent.
        """
        rows = self._page.locator(self._TABLE_ROWS).filter(has_text=title)
        if rows.count() == 0:
            return None
        cell = rows.first.locator("td:nth-child(4)")
        if cell.count() == 0:
            return None
        return (cell.text_content() or "").strip()

    def get_creation_date_for_title(self, title: str) -> Optional[str]:
        """Return the creation date text for the first row matching *title*.

        The date is the text of the fifth ``<td>``, formatted by
        ``new Date(createdAt).toLocaleDateString()`` on the frontend.
        Returns None if no row matches or the cell is absent.
        """
        rows = self._page.locator(self._TABLE_ROWS).filter(has_text=title)
        if rows.count() == 0:
            return None
        cell = rows.first.locator("td:nth-child(5)")
        if cell.count() == 0:
            return None
        return (cell.text_content() or "").strip()

    def has_thumbnail_element_for_title(self, title: str) -> bool:
        """Return True if the thumbnail cell for the first row matching *title*
        contains an ``<img>`` (real thumbnail) or a placeholder ``<div>``.
        """
        rows = self._page.locator(self._TABLE_ROWS).filter(has_text=title)
        if rows.count() == 0:
            return False
        thumb_cell = rows.first.locator("td:nth-child(1)")
        if thumb_cell.count() == 0:
            return False
        return (
            thumb_cell.locator("img").count() > 0
            or thumb_cell.locator("div").count() > 0
        )

    # ------------------------------------------------------------------
    # Upload CTA actions
    # ------------------------------------------------------------------

    def is_upload_cta_visible(self, timeout: int = 5_000) -> bool:
        """Return True if the 'Upload new video' CTA is visible on the dashboard."""
        try:
            self._page.wait_for_selector(
                f"text={self._UPLOAD_CTA_TEXT}", timeout=timeout
            )
            return True
        except Exception:
            try:
                self._page.wait_for_selector(self._UPLOAD_CTA_LINK, timeout=1_000)
                return True
            except Exception:
                return False

    def click_upload_new_video_cta(self) -> None:
        """Click the 'Upload new video' call-to-action on the dashboard.

        Uses Playwright's built-in navigation handling to wait for the URL to
        change after the click, avoiding race conditions with SPA routing.
        """
        cta = self._page.locator(f"text={self._UPLOAD_CTA_TEXT}").first
        if cta.count() > 0 and cta.is_visible():
            cta.click()
        else:
            self._page.locator(self._UPLOAD_CTA_LINK).first.click()
        # Wait for the URL to change away from /dashboard/
        self._page.wait_for_url(lambda url: "/upload" in url, timeout=15_000)

    # ------------------------------------------------------------------
    # Status badge inspection
    # ------------------------------------------------------------------

    def has_status_badge(self, status: str, timeout: int = 5_000) -> bool:
        """Return True if a status badge with the given text is visible.

        Matches span elements whose entire text content (ignoring surrounding
        whitespace) equals *status*.  Works with both the production app
        (Tailwind-styled spans) and fixture HTML (inline-styled spans).
        """
        badge = self._page.locator("span").filter(
            has_text=re.compile(rf"^\s*{re.escape(status)}\s*$")
        )
        try:
            badge.first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def get_status_badge_class(self, status: str) -> Optional[str]:
        """Return the CSS class string of the first badge with the given status text.

        Returns None when no matching badge is found.
        """
        badge = self._page.locator("span").filter(
            has_text=re.compile(rf"^\s*{re.escape(status)}\s*$")
        )
        if badge.count() == 0:
            return None
        return badge.first.get_attribute("class")
