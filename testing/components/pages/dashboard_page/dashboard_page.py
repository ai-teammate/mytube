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

from playwright.sync_api import Page, expect


class DashboardPage:
    """Page Object for the MyTube video management dashboard at /dashboard."""

    # Selectors — these reflect the expected dashboard UI
    _HEADING = "h1"
    _VIDEO_LIST_ITEM = "[data-testid='video-item'], .video-item, [class*='video']"
    _PROCESSING_STATUS = "text=Processing"
    _NOT_FOUND = "text=404"
    _TABLE = "table"
    _TABLE_ROWS = "table tbody tr"
    _UPLOAD_CTA_TEXT = "Upload your first video"
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
        """Return True if the page visibly displays a 404 not-found error.

        Uses DOM-based locators to avoid false positives from Next.js RSC JSON
        payloads that embed a 404 component on every page.
        """
        four_oh_four = self._page.locator("text=404").count()
        not_found = self._page.locator("text=page could not be found").count()
        return four_oh_four > 0 or not_found > 0

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
    # Video table queries
    # ------------------------------------------------------------------

    def get_video_row_count(self) -> int:
        """Return the number of video rows in the dashboard table (0 if no table)."""
        return self._page.locator("table tbody tr").count()

    def is_video_visible_by_title(self, title: str, timeout: int = 3_000) -> bool:
        """Return True if a table row containing *title* is visible."""
        try:
            row = self._page.locator("table tbody tr").filter(has_text=title).first
            row.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def wait_for_video_to_disappear(self, title: str, timeout: int = 5_000) -> None:
        """Wait until no table row containing *title* remains in the DOM."""
        locator = self._page.locator("table tbody tr").filter(has_text=title)
        expect(locator).to_have_count(0, timeout=timeout)

    # ------------------------------------------------------------------
    # Delete flow actions & state queries
    # ------------------------------------------------------------------

    def is_delete_button_visible(self, video_title: str, timeout: int = 3_000) -> bool:
        """Return True if the Delete button for *video_title* is visible.

        The button carries ``aria-label="Delete <video_title>"``.
        """
        try:
            btn = self._page.get_by_role(
                "button", name=f"Delete {video_title}", exact=True
            )
            btn.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def click_delete_button(self, video_title: str) -> None:
        """Click the Delete button for the video with *video_title*."""
        self._page.get_by_role(
            "button", name=f"Delete {video_title}", exact=True
        ).click()

    def is_confirm_delete_button_visible(self, timeout: int = 3_000) -> bool:
        """Return True if the inline Confirm button (deletion confirmation) is visible."""
        try:
            self._page.get_by_role(
                "button", name="Confirm", exact=True
            ).wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def is_cancel_delete_button_visible(self, timeout: int = 3_000) -> bool:
        """Return True if the inline Cancel button (deletion confirmation) is visible."""
        try:
            self._page.get_by_role(
                "button", name="Cancel", exact=True
            ).wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def click_confirm_delete(self) -> None:
        """Click the Confirm button to confirm video deletion."""
        self._page.get_by_role("button", name="Confirm", exact=True).click()

    def click_cancel_delete(self) -> None:
        """Click the Cancel button to dismiss the deletion confirmation."""
        self._page.get_by_role("button", name="Cancel", exact=True).click()

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
    # CSS grid inspection (MYTUBE-522)
    # ------------------------------------------------------------------

    _VIDEO_GRID = '[data-testid="video-grid"]'
    _DASHBOARD_TOOLBAR = '[data-testid="dashboard-toolbar"]'

    def is_video_grid_present(self) -> bool:
        """Return True if the video grid container is present in the DOM."""
        return self._page.locator(self._VIDEO_GRID).count() > 0

    def wait_for_video_grid_visible(self, timeout: int = 5_000) -> None:
        """Wait until the video grid container is visible."""
        self._page.locator(self._VIDEO_GRID).first.wait_for(
            state="visible", timeout=timeout
        )

    def is_toolbar_present(self) -> bool:
        """Return True if the dashboard toolbar is present in the DOM."""
        return self._page.locator(self._DASHBOARD_TOOLBAR).count() > 0

    def get_video_grid_styles(self) -> dict | None:
        """Return authored gridTemplateColumns and computed gap for the video grid.

        Scans loaded stylesheets for the rule matching the video grid element so
        that ``grid-template-columns`` is returned as the authored value rather
        than the resolved pixel string from ``getComputedStyle``.
        """
        return self._page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                const cs = window.getComputedStyle(el);
                const computedGap = cs.gap || cs.rowGap || '';
                let authoredGtc = '';
                for (const sheet of document.styleSheets) {
                    let rules;
                    try { rules = sheet.cssRules || sheet.rules; } catch (e) { continue; }
                    if (!rules) continue;
                    for (const rule of rules) {
                        if (!(rule instanceof CSSStyleRule)) continue;
                        try {
                            if (el.matches(rule.selectorText)) {
                                const gtc = rule.style.gridTemplateColumns;
                                if (gtc) { authoredGtc = gtc; }
                            }
                        } catch (e) {}
                    }
                }
                return { gridTemplateColumns: authoredGtc, gap: computedGap };
            }""",
            self._VIDEO_GRID,
        )

    def get_live_grid_rule(self) -> dict | None:
        """Scan all loaded document.styleSheets for the video grid CSS rule.

        Returns a dict with ``gridTemplateColumns`` and ``gap`` if a rule
        containing ``repeat(auto-fill, minmax(220px, ...))`` is found, or None.
        """
        return self._page.evaluate(
            """() => {
                for (const sheet of document.styleSheets) {
                    let rules;
                    try {
                        rules = sheet.cssRules || sheet.rules;
                    } catch (e) {
                        continue;
                    }
                    if (!rules) continue;
                    for (const rule of rules) {
                        if (!(rule instanceof CSSStyleRule)) continue;
                        const gtc = rule.style.gridTemplateColumns;
                        if (
                            gtc &&
                            gtc.includes('auto-fill') &&
                            gtc.includes('220px')
                        ) {
                            return {
                                gridTemplateColumns: gtc,
                                gap: rule.style.gap || rule.style.rowGap || ''
                            };
                        }
                    }
                }
                return null;
            }"""
        )

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

    # ------------------------------------------------------------------
    # Playlist chip interactions (card-grid layout)
    # ------------------------------------------------------------------

    _PLAYLIST_CHIP_GROUP = '[role="group"][aria-label="Filter by playlist"]'
    _VIDEO_GRID = "[class*='videoGrid']"

    def wait_for_playlist_chips(self, timeout: int = 15_000) -> None:
        """Wait until the playlist chip row is visible."""
        self._page.wait_for_selector(self._PLAYLIST_CHIP_GROUP, timeout=timeout)

    def click_playlist_chip(self, playlist_name: str) -> None:
        """Click the playlist filter chip with the given *playlist_name*."""
        chip = self._page.locator(self._PLAYLIST_CHIP_GROUP).get_by_role(
            "button", name=playlist_name, exact=True
        )
        chip.click()

    def click_all_chip(self) -> None:
        """Click the 'All' filter chip to reset the playlist filter."""
        chip = self._page.locator(self._PLAYLIST_CHIP_GROUP).get_by_role(
            "button", name="All", exact=True
        )
        chip.click()

    def get_video_card_count(self, timeout: int = 5_000) -> int:
        """Return the number of video cards currently visible in the card grid."""
        grid = self._page.locator(self._VIDEO_GRID)
        try:
            grid.wait_for(state="visible", timeout=timeout)
        except Exception:
            return 0
        return grid.locator("> div").count()

    def get_video_card_titles(self) -> list[str]:
        """Return the text of each title element in the video card grid."""
        grid = self._page.locator(self._VIDEO_GRID)
        if grid.count() == 0:
            return []
        titles: list[str] = []
        cards = grid.locator("> div")
        for i in range(cards.count()):
            card = cards.nth(i)
            title_el = card.locator("a, span").first
            text = (title_el.text_content() or "").strip()
            if text:
                titles.append(text)
        return titles

    def is_video_card_visible_by_title(self, title: str, timeout: int = 3_000) -> bool:
        """Return True if a video card containing *title* is visible in the grid."""
        try:
            card = self._page.locator(self._VIDEO_GRID).locator(
                f"a:has-text('{title}'), span:has-text('{title}')"
            ).first
            card.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def wait_for_video_card_count(self, expected: int, timeout: int = 5_000) -> None:
        """Wait until the card grid contains exactly *expected* cards."""
        grid = self._page.locator(self._VIDEO_GRID)
        expect(grid.locator("> div")).to_have_count(expected, timeout=timeout)
