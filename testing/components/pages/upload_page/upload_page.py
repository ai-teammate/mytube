"""UploadPage — Page Object for the /upload page of the MyTube web application.

Encapsulates all interactions with the video upload form, including file selection,
metadata entry, upload submission, and real-time progress bar observation.

Architecture notes
------------------
- Dependency-injected Playwright ``Page`` is passed via constructor.
- No hardcoded URLs — the caller provides the full upload URL.
- All waits use Playwright's built-in auto-wait; no ``time.sleep`` calls.
- Progress bar snapshots are captured at intervals for incremental verification.
"""
from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import Page


@dataclass
class UploadProgressSnapshot:
    """A single snapshot of progress bar state during upload."""
    progress_visible: bool
    aria_value_now: Optional[int]
    percentage_text: Optional[str]
    phase_text: Optional[str]


class UploadPage:
    """Page Object for the MyTube upload page at /upload."""

    # Selectors
    _HEADING = "h1"
    _FILE_INPUT = 'input[id="video-file"]'
    _FILE_SIZE_WARNING = '[role="note"]'
    _MIME_TYPE_ERROR = '[role="alert"]'
    _TITLE_INPUT = 'input[id="title"]'
    _DESCRIPTION_INPUT = 'textarea[id="description"]'
    _CATEGORY_SELECT = 'select[id="categoryId"]'
    _TAGS_INPUT = 'input[id="tags"]'
    _SUBMIT_BUTTON = 'button[type="submit"]'
    _UPLOAD_BUTTON = 'button[type="submit"]'
    _ERROR_ALERT = '[role="alert"]'
    _MIME_ERROR_ALERT = '[role="alert"]'
    _PROGRESS_BAR = '[role="progressbar"]'
    _PROGRESS_CONTAINER = '[aria-label="upload progress"]'
    _UPLOAD_PROGRESS_CONTAINER = '[aria-label="upload progress"]'
    _SUPPORTED_FORMATS_TEXT = "p.mt-1.text-sm.text-gray-500"
    _HEADING = "h1"

    # Timeouts
    _MIME_ERROR_TIMEOUT = 5_000  # ms — max time to wait for the error alert to appear

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> None:
        """Navigate to the /upload page and wait for it to load.

        Uses ``networkidle`` so that Firebase auth state resolves before the
        page logic runs (the upload form redirects to /login when auth is still
        loading).
        """
        self._page.goto(url, wait_until="networkidle")
        # Wait for the file input to be present — confirms the auth guard has
        # resolved and the upload form is fully rendered.
        self._page.locator(self._FILE_INPUT).wait_for(state="attached", timeout=15_000)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def set_video_file(self, file_path: str) -> None:
        """Set the video file input to the file at *file_path*."""
        self._page.set_input_files(self._FILE_INPUT, file_path)

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

    def set_file(self, file_path: str) -> None:
        """Attach a local file to the hidden file input."""
        self._page.set_input_files(self._FILE_INPUT, file_path)

    def fill_title(self, title: str) -> None:
        """Fill the title input field."""
        self._page.fill(self._TITLE_INPUT, title)

    def fill_description(self, description: str) -> None:
        """Fill the description textarea."""
        self._page.fill(self._DESCRIPTION_INPUT, description)

    def select_category(self, value: str) -> None:
        """Select a category by its option value (e.g. '1' for Education)."""
        self._page.select_option(self._CATEGORY_SELECT, value=value)

    def fill_tags(self, tags: str) -> None:
        """Fill the tags input with comma-separated tag string."""
        self._page.fill(self._TAGS_INPUT, tags)

    def click_upload(self) -> None:
        """Click the Upload video submit button."""
        self._page.click(self._UPLOAD_BUTTON)

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
    # Progress bar observations
    # ------------------------------------------------------------------

    def is_progress_visible(self) -> bool:
        """Return True when the progress bar container is present and visible."""
        locator = self._page.locator(self._PROGRESS_CONTAINER)
        return locator.count() > 0 and locator.first.is_visible()

    def get_progress_value(self) -> Optional[int]:
        """Return the current aria-valuenow attribute of the progressbar, or None."""
        locator = self._page.locator(self._PROGRESS_BAR)
        if locator.count() == 0:
            return None
        raw = locator.first.get_attribute("aria-valuenow")
        return int(raw) if raw is not None else None

    def get_progress_percentage_text(self) -> Optional[str]:
        """Return the percentage text shown next to the progress bar (e.g. '42%').

        Returns None if the container or span is not present (e.g. page
        navigated away after upload completion).
        """
        container = self._page.locator(self._PROGRESS_CONTAINER)
        if container.count() == 0:
            return None
        # The percentage span is the second <span> inside the flex header row.
        # Use a short timeout so we don't block if the element disappears.
        spans = container.locator("span")
        if spans.count() < 2:
            return None
        try:
            return spans.nth(1).text_content(timeout=2_000)
        except Exception:
            return None

    def get_phase_text(self) -> Optional[str]:
        """Return the phase label text ('Uploading…' or 'Upload complete').

        Returns None if the container is not present.
        """
        container = self._page.locator(self._PROGRESS_CONTAINER)
        if container.count() == 0:
            return None
        spans = container.locator("span")
        if spans.count() == 0:
            return None
        try:
            return spans.first.text_content(timeout=2_000)
        except Exception:
            return None

    def snapshot_progress(self) -> UploadProgressSnapshot:
        """Capture a point-in-time snapshot of the progress bar state."""
        return UploadProgressSnapshot(
            progress_visible=self.is_progress_visible(),
            aria_value_now=self.get_progress_value(),
            percentage_text=self.get_progress_percentage_text(),
            phase_text=self.get_phase_text(),
        )

    def wait_for_progress_visible(self, timeout: float = 30_000) -> None:
        """Block until the upload progress container appears in the DOM."""
        self._page.locator(self._PROGRESS_CONTAINER).wait_for(
            state="visible", timeout=timeout
        )

    def wait_for_upload_complete(self, timeout: float = 120_000) -> None:
        """Block until the upload is considered complete.

        Completion is defined as one of:
        - The phase label 'Upload complete' is visible in the progress container, OR
        - The page navigates away from /upload (which happens on success after
          router.replace('/dashboard?uploaded=...')).

        This dual condition handles the case where the upload finishes so
        quickly that the page navigates before the 'Upload complete' label is
        observable.
        """
        try:
            self._page.locator(self._PROGRESS_CONTAINER).locator(
                "span", has_text="Upload complete"
            ).wait_for(state="visible", timeout=timeout)
        except Exception:
            # If the 'Upload complete' label is not visible, accept navigation
            # away from /upload as implicit completion.
            current = self._page.url
            if "/upload" not in current:
                return  # Navigated away successfully — upload completed
            raise  # Unexpected state: still on /upload but no complete label

    def collect_progress_snapshots(
        self,
        interval_ms: int = 200,
        max_snapshots: int = 50,
    ) -> list[UploadProgressSnapshot]:
        """
        Poll the progress bar repeatedly while uploading and return a list of
        snapshots captured at *interval_ms* intervals.

        Stops early when:
        - 'Upload complete' is detected in the phase text, OR
        - The page navigates away from /upload (implicit completion), OR
        - *max_snapshots* is reached.
        """
        snapshots: list[UploadProgressSnapshot] = []
        for _ in range(max_snapshots):
            # Stop if we've navigated away from the upload page
            if "/upload" not in self._page.url:
                break
            snap = self.snapshot_progress()
            snapshots.append(snap)
            if snap.phase_text and "complete" in snap.phase_text.lower():
                break
            self._page.wait_for_timeout(interval_ms)
        return snapshots

    # ------------------------------------------------------------------
    # State queries
    # ------------------------------------------------------------------

    def current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url

    def is_on_login_page(self) -> bool:
        """Return True if the browser has been redirected to the /login page."""
        return "/login" in self._page.url

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

    def is_upload_button_enabled(self) -> bool:
        """Return True when the upload submit button is enabled."""
        return self._page.locator(self._UPLOAD_BUTTON).is_enabled()

    def is_upload_button_disabled(self) -> bool:
        """Return True when the upload submit button is disabled."""
        return not self._page.locator(self._UPLOAD_BUTTON).is_enabled()

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

    def is_form_visible(self) -> bool:
        """Return True when the file input is present in the DOM."""
        return self._page.locator(self._FILE_INPUT).count() > 0

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
