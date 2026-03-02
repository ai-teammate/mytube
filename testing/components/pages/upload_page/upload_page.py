"""UploadPage — Page Object for the /upload page of the MyTube web application.

Encapsulates navigation to and state queries for the upload page.
Used primarily to test access control — verifying that unauthenticated
users are redirected away from this protected page.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the base URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from playwright.sync_api import Page


class UploadPage:
    """Page Object for the MyTube video upload page (/upload)."""

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, base_url: str) -> None:
        """Navigate directly to /upload and wait for the page to settle.

        Uses ``networkidle`` so that any client-side auth check and redirect
        has time to complete before callers inspect the URL.
        """
        url = f"{base_url.rstrip('/')}/upload"
        self._page.goto(url, wait_until="networkidle", timeout=30_000)

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def is_on_login_page(self) -> bool:
        """Return True if the browser has been redirected to the /login page."""
        return "/login" in self._page.url
