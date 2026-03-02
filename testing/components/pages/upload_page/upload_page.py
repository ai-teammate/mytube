"""UploadPage — Page Object for the /upload page of the MyTube web application.

Encapsulates all interactions with the video upload form, exposing only
high-level actions and state queries to callers.  Raw selectors never leak
outside this class.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the full upload URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
"""
from playwright.sync_api import Page


class UploadPage:
    """Page Object for the MyTube upload page."""

    # Selectors
    _FILE_INPUT = 'input[id="video-file"]'
    _MIME_ERROR_ALERT = '[role="alert"]'
    _SUPPORTED_FORMATS_TEXT = "p.mt-1.text-sm.text-gray-500"

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> None:
        """Navigate the browser to the upload page URL and wait for it to load."""
        self._page.goto(url, wait_until="domcontentloaded")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def set_input_file_by_mime(self, filename: str, mime_type: str, content: bytes = b"fake content") -> None:
        """Simulate selecting a file with a specific MIME type via the file input.

        Uses Playwright's ``set_input_files`` to bypass the OS file picker and
        inject a synthetic file directly into the ``<input type="file">`` element.
        """
        self._page.set_input_files(
            self._FILE_INPUT,
            files=[{"name": filename, "mimeType": mime_type, "buffer": content}],
        )

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def get_mime_error_message(self) -> str | None:
        """Return the visible MIME type error alert text, or None if not shown."""
        locator = self._page.locator(self._MIME_ERROR_ALERT)
        if locator.count() == 0:
            return None
        for i in range(locator.count()):
            text = locator.nth(i).text_content()
            if text and ("unsupported" in text.lower() or "mp4" in text.lower()):
                return text.strip()
        return None

    def has_mime_error(self) -> bool:
        """Return True if a MIME type validation error alert is currently visible."""
        return self.get_mime_error_message() is not None

    def get_file_input_accept_attribute(self) -> str | None:
        """Return the ``accept`` attribute value of the file input element."""
        return self._page.get_attribute(self._FILE_INPUT, "accept")

    def is_upload_form_visible(self) -> bool:
        """Return True when the file input is present in the DOM."""
        return self._page.locator(self._FILE_INPUT).count() > 0
