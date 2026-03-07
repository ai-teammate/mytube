"""Page Object for the category browse page at /category/{id}/."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError


@dataclass
class CategoryPageState:
    """Snapshot of the category page after loading."""

    category_name: Optional[str]
    video_card_count: int
    video_titles: list[str]
    has_error: bool
    error_text: Optional[str]
    is_loading: bool


class CategoryPage:
    """Encapsulates interactions with the /category/{id}/ page.

    Usage::

        page_obj = CategoryPage(page)
        page_obj.navigate(web_config.base_url, category_id=3)
        state = page_obj.get_state()
    """

    _HEADING_SELECTOR = "h1"
    _VIDEO_CARD_SELECTOR = "[data-testid='video-card'], .video-card, article"
    _VIDEO_TITLE_SELECTOR = "[data-testid='video-title'], .video-title, h2, h3"
    _ERROR_SELECTOR = "[role='alert']"
    _EMPTY_STATE_MESSAGES = ("No videos in this category yet", "No videos")
    _LOADING_TEXT = "Loading"
    _LOAD_TIMEOUT_MS = 30_000
    _CONTENT_TIMEOUT_MS = 15_000

    def __init__(self, page: Page) -> None:
        self._page = page

    def navigate(self, base_url: str, category_id: int) -> None:
        """Navigate to /category/{category_id}/ and wait for content to load."""
        url = f"{base_url.rstrip('/')}/category/{category_id}/"
        self._page.goto(url, wait_until="domcontentloaded", timeout=self._LOAD_TIMEOUT_MS)
        self._wait_for_content_loaded()

    def _wait_for_content_loaded(self) -> None:
        """Wait until the loading spinner disappears (content is ready)."""
        try:
            # Wait for the h1 heading to appear (category name rendered)
            self._page.wait_for_selector(
                self._HEADING_SELECTOR,
                state="visible",
                timeout=self._CONTENT_TIMEOUT_MS,
            )
        except PlaywrightTimeoutError:
            # Page may show error state — that's still a valid loaded state
            pass

    def get_category_name(self) -> Optional[str]:
        """Return the text of the <h1> heading, or None if not present."""
        try:
            el = self._page.query_selector(self._HEADING_SELECTOR)
            if el:
                return el.inner_text().strip() or None
        except Exception:
            pass
        return None

    def get_video_cards(self) -> list:
        """Return all video card elements on the page."""
        try:
            return self._page.query_selector_all(self._VIDEO_CARD_SELECTOR)
        except Exception:
            return []

    def get_video_card_count(self) -> int:
        """Return the number of video cards rendered on the page."""
        return len(self.get_video_cards())

    def get_video_titles(self) -> list[str]:
        """Return text of all video title elements inside video cards."""
        titles: list[str] = []
        try:
            cards = self.get_video_cards()
            for card in cards:
                title_el = card.query_selector(self._VIDEO_TITLE_SELECTOR)
                if title_el:
                    text = title_el.inner_text().strip()
                    if text:
                        titles.append(text)
        except Exception:
            pass
        return titles

    def has_error(self) -> bool:
        """Return True if an error message with non-empty text is visible on the page.

        Next.js injects a visually-hidden [role="alert"] element for accessibility
        on every page; this method ignores that empty element and only returns True
        when the alert contains actual text.
        """
        try:
            el = self._page.query_selector(self._ERROR_SELECTOR)
            if el and el.is_visible():
                return bool(el.inner_text().strip())
            return False
        except Exception:
            return False

    def get_error_text(self) -> Optional[str]:
        """Return the text of the error alert, or None if no error."""
        try:
            el = self._page.query_selector(self._ERROR_SELECTOR)
            if el and el.is_visible():
                return el.inner_text().strip()
        except Exception:
            pass
        return None

    def is_loading(self) -> bool:
        """Return True if the page is still in loading state."""
        try:
            content = self._page.content()
            return "Loading" in content and self.get_category_name() is None
        except Exception:
            return False

    def get_state(self) -> CategoryPageState:
        """Capture a full state snapshot of the page."""
        return CategoryPageState(
            category_name=self.get_category_name(),
            video_card_count=self.get_video_card_count(),
            video_titles=self.get_video_titles(),
            has_error=self.has_error(),
            error_text=self.get_error_text(),
            is_loading=self.is_loading(),
        )

    def has_empty_state_message(self) -> bool:
        """Return True if an empty-state message is visibly rendered in the DOM.

        Uses get_by_text() so only text actually rendered in the viewport is
        matched — not hidden elements, <script> bundles, or <noscript> blocks.
        """
        try:
            for msg in self._EMPTY_STATE_MESSAGES:
                locator = self._page.get_by_text(msg, exact=False)
                if locator.count() > 0 and locator.first.is_visible():
                    return True
            return False
        except Exception:
            return False

    def get_empty_state_message(self) -> Optional[str]:
        """Return the first empty-state message visibly rendered in the DOM, or None."""
        try:
            for msg in self._EMPTY_STATE_MESSAGES:
                locator = self._page.get_by_text(msg, exact=False)
                if locator.count() > 0 and locator.first.is_visible():
                    return msg
        except Exception:
            pass
        return None

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url
