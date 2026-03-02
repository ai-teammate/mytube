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
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page


class UploadPage:
    """Page Object for the MyTube upload page at /upload."""

    # Selectors
    _HEADING = "h1"
    _FILE_INPUT = 'input[id="video-file"]'
    _TITLE_INPUT = 'input[id="title"]'
    _DESCRIPTION_INPUT = 'textarea[id="description"]'
    _CATEGORY_SELECT = 'select[id="categoryId"]'
    _TAGS_INPUT = 'input[id="tags"]'
    _SUBMIT_BUTTON = 'button[type="submit"]'
    _ERROR_ALERT = '[role="alert"]'
    _MIME_ERROR_ALERT = '[role="alert"]'
    _PROGRESS_BAR = '[role="progressbar"]'
    _UPLOAD_PROGRESS_CONTAINER = '[aria-label="upload progress"]'
    _SUPPORTED_FORMATS_TEXT = "p.mt-1.text-sm.text-gray-500"

    # Timeouts
    _MIME_ERROR_TIMEOUT = 5_000  # ms — max time to wait for the error alert to appear

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> None:
        """Navigate to the /upload page and wait for it to load."""
        self._page.goto(url, wait_until="domcontentloaded")
        # Wait for the form heading to appear
        self._page.wait_for_selector(self._HEADING, timeout=20_000)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def set_video_file(self, file_path: str) -> None:
        """Set the video file input to the file at *file_path*."""
        self._page.set_input_files(self._FILE_INPUT, file_path)

    def fill_title(self, title: str) -> None:
        """Fill the title input field."""
        self._page.fill(self._TITLE_INPUT, title)

    def fill_description(self, description: str) -> None:
        """Fill the description textarea."""
        self._page.fill(self._DESCRIPTION_INPUT, description)

    def select_category(self, value: str) -> None:
        """Select a category by its option value (e.g. '1' for Education)."""
        self._page.select_option(self._CATEGORY_SELECT, value)

    def fill_tags(self, tags: str) -> None:
        """Fill the tags input with comma-separated tag string."""
        self._page.fill(self._TAGS_INPUT, tags)

    def click_upload(self) -> None:
        """Click the Upload video submit button."""
        self._page.click(self._SUBMIT_BUTTON)

    def fill_form_and_upload(
        self,
        file_path: str,
        title: str,
        description: str = "",
        category_value: str = "",
        tags: str = "",
    ) -> None:
        """High-level action: fill the entire form and click Upload video.

        Does NOT wait for navigation -- the caller is responsible for asserting
        the post-upload state.
        """
        self.set_video_file(file_path)
        self.fill_title(title)
        if description:
            self.fill_description(description)
        if category_value:
            self.select_category(category_value)
        if tags:
            self.fill_tags(tags)
        self.click_upload()

    def set_input_file_by_mime(self, filename: str, mime_type: str, content: bytes = b"fake content") -> None:
        """Simulate selecting a file with a specific MIME type via the file input.

        Uses Playwright's ``set_input_files`` to bypass the OS file picker and
        inject a synthetic file directly into the ``<input type="file">`` element.
        Waits for the MIME error alert to become visible after the file is set,
        so callers do not need any additional waits.
        """
        self._page.set_input_files(
            self._FILE_INPUT,
            files=[{"name": filename, "mimeType": mime_type, "buffer": content}],
        )
        # Wait for the React state update to propagate and the alert to appear.
        # This is an event-driven wait — it resolves as soon as the element is
        # visible and times out (raising) if it never appears within the timeout.
        try:
            self._page.locator(self._MIME_ERROR_ALERT).first.wait_for(
                state="visible", timeout=self._MIME_ERROR_TIMEOUT
            )
        except Exception:
            # The alert may not always appear (e.g. for the accept-attribute test).
            # Silently swallow the timeout so callers can make their own assertions.
            pass

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def is_on_upload_page(self) -> bool:
        """Return True if the upload form heading is visible."""
        heading = self._page.locator(self._HEADING)
        return heading.count() > 0 and "Upload video" in (heading.text_content() or "")

    def is_on_login_page(self) -> bool:
        """Return True if the browser has been redirected to the /login page."""
        return "/login" in self._page.url

    def get_error_message(self) -> Optional[str]:
        """Return the visible error alert text, or None if absent."""
        locator = self._page.locator(self._ERROR_ALERT)
        if locator.count() == 0:
            return None
        text = locator.text_content()
        return text.strip() if text else None

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

    def is_uploading(self) -> bool:
        """Return True if the upload progress bar is visible."""
        return self._page.locator(self._UPLOAD_PROGRESS_CONTAINER).count() > 0

    def get_upload_progress(self) -> Optional[int]:
        """Return the current upload progress value (0-100) or None."""
        bar = self._page.locator(self._PROGRESS_BAR)
        if bar.count() == 0:
            return None
        val = bar.get_attribute("aria-valuenow")
        return int(val) if val is not None else None

    def wait_for_upload_complete_and_redirect(
        self,
        dashboard_url_fragment: str = "/dashboard",
        timeout: int = 60_000,
    ) -> str:
        """Wait for upload to complete and for the browser to redirect to the dashboard.

        Returns the final URL after navigation.
        """
        self._page.wait_for_url(
            lambda u: dashboard_url_fragment in u,
            timeout=timeout,
        )
        return self._page.url
