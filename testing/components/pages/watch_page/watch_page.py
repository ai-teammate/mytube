"""Page Object for the public video watch page (/v/<id>)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import Page, Request


@dataclass
class WatchPageState:
    """Captured state after navigating to the watch page."""
    hls_requests: list[str] = field(default_factory=list)
    network_errors: list[str] = field(default_factory=list)


class WatchPage:
    """Encapsulates interactions with the video watch page at /v/<id>.

    The watch page:
    - Fetches video metadata from the API
    - Renders the Video.js player when hlsManifestUrl is present
    - Initialises HLS streaming via @videojs/http-streaming

    Usage
    -----
    watch = WatchPage(page)
    watch.navigate(base_url, video_id)
    assert watch.is_player_visible()
    """

    # Selectors
    _VJS_PLAYER_CONTAINER = "[data-vjs-player]"
    _VIDEO_JS_ELEMENT = "video.video-js"
    _VJS_BIG_PLAY_BUTTON = ".vjs-big-play-button"
    _VJS_CONTROL_BAR = ".vjs-control-bar"
    _LOADING_SPINNER = "[class*='vjs-loading-spinner']"
    _VIDEO_TITLE = "h1"
    _LOADING_TEXT = "text=Loading…"
    _NOT_FOUND_TEXT = "text=Video not found."
    _ERROR_ALERT = "[role='alert']"

    _PLAYER_INIT_TIMEOUT = 20_000   # ms — wait for Video.js to fully init
    _PAGE_LOAD_TIMEOUT = 30_000     # ms — max time for page load

    def __init__(self, page: Page) -> None:
        self._page = page
        self._captured_hls_urls: list[str] = []

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, base_url: str, video_id: str) -> None:
        """Navigate to /v/<video_id> and wait for the video metadata to load."""
        url = f"{base_url.rstrip('/')}/v/{video_id}"
        self._page.goto(url, wait_until="domcontentloaded")
        # Wait for the loading indicator to disappear (video data fetched)
        self._page.wait_for_selector(
            self._LOADING_TEXT, state="hidden", timeout=self._PAGE_LOAD_TIMEOUT
        )

    def navigate_and_capture_network(
        self, base_url: str, video_id: str
    ) -> WatchPageState:
        """Navigate to /v/<video_id>, capture HLS manifest requests, return state."""
        state = WatchPageState()

        def on_request(request: Request) -> None:
            url = request.url
            # Capture any request that looks like an HLS manifest
            if ".m3u8" in url or "hls" in url.lower():
                state.hls_requests.append(url)

        self._page.on("request", on_request)
        try:
            self.navigate(base_url, video_id)
            # Give the player a moment to fire the manifest request
            self._page.wait_for_timeout(3_000)
        finally:
            self._page.remove_listener("request", on_request)

        return state

    # ------------------------------------------------------------------
    # Player state queries
    # ------------------------------------------------------------------

    def is_player_container_visible(self) -> bool:
        """Return True if the [data-vjs-player] wrapper div is visible."""
        el = self._page.query_selector(self._VJS_PLAYER_CONTAINER)
        return bool(el and el.is_visible())

    def is_video_element_present(self) -> bool:
        """Return True if a <video> element with class video-js exists in the DOM."""
        el = self._page.query_selector(self._VIDEO_JS_ELEMENT)
        return el is not None

    def is_player_initialised(self) -> bool:
        """Return True when Video.js has attached its classes to the video element.

        Video.js adds the `vjs-paused` (or `vjs-playing`) class to the video
        element once the player is fully initialised.
        """
        try:
            # Wait up to _PLAYER_INIT_TIMEOUT for any vjs-* state class to appear
            self._page.wait_for_selector(
                "video.video-js.vjs-paused, video.video-js.vjs-playing",
                timeout=self._PLAYER_INIT_TIMEOUT,
            )
            return True
        except Exception:
            return False

    def is_controls_visible(self) -> bool:
        """Return True if the Video.js control bar is visible."""
        el = self._page.query_selector(self._VJS_CONTROL_BAR)
        return bool(el and el.is_visible())

    def is_big_play_button_visible(self) -> bool:
        """Return True if the big-play-button overlay is visible (player ready, paused)."""
        el = self._page.query_selector(self._VJS_BIG_PLAY_BUTTON)
        return bool(el and el.is_visible())

    # ------------------------------------------------------------------
    # Page state queries
    # ------------------------------------------------------------------

    def get_video_title(self) -> Optional[str]:
        """Return the <h1> title text, or None if not present."""
        el = self._page.query_selector(self._VIDEO_TITLE)
        if el is None:
            return None
        return (el.text_content() or "").strip()

    def is_not_found(self) -> bool:
        """Return True if the 'Video not found.' message is displayed."""
        return self._page.locator(self._NOT_FOUND_TEXT).count() > 0

    def get_error_message(self) -> Optional[str]:
        """Return the text of the error alert element, or None."""
        el = self._page.query_selector(self._ERROR_ALERT)
        if el is None:
            return None
        return (el.text_content() or "").strip()

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    # ------------------------------------------------------------------
    # JavaScript helpers
    # ------------------------------------------------------------------

    def get_player_src(self) -> Optional[str]:
        """Return the current src set on the Video.js player via JS evaluation."""
        try:
            result = self._page.evaluate(
                """() => {
                    const video = document.querySelector('video.video-js');
                    if (!video) return null;
                    // Video.js stores the resolved src on the video element
                    return video.currentSrc || video.src || null;
                }"""
            )
            return result if result else None
        except Exception:
            return None

    def has_hls_source_configured(self) -> bool:
        """Return True if the Video.js player has an HLS (m3u8) source configured."""
        try:
            result = self._page.evaluate(
                """() => {
                    const video = document.querySelector('video.video-js');
                    if (!video) return false;
                    // Check source elements
                    const sources = Array.from(video.querySelectorAll('source'));
                    for (const s of sources) {
                        if (s.type === 'application/x-mpegURL' ||
                            (s.src && s.src.includes('.m3u8'))) {
                            return true;
                        }
                    }
                    // Also check currentSrc/src directly
                    const src = video.currentSrc || video.src || '';
                    return src.includes('.m3u8') || src.includes('m3u8');
                }"""
            )
            return bool(result)
        except Exception:
            return False
