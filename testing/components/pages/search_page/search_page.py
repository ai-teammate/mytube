"""SearchPage — Page Object for the /search page of the MyTube web application.

Encapsulates all interactions with the search results page, exposing only
high-level actions and state queries to callers.  Raw selectors never leak
outside this class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the base URL and search query.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode, urlparse, parse_qs

from playwright.sync_api import Page


class SearchPage:
    """Page Object for the MyTube search results page (/search?q=<query>).

    The search page is reached by:
    - Typing a term in the SiteHeader search input and pressing Enter or
      clicking the Search button.
    - Direct navigation to /search?q=<query>.

    UI states
    ---------
    - Loading : "Loading…" paragraph visible while the API call is in flight.
    - Error   : ``[role="alert"]`` paragraph with an error message.
    - Empty   : "No videos found." paragraph when no results match.
    - Results : responsive grid of VideoCard components (a[href^="/v/"]).
    """

    # ------------------------------------------------------------------
    # Selectors (kept private — callers use the query methods below)
    # ------------------------------------------------------------------
    _SEARCH_INPUT = 'input[type="search"]'
    _SEARCH_BUTTON = 'button[aria-label="Submit search"]'
    _SEARCH_FORM = 'form[role="search"]'
    _RESULTS_HEADING = "h1"
    _LOADING_TEXT = "Loading…"
    _NO_RESULTS_TEXT = "No videos found."
    _ERROR_ALERT = '[role="alert"]'
    _VIDEO_CARD = "a[href^='/v/']"

    _PAGE_LOAD_TIMEOUT = 30_000  # ms
    _RESULTS_TIMEOUT = 15_000   # ms — wait for results / empty / error state

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, base_url: str, query: str) -> None:
        """Navigate directly to /search?q=<query> and wait for results to load."""
        encoded = urlencode({"q": query})
        url = f"{base_url.rstrip('/')}/search?{encoded}"
        self._page.goto(url, wait_until="domcontentloaded")
        self._wait_for_results_state()

    # ------------------------------------------------------------------
    # Search-from-header actions
    # ------------------------------------------------------------------

    def navigate_to_home(self, base_url: str) -> None:
        """Navigate to the home page where the SiteHeader search bar is present."""
        self._page.goto(f"{base_url.rstrip('/')}/", wait_until="domcontentloaded")
        # Wait for the search input to be visible in the header
        self._page.wait_for_selector(self._SEARCH_INPUT, timeout=self._PAGE_LOAD_TIMEOUT)

    def fill_search_input(self, query: str) -> None:
        """Type *query* into the header search input field."""
        self._page.fill(self._SEARCH_INPUT, query)

    def submit_search_by_enter(self) -> None:
        """Press Enter in the search input to submit the search."""
        self._page.press(self._SEARCH_INPUT, "Enter")
        self._wait_for_results_state()

    def submit_search_by_button(self) -> None:
        """Click the search button to submit the search."""
        self._page.click(self._SEARCH_BUTTON)
        self._wait_for_results_state()

    # ------------------------------------------------------------------
    # Wait helpers (private)
    # ------------------------------------------------------------------

    def _wait_for_results_state(self) -> None:
        """Wait until the search page has settled: results, empty, or error."""
        # Wait for the loading indicator to disappear
        loading_locator = self._page.get_by_text(self._LOADING_TEXT, exact=True)
        try:
            loading_locator.wait_for(state="visible", timeout=3_000)
        except Exception:
            pass  # Loading may be too fast to catch
        try:
            loading_locator.wait_for(state="hidden", timeout=self._RESULTS_TIMEOUT)
        except Exception:
            pass  # Loading indicator may not appear at all for fast responses

    # ------------------------------------------------------------------
    # URL / navigation state queries
    # ------------------------------------------------------------------

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def is_on_search_page(self) -> bool:
        """Return True if the current URL path is /search."""
        parsed = urlparse(self._page.url)
        return parsed.path.rstrip("/") == "/search"

    def get_query_param(self) -> Optional[str]:
        """Return the value of the ``q`` query parameter in the current URL, or None."""
        parsed = urlparse(self._page.url)
        params = parse_qs(parsed.query)
        values = params.get("q", [])
        return values[0] if values else None

    # ------------------------------------------------------------------
    # Page content queries
    # ------------------------------------------------------------------

    def get_heading_text(self) -> Optional[str]:
        """Return the text content of the results <h1> heading, or None."""
        el = self._page.query_selector(self._RESULTS_HEADING)
        if el is None:
            return None
        return (el.text_content() or "").strip()

    def get_video_card_count(self) -> int:
        """Return the number of VideoCard links rendered in the results grid."""
        return len(self._page.query_selector_all(self._VIDEO_CARD))

    def get_video_card_hrefs(self) -> list[str]:
        """Return the href values for every VideoCard on the page."""
        cards = self._page.query_selector_all(self._VIDEO_CARD)
        hrefs: list[str] = []
        for card in cards:
            href = card.get_attribute("href") or ""
            if href:
                hrefs.append(href)
        return hrefs

    def has_results(self) -> bool:
        """Return True if at least one VideoCard is visible."""
        return self.get_video_card_count() > 0

    def is_empty_state_visible(self) -> bool:
        """Return True if the 'No videos found.' message is displayed."""
        return self._page.locator(f"text={self._NO_RESULTS_TEXT}").count() > 0

    def is_loading(self) -> bool:
        """Return True if the loading indicator is currently visible."""
        locator = self._page.get_by_text(self._LOADING_TEXT, exact=True)
        try:
            return locator.is_visible()
        except Exception:
            return False

    def get_error_message(self) -> Optional[str]:
        """Return the text of the error alert element, or None."""
        el = self._page.query_selector(self._ERROR_ALERT)
        if el is None:
            return None
        return (el.text_content() or "").strip()

    def is_error_displayed(self) -> bool:
        """Return True if an error alert is currently visible."""
        el = self._page.query_selector(self._ERROR_ALERT)
        return bool(el and el.is_visible())
