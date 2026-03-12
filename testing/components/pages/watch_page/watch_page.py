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

from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import Page, Request


@dataclass
class WatchPageState:
    """Captured state after navigating to the watch page."""
    hls_requests: list[str] = field(default_factory=list)
    network_errors: list[str] = field(default_factory=list)


class WatchPage:
    """Page Object for the MyTube video watch page (/v/:id)."""

    # Selectors
    _VJS_PLAYER_CONTAINER = "[data-vjs-player]"
    # Video.js v8 may restructure the DOM so the original <video> tag receives
    # class "vjs-tech" rather than "video-js".  Both selectors are included so
    # is_video_element_present() works regardless of initialisation state.
    _VIDEO_JS_ELEMENT = "video.video-js, video.vjs-tech"
    _VJS_BIG_PLAY_BUTTON = ".vjs-big-play-button"
    _VJS_CONTROL_BAR = ".vjs-control-bar"
    _LOADING_SPINNER = "[class*='vjs-loading-spinner']"
    _VIDEO_TITLE = "h1"
    _TITLE_HEADING = "h1"
    _LOADING_TEXT = "text=Loading…"
    _NOT_FOUND_TEXT = "text=Video not found."
    _ERROR_ALERT = "[data-vjs-player] [role='alert']"

    _DEFAULT_LOAD_TIMEOUT = 15_000  # ms
    _PLAYER_INIT_TIMEOUT = 20_000   # ms — wait for Video.js to fully init
    _PAGE_LOAD_TIMEOUT = 30_000     # ms — max time for page load
    _OG_TAG_TIMEOUT = 15_000        # ms — wait for OG tags to be set

    def __init__(self, page: Page) -> None:
        self._page = page
        self._captured_hls_urls: list[str] = []

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_video(self, base_url: str, video_id: str) -> None:
        """Navigate to the watch page for *video_id* and wait for DOM load."""
        url = f"{base_url.rstrip('/')}/v/{video_id}"
        self._page.goto(url, wait_until="domcontentloaded")

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
            # Wait for at least one HLS manifest request (or timeout gracefully)
            try:
                self._page.wait_for_request(
                    lambda req: ".m3u8" in req.url or "hls" in req.url.lower(),
                    timeout=self._PLAYER_INIT_TIMEOUT,
                )
            except Exception:
                pass  # manifest may not be requested (test will assert later)
        finally:
            self._page.remove_listener("request", on_request)

        return state

    # ------------------------------------------------------------------
    # Wait helpers
    # ------------------------------------------------------------------

    def wait_for_controls(self, timeout: int = _PLAYER_INIT_TIMEOUT) -> None:
        """Wait until the Video.js control bar is visible."""
        self._page.wait_for_selector(self._VJS_CONTROL_BAR, state="visible", timeout=timeout)

    def wait_for_big_play_button(self, timeout: int = _PLAYER_INIT_TIMEOUT) -> None:
        """Wait until the big-play-button overlay is visible."""
        self._page.wait_for_selector(self._VJS_BIG_PLAY_BUTTON, state="visible", timeout=timeout)

    def is_homepage_grid_visible(self) -> bool:
        """Return True if any homepage discovery section is still rendered."""
        recently_uploaded = self._page.locator(
            "section[aria-labelledby='recently-uploaded-heading']"
        )
        most_viewed = self._page.locator(
            "section[aria-labelledby='most-viewed-heading']"
        )
        ru_visible = recently_uploaded.count() > 0 and recently_uploaded.is_visible()
        mv_visible = most_viewed.count() > 0 and most_viewed.is_visible()
        return ru_visible or mv_visible

    def wait_for_metadata(self, timeout: float = _DEFAULT_LOAD_TIMEOUT) -> None:
        """Wait until the loading indicator disappears and the h1 title is visible."""
        # Wait for the loading spinner to go away
        loading = self._page.get_by_text("Loading")
        try:
            loading.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass  # loading indicator may not appear at all
        # Then wait for the h1 title element to be present
        self._page.locator("h1").wait_for(state="visible", timeout=timeout)

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

        Video.js adds the `vjs-paused` (or `vjs-playing`) class to the wrapping
        div element once the player is fully initialised. The selector is
        tag-agnostic to handle Video.js DOM restructuring at runtime.
        """
        try:
            # Wait up to _PLAYER_INIT_TIMEOUT for any vjs-* state class to appear
            self._page.wait_for_selector(
                ".video-js.vjs-paused, .video-js.vjs-playing",
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

    def click_play(self) -> None:
        """Click the play button to start or replay playback.

        Tries the big-play-button overlay first (visible in initial paused
        state).  If it is hidden (e.g. after ``vjs-ended`` with the app's
        custom CSS), falls back to the control-bar play/pause toggle so the
        test can verify replay behaviour without timing out.
        """
        big_btn = self._page.query_selector(self._VJS_BIG_PLAY_BUTTON)
        if big_btn and big_btn.is_visible():
            big_btn.click()
            return
        # vjs-ended or custom CSS: big play button hidden; use the control bar
        play_ctrl = self._page.query_selector(".vjs-play-control")
        if play_ctrl and play_ctrl.is_visible():
            play_ctrl.click()
            return
        # Last resort: click the player container (triggers playback in most themes)
        self._page.locator(self._VJS_PLAYER_CONTAINER).click()

    def is_playing(self) -> bool:
        """Return True when Video.js is in the playing state."""
        try:
            self._page.wait_for_selector(
                ".video-js.vjs-playing",
                timeout=self._PLAYER_INIT_TIMEOUT,
            )
            return True
        except Exception:
            return False

    def is_playing_or_ended(self) -> bool:
        """Return True when Video.js is in the playing or ended state.

        For short/mocked streams the player may transition directly from
        paused → ended without a measurable vjs-playing window.
        """
        try:
            self._page.wait_for_selector(
                ".video-js.vjs-playing, .video-js.vjs-ended",
                timeout=self._PLAYER_INIT_TIMEOUT,
            )
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Page state queries
    # ------------------------------------------------------------------

    def get_video_title(self) -> Optional[str]:
        """Return the <h1> title text, or None if not present."""
        el = self._page.query_selector(self._VIDEO_TITLE)
        if el is None:
            return None
        return (el.text_content() or "").strip()

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

    def is_not_found(self) -> bool:
        """Return True if the 'Video not found.' message is displayed."""
        return self._page.locator(self._NOT_FOUND_TEXT).count() > 0

    def get_error_message(self) -> Optional[str]:
        """Return the text of the error alert element, or None."""
        el = self._page.query_selector(self._ERROR_ALERT)
        if el is None:
            return None
        return (el.text_content() or "").strip()

    def is_error_displayed(self) -> bool:
        """Return True if an error alert is visible."""
        el = self._page.query_selector(self._ERROR_ALERT)
        return bool(el and el.is_visible())

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def get_page_title(self) -> str:
        """Return the document.title value."""
        return self._page.title()

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

    # ------------------------------------------------------------------
    # Comment section queries (guest / authenticated state)
    # ------------------------------------------------------------------

    _COMMENT_SECTION = "section[aria-label='Comments']"
    _COMMENT_HEADING = "section[aria-label='Comments'] h2"
    _LOGIN_LINK = "section[aria-label='Comments'] a[href='/login']"
    _COMMENT_TEXTAREA = "section[aria-label='Comments'] textarea[aria-label='Comment body']"
    _COMMENT_SUBMIT = "section[aria-label='Comments'] button[type='submit']"
    _AUTH_WAIT_TIMEOUT = 20_000  # ms — Firebase auth resolves quickly for guests

    def wait_for_comment_section_auth_resolved(self, timeout: int = _AUTH_WAIT_TIMEOUT) -> None:
        """Wait until the comment section finishes resolving auth state.

        After auth resolves, either the login prompt (guest) or the comment
        form (authenticated user) will be present.  Block until one of them
        is visible.
        """
        self._page.wait_for_selector(
            f"{self._LOGIN_LINK}, {self._COMMENT_TEXTAREA}",
            timeout=timeout,
        )

    def is_comment_section_visible(self) -> bool:
        """Return True if the Comments section heading is visible."""
        el = self._page.query_selector(self._COMMENT_HEADING)
        return bool(el and el.is_visible())

    def has_login_to_comment_prompt(self) -> bool:
        """Return True if the 'Login to comment' link is visible for guests."""
        el = self._page.query_selector(self._LOGIN_LINK)
        return bool(el and el.is_visible())

    def get_login_link_href(self) -> Optional[str]:
        """Return the href of the 'Login' link in the comment section, or None."""
        el = self._page.query_selector(self._LOGIN_LINK)
        if el is None:
            return None
        return el.get_attribute("href")

    def has_comment_textarea(self) -> bool:
        """Return True if the comment text area is present (only for auth users)."""
        el = self._page.query_selector(self._COMMENT_TEXTAREA)
        return bool(el and el.is_visible())

    def has_comment_submit_button(self) -> bool:
        """Return True if the comment submit button is present (only for auth users)."""
        el = self._page.query_selector(self._COMMENT_SUBMIT)
        return bool(el and el.is_visible())

    # ------------------------------------------------------------------
    # Rating widget queries and actions
    # ------------------------------------------------------------------

    _RATING_GROUP = '[role="group"][aria-label="Star rating"]'
    _RATING_SUMMARY_TIMEOUT = 10_000  # ms — wait for the summary span to appear

    def get_rating_summary_text(self) -> Optional[str]:
        """Return the rating summary text (e.g. '4.2 / 5 (10 ratings)'), or None."""
        locator = self._page.locator('span:has-text("/ 5")')
        if locator.count() == 0:
            return None
        return (locator.first.text_content() or "").strip()

    def wait_for_rating_summary(self, timeout: float = _RATING_SUMMARY_TIMEOUT) -> None:
        """Wait until the rating summary span ('X.X / 5 ...') is visible."""
        self._page.locator('span:has-text("/ 5")').wait_for(
            state="visible", timeout=timeout
        )

    def wait_for_rating_summary_text(self, expected: str, timeout: float = _RATING_SUMMARY_TIMEOUT) -> None:
        """Wait until the rating summary span contains *expected* text."""
        self._page.locator(f'span:has-text("{expected}")').wait_for(
            state="visible", timeout=timeout
        )

    def click_star(self, n: int) -> None:
        """Click the nth star button (1–5) in the rating widget."""
        label = f"Rate {n} star{'s' if n != 1 else ''}"
        self._page.locator(f'button[aria-label="{label}"]').click()

    def is_star_pressed(self, n: int) -> bool:
        """Return True if star *n* has aria-pressed='true'."""
        label = f"Rate {n} star{'s' if n != 1 else ''}"
        el = self._page.query_selector(f'button[aria-label="{label}"]')
        if el is None:
            return False
        return el.get_attribute("aria-pressed") == "true"

    def is_rating_widget_visible(self) -> bool:
        """Return True if the star rating group is present in the DOM."""
        return self._page.locator(self._RATING_GROUP).count() > 0

    def has_login_to_rate_prompt(self) -> bool:
        """Return True if the 'Log in to rate this video.' link is visible."""
        return self._page.get_by_text("to rate this video.").count() > 0

    # ------------------------------------------------------------------
    # Computed style queries (CSS visual attributes)
    # ------------------------------------------------------------------

    def get_computed_style(self, css_selector: str, css_property: str) -> Optional[str]:
        """Return the computed value of *css_property* for the first element matching
        *css_selector*, or None if no element is found.

        The selector is matched using ``document.querySelector`` so CSS Module
        class names should be supplied as attribute-contains patterns, e.g.
        ``[class*="player"]``.
        """
        return self._page.evaluate(
            """([sel, prop]) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                return window.getComputedStyle(el)[prop];
            }""",
            [css_selector, css_property],
        )

    def get_player_computed_style(self, css_property: str) -> Optional[str]:
        """Return the computed value of *css_property* for the .player container."""
        return self.get_computed_style('[class*="player"]', css_property)

    def get_video_title_computed_style(self, css_property: str) -> Optional[str]:
        """Return the computed value of *css_property* for the .videoTitle element."""
        return self.get_computed_style('[class*="videoTitle"]', css_property)
