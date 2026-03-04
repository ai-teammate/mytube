"""PlaylistPage — Page Object for the /pl/:id playlist page of the MyTube web application.

Encapsulates all interactions with the playlist page, exposing only
high-level state queries and actions to callers. Raw selectors never leak
outside this class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs -- the caller provides the base URL and playlist ID.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class PlaylistPage:
    """Page Object for the MyTube playlist page (/pl/:id)."""

    # -- Selectors ----------------------------------------------------------------

    # Loading / error states
    _LOADING_TEXT = "text=Loading..."
    _NOT_FOUND_TEXT = "text=Playlist not found."
    _ERROR_ALERT = "[role='alert']"

    # Playlist header
    _PLAYLIST_TITLE = "h1"

    # Player area
    _VIDEO_JS = "video.video-js"
    _PLAYER_READY = (
        "video.video-js.vjs-paused, "
        "video.video-js.vjs-playing, "
        "video.video-js.vjs-error"
    )
    _VIDEO_NOT_AVAILABLE = "p:has-text('Video not available.')"
    _SKIP_BUTTON = "button:has-text('Skip')"

    # End-of-playlist overlay
    _END_OF_PLAYLIST = "[data-testid='end-of-playlist']"
    _PLAY_AGAIN_BUTTON = "button:has-text('Play again')"

    # "Now playing (X/N)" label
    _NOW_PLAYING = "p:has-text('Now playing')"

    # Queue items in the sidebar -- aria-label="Play <title>"
    _QUEUE_ITEMS = "button[aria-label^='Play ']"
    _CURRENT_QUEUE_ITEM = "button[aria-current='true']"

    # -- Timeouts -----------------------------------------------------------------

    _PAGE_LOAD_TIMEOUT = 30_000   # ms
    _PLAYER_INIT_TIMEOUT = 20_000 # ms
    _AUTO_ADVANCE_TIMEOUT = 8_000 # ms -- how long to wait for queue to advance

    # -- Constructor --------------------------------------------------------------

    def __init__(self, page: Page) -> None:
        self._page = page

    # -- Navigation ---------------------------------------------------------------

    def navigate(self, base_url: str, playlist_id: str) -> None:
        """Navigate to /pl/<playlist_id> and wait for the loading indicator to clear."""
        url = f"{base_url.rstrip('/')}/pl/{playlist_id}/"
        self._page.goto(url, wait_until="domcontentloaded")
        try:
            self._page.wait_for_selector(
                self._LOADING_TEXT,
                state="hidden",
                timeout=self._PAGE_LOAD_TIMEOUT,
            )
        except Exception:
            pass  # loading indicator may not appear or may vanish before we check

    # -- Playlist header queries --------------------------------------------------

    def get_playlist_title(self) -> Optional[str]:
        """Return the <h1> playlist title text, or None if absent."""
        el = self._page.query_selector(self._PLAYLIST_TITLE)
        return (el.text_content() or "").strip() if el else None

    def is_not_found(self) -> bool:
        """Return True if 'Playlist not found.' is shown."""
        return self._page.locator(self._NOT_FOUND_TEXT).count() > 0

    def is_error_displayed(self) -> bool:
        """Return True if an error alert is visible."""
        el = self._page.query_selector(self._ERROR_ALERT)
        return bool(el and el.is_visible())

    # -- "Now playing" label ------------------------------------------------------

    def get_now_playing_text(self) -> Optional[str]:
        """Return the 'Now playing (X/N)' paragraph text, or None."""
        el = self._page.query_selector(self._NOW_PLAYING)
        return (el.text_content() or "").strip() if el else None

    def wait_for_now_playing_index(
        self,
        index: int,
        total: int,
        timeout: float = _AUTO_ADVANCE_TIMEOUT,
    ) -> None:
        """Block until 'Now playing (index/total)' text is visible in the DOM."""
        # The text is rendered as-is in the DOM (CSS `text-transform: uppercase`
        # only affects visual display, not text_content()).
        expected = f"Now playing ({index}/{total})"
        self._page.wait_for_selector(
            f"p:has-text('{expected}')",
            timeout=timeout,
        )

    # -- Queue panel queries ------------------------------------------------------

    def get_queue_item_count(self) -> int:
        """Return the number of items in the queue sidebar."""
        return self._page.locator(self._QUEUE_ITEMS).count()

    def get_current_queue_index(self) -> int:
        """Return the 0-based index of the currently highlighted queue item, or -1."""
        items = self._page.locator(self._QUEUE_ITEMS)
        count = items.count()
        for i in range(count):
            if items.nth(i).get_attribute("aria-current") == "true":
                return i
        return -1

    def get_queue_item_title(self, index: int) -> Optional[str]:
        """Return the title text of queue item at 0-based *index*, or None."""
        items = self._page.locator(self._QUEUE_ITEMS)
        if items.count() <= index:
            return None
        # Title is in a <p> inside the button
        p_el = items.nth(index).locator("p").first
        return (p_el.text_content() or "").strip() if p_el else None

    def is_queue_item_current(self, index: int) -> bool:
        """Return True if queue item at *index* has aria-current='true'."""
        items = self._page.locator(self._QUEUE_ITEMS)
        if items.count() <= index:
            return False
        return items.nth(index).get_attribute("aria-current") == "true"

    # -- Player state queries -----------------------------------------------------

    def wait_for_video_element(
        self,
        timeout: float = _PLAYER_INIT_TIMEOUT,
    ) -> bool:
        """Wait until a <video.video-js> element appears in the DOM.

        Returns True if found within *timeout*, False otherwise.
        """
        try:
            self._page.wait_for_selector(self._VIDEO_JS, timeout=timeout)
            return True
        except Exception:
            return False

    def wait_for_player_ready(
        self,
        timeout: float = _PLAYER_INIT_TIMEOUT,
    ) -> bool:
        """Wait for Video.js to finish initialising (vjs-paused, vjs-playing, or vjs-error).

        Returns True if any of those states are reached, False on timeout.
        """
        try:
            self._page.wait_for_selector(self._PLAYER_READY, timeout=timeout)
            return True
        except Exception:
            return False

    def has_video_not_available(self) -> bool:
        """Return True if the 'Video not available.' overlay is shown."""
        return self._page.locator(self._VIDEO_NOT_AVAILABLE).count() > 0

    def has_skip_button(self) -> bool:
        """Return True if the 'Skip' button is visible."""
        return self._page.locator(self._SKIP_BUTTON).is_visible()

    def click_skip(self) -> None:
        """Click the 'Skip' button on the 'Video not available' overlay."""
        self._page.locator(self._SKIP_BUTTON).click()

    def is_end_of_playlist_shown(self) -> bool:
        """Return True if the end-of-playlist overlay is visible."""
        return self._page.locator(self._END_OF_PLAYLIST).count() > 0

    # -- Video event helpers ------------------------------------------------------

    def fire_video_ended_event(self) -> bool:
        """Dispatch a native 'ended' event on the first <video.video-js> element.

        Returns True if the element was found, False if not present in DOM.
        This simulates the user watching the video through to the end and is
        equivalent to seeking to the last frame.
        """
        result = self._page.evaluate(
            """() => {
                const video = document.querySelector('video.video-js');
                if (!video) return false;
                // Dispatch the same event the browser fires on natural completion.
                video.dispatchEvent(new Event('ended', { bubbles: true }));
                return true;
            }"""
        )
        return bool(result)

    def wait_for_auto_advance(
        self,
        expected_index: int,
        timeout: float = _AUTO_ADVANCE_TIMEOUT,
    ) -> bool:
        """Wait until queue item at *expected_index* becomes current (aria-current='true').

        Returns True if the advance happened within *timeout*, False otherwise.
        """
        try:
            self._page.wait_for_function(
                f"""() => {{
                    const items = document.querySelectorAll("button[aria-label^='Play ']");
                    const item = items[{expected_index}];
                    return item && item.getAttribute('aria-current') === 'true';
                }}""",
                timeout=timeout,
            )
            return True
        except Exception:
            return False
