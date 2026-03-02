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
    """Page Object for the MyTube upload page (/upload)."""

    # Selectors
    _FILE_INPUT = 'input[id="video-file"]'
    _TITLE_INPUT = 'input[id="title"]'
    _DESCRIPTION_INPUT = 'textarea[id="description"]'
    _CATEGORY_SELECT = 'select[id="categoryId"]'
    _TAGS_INPUT = 'input[id="tags"]'
    _UPLOAD_BUTTON = 'button[type="submit"]'
    _PROGRESS_BAR = '[role="progressbar"]'
    _PROGRESS_CONTAINER = '[aria-label="upload progress"]'
    _ERROR_ALERT = '[role="alert"]'

    def __init__(self, page: Page) -> None:
        self._page = page

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def navigate(self, url: str) -> None:
        """Navigate the browser to the upload page URL.

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

    def set_file(self, file_path: str) -> None:
        """Attach a local file to the hidden file input."""
        self._page.set_input_files(self._FILE_INPUT, file_path)

    def fill_title(self, title: str) -> None:
        """Type *title* into the title input field."""
        self._page.fill(self._TITLE_INPUT, title)

    def fill_description(self, description: str) -> None:
        """Type *description* into the description textarea."""
        self._page.fill(self._DESCRIPTION_INPUT, description)

    def select_category(self, value: str) -> None:
        """Select a category by its option value (e.g. '1' for Education)."""
        self._page.select_option(self._CATEGORY_SELECT, value=value)

    def fill_tags(self, tags: str) -> None:
        """Type comma-separated tags into the tags input field."""
        self._page.fill(self._TAGS_INPUT, tags)

    def click_upload(self) -> None:
        """Click the Upload Video submit button."""
        self._page.click(self._UPLOAD_BUTTON)

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

    def is_upload_button_enabled(self) -> bool:
        """Return True when the upload submit button is enabled."""
        return self._page.locator(self._UPLOAD_BUTTON).is_enabled()

    def is_upload_button_disabled(self) -> bool:
        """Return True when the upload submit button is disabled."""
        return not self._page.locator(self._UPLOAD_BUTTON).is_enabled()

    def get_error_message(self) -> Optional[str]:
        """Return the visible error alert text, or None if no alert is shown."""
        locator = self._page.locator(self._ERROR_ALERT)
        if locator.count() == 0:
            return None
        text = locator.text_content()
        return text if text else None

    def is_form_visible(self) -> bool:
        """Return True when the file input is present in the DOM."""
        return self._page.locator(self._FILE_INPUT).count() > 0

    def get_current_url(self) -> str:
        """Return the current browser URL."""
        return self._page.url
