"""UploadPage — Page Object for the /upload page of the MyTube web application.

Encapsulates all interactions with the video upload form, exposing only
high-level actions and state queries to callers. Raw selectors never leak
outside this class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the base URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from __future__ import annotations

from typing import Optional

from playwright.sync_api import Page


class UploadPage:
    """Page Object for the MyTube video upload page (/upload)."""

    # Selectors
    _FILE_INPUT = 'input[id="video-file"]'
    _FILE_SIZE_WARNING = '[role="note"]'
    _MIME_TYPE_ERROR = '[role="alert"]'
    _HEADING = "h1"

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, base_url: str) -> None:
        """Navigate to the /upload page and wait for it to load."""
        url = f"{base_url.rstrip('/')}/upload"
        self._page.goto(url, wait_until="domcontentloaded")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def simulate_large_file_selection(self, size_bytes: int, filename: str = "large.mp4") -> None:
        """Simulate selecting a file with a given size (in bytes) via the file input.

        Uses JavaScript to create a File object with an overridden ``size``
        property, then dispatches a ``change`` event on the file input.
        This avoids having to upload a real multi-GB file during testing.

        Parameters
        ----------
        size_bytes:
            The apparent file size to report (e.g., 4 * 1024**3 + 1 for > 4 GB).
        filename:
            The name of the simulated file. Defaults to ``large.mp4``.
        """
        self._page.evaluate(
            """
            ([selector, sizeBytes, filename]) => {
                const input = document.querySelector(selector);
                if (!input) throw new Error('File input not found: ' + selector);

                // Create a minimal File object with an overridden size
                const file = new File(['x'], filename, { type: 'video/mp4' });
                Object.defineProperty(file, 'size', {
                    value: sizeBytes,
                    writable: false,
                });

                // Inject the file into the input's FileList via a DataTransfer
                const dt = new DataTransfer();
                dt.items.add(file);
                Object.defineProperty(input, 'files', {
                    value: dt.files,
                    writable: false,
                    configurable: true,
                });

                // Dispatch the change event so React's onChange handler fires
                input.dispatchEvent(new Event('change', { bubbles: true }));
            }
            """,
            [self._FILE_INPUT, size_bytes, filename],
        )

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def get_file_size_warning_text(self, timeout: float = 5_000) -> Optional[str]:
        """Return the text of the file size warning note, or None if not shown."""
        locator = self._page.locator(self._FILE_SIZE_WARNING)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return locator.text_content()
        except Exception:
            return None

    def is_file_size_warning_visible(self, timeout: float = 5_000) -> bool:
        """Return True if the file size warning (role=note) is visible."""
        locator = self._page.locator(self._FILE_SIZE_WARNING)
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def is_on_upload_page(self) -> bool:
        """Return True if the Upload video heading is visible on the page."""
        return self._page.locator(self._HEADING).filter(has_text="Upload video").is_visible()

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def is_on_login_page(self) -> bool:
        """Return True if the browser has been redirected to the /login page."""
        return "/login" in self._page.url
