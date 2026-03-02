"""UserProfilePage — Page Object for /u/:username pages of the MyTube web application.

Encapsulates all interactions with the user profile page, exposing only
high-level state queries to callers.  Raw selectors never leak outside this
class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the base URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from playwright.sync_api import Page


class UserProfilePage:
    """Page Object for the MyTube public user profile page (/u/:username)."""

    _NOT_FOUND_TEXT = "User not found."
    _LOADING_TEXT = "Loading"

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate_to_user(self, base_url: str, username: str) -> None:
        """Navigate to the profile page for *username* and wait for load."""
        url = f"{base_url.rstrip('/')}/u/{username}"
        self._page.goto(url, wait_until="domcontentloaded")

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def is_not_found(self, timeout: float = 10_000) -> bool:
        """Return True when the 'User not found.' message is visible."""
        locator = self._page.get_by_text(self._NOT_FOUND_TEXT, exact=True)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def is_loading(self) -> bool:
        """Return True when the loading indicator is visible."""
        return self._page.get_by_text(self._LOADING_TEXT).count() > 0

    def get_not_found_text(self) -> str | None:
        """Return the text content of the not-found paragraph, or None."""
        locator = self._page.get_by_text(self._NOT_FOUND_TEXT, exact=True)
        if locator.count() == 0:
            return None
        return locator.text_content()

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    # ------------------------------------------------------------------
    # Event monitoring
    # ------------------------------------------------------------------

    def listen_for_js_errors(self) -> list[str]:
        """Attach a pageerror listener and return the shared errors list."""
        errors: list[str] = []
        self._page.on("pageerror", lambda err: errors.append(str(err)))
        return errors
