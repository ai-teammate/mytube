"""
MYTUBE-596: Interact with Choose File button — button is clickable and opens file picker

Objective
---------
Verify that the newly styled Choose File button remains functional and correctly
triggers the system file selection dialog.

Preconditions
-------------
User is on the /upload page.

Steps
-----
1. Click directly on the styled Choose File button.
2. Select a valid video file from the OS file picker.

Expected Result
---------------
The OS file picker dialog opens immediately upon clicking the button. After selecting
a file, the text next to the button updates from "no file selected" to the name of
the chosen file.

Test Approach
-------------
Two complementary layers:

**Layer A — Static CSS analysis** (always runs):
  - Reads ``upload.module.css`` from the web source tree.
  - Verifies the ``::file-selector-button`` pseudo-element rule is present inside the
    ``.fileInput`` selector (fix for MYTUBE-591 must be in place).
  - Verifies the rule contains ``background`` and ``color`` declarations.

**Layer B — Live browser test** (runs when the app is reachable):
  - Registers a temporary user via /register so the test is self-contained.
  - Navigates to /upload.
  - Uses ``page.expect_file_chooser()`` to intercept the file chooser dialog that
    opens when the file input is clicked.
  - Sets a minimal valid MP4 fixture file via the intercepted file chooser.
  - Asserts the hint text (``<p class="tiny">``) now shows the fixture filename,
    confirming that clicking the button opened the dialog and that file selection
    updates the displayed filename.

Architecture
------------
- UploadPage from testing/components/pages/upload_page/upload_page.py.
- RegisterPage from testing/components/pages/register_page/register_page.py.
- UploadCSSModule from testing/components/pages/upload_page/upload_css_module.py.
- WebConfig from testing/core/config/web_config.py.
- Playwright sync API with pytest-style fixtures.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-596/test_mytube_596.py -v
"""
from __future__ import annotations

import os
import sys
import tempfile
import urllib.request
import uuid

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.register_page.register_page import RegisterPage
from testing.components.pages.upload_page.upload_page import UploadPage
from testing.components.pages.upload_page.upload_css_module import UploadCSSModule

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_FILE_CHOOSER_TIMEOUT = 5_000 # ms — max time to wait for file chooser to appear
_FIXTURE_VIDEO_FILENAME = "test_clip.mp4"

# Minimal valid MP4 header bytes (ftyp box — isom brand).
# Large enough for the file input to accept without triggering size warnings.
_MINIMAL_MP4_BYTES: bytes = (
    b"\x00\x00\x00\x20"  # box size = 32
    b"ftyp"               # box type
    b"isom"               # major brand
    b"\x00\x00\x02\x00"  # minor version
    b"isom"               # compatible brand 1
    b"iso2"               # compatible brand 2
    b"mp41"               # compatible brand 3
    + b"\x00" * 1024      # padding to make it a plausible small video file
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_reachable(url: str, timeout: int = 10) -> bool:
    """Return True if *url* responds with an HTTP status below 500."""
    try:
        res = urllib.request.urlopen(url, timeout=timeout)
        return res.status < 500
    except Exception:
        return False


def _create_fixture_video_file() -> str:
    """Write a minimal MP4 fixture to a temp file and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=".mp4", prefix="mytube596_"
    )
    tmp.write(_MINIMAL_MP4_BYTES)
    tmp.flush()
    tmp.close()
    return tmp.name


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def app_reachable(config: WebConfig) -> bool:
    return _is_url_reachable(config.home_url())


@pytest.fixture(scope="module")
def browser_instance(config: WebConfig):
    """Launch a Chromium browser instance shared across all tests in the module."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def authenticated_page(config: WebConfig, browser_instance: Browser, app_reachable: bool):
    """Return a Page that is already authenticated via a freshly registered account.

    Skips (not fails) when the app is unreachable so that the static CSS
    analysis tests can still run in isolation.
    """
    if not app_reachable:
        pytest.skip("Application is not reachable — skipping live browser tests.")

    page = browser_instance.new_page(viewport={"width": 1280, "height": 800})
    register_page = RegisterPage(page)

    try:
        register_page.navigate(config.register_url())
    except Exception as exc:
        pytest.skip(
            f"Could not reach {config.register_url()} — skipping live browser tests. Error: {exc}"
        )

    if not register_page.is_on_register_page():
        # Fallback: check for presence of the email/password form directly,
        # as `is_on_register_page()` may not match if the heading text differs.
        email_input_count = page.locator('input[type="email"]').count()
        password_input_count = page.locator('input[type="password"]').count()
        if email_input_count == 0 or password_input_count == 0:
            pytest.skip(
                "Registration page did not load (no email/password inputs found) — "
                f"current URL: {register_page.current_url()}"
            )

    # Register a temporary test account (no pre-existing credentials needed).
    unique_suffix = uuid.uuid4().hex[:8]
    test_email = f"mytube596.{unique_suffix}@test.invalid"
    test_password = "Test@1234!"

    result = register_page.register_and_capture(
        email=test_email,
        password=test_password,
        base_url=config.base_url,
        timeout_ms=_PAGE_LOAD_TIMEOUT,
    )

    if not result.redirected_away:
        error = result.error_message or "Unknown error"
        pytest.skip(
            f"Registration did not redirect — cannot test upload. "
            f"Error: {error!r}. Final URL: {result.final_url}"
        )

    yield page
    page.close()


# ---------------------------------------------------------------------------
# Layer A — Static CSS analysis (always runs)
# ---------------------------------------------------------------------------


class TestUploadButtonCSSLayer:
    """MYTUBE-596 Layer A: Verify ::file-selector-button is styled in the CSS module."""

    def test_file_selector_button_rule_exists(self) -> None:
        """The upload.module.css must contain a ::file-selector-button rule.

        This confirms the MYTUBE-591 fix is present: the button cannot be
        clickable if it is invisible due to missing styling.
        """
        css = UploadCSSModule()
        assert css.file_exists(), (
            "upload.module.css was not found at the expected path. "
            "Ensure the web source is present."
        )
        css_text = css._css_text  # raw text for pseudo-element checking

        assert "::file-selector-button" in css_text, (
            "::file-selector-button pseudo-element rule is missing from upload.module.css. "
            "The MYTUBE-591 fix must add styling so the Choose File button is visible "
            "and clickable."
        )

    def test_file_selector_button_has_background(self) -> None:
        """The ::file-selector-button rule must declare a background property.

        A visible background is required so the button is distinguishable
        from the card background in dark mode.
        """
        css = UploadCSSModule()
        css_text = css._css_text

        # Extract the rule block for ::file-selector-button
        import re
        pattern = r"::file-selector-button\s*\{([^}]*)\}"
        matches = re.findall(pattern, css_text, re.DOTALL | re.IGNORECASE)
        assert matches, (
            "::file-selector-button rule block not found in upload.module.css."
        )
        rule_body = matches[0].lower()
        assert "background" in rule_body, (
            "::file-selector-button rule does not declare a 'background' property. "
            "The button will be invisible without a contrasting background. "
            f"Rule body found: {matches[0]!r}"
        )

    def test_file_selector_button_has_color(self) -> None:
        """The ::file-selector-button rule must declare a color property.

        The text colour must be explicitly set to ensure readability
        regardless of the browser theme.
        """
        css = UploadCSSModule()
        css_text = css._css_text

        import re
        pattern = r"::file-selector-button\s*\{([^}]*)\}"
        matches = re.findall(pattern, css_text, re.DOTALL | re.IGNORECASE)
        assert matches, (
            "::file-selector-button rule block not found in upload.module.css."
        )
        rule_body = matches[0].lower()
        assert "color" in rule_body, (
            "::file-selector-button rule does not declare a 'color' property. "
            f"Rule body found: {matches[0]!r}"
        )


# ---------------------------------------------------------------------------
# Layer B — Live browser interaction (runs when app is reachable)
# ---------------------------------------------------------------------------


class TestUploadButtonInteractionLayer:
    """MYTUBE-596 Layer B: Verify the Choose File button is clickable and triggers file picker."""

    def test_upload_page_is_accessible_when_authenticated(
        self, authenticated_page: Page, config: WebConfig
    ) -> None:
        """Pre-condition: authenticated user can reach the /upload page.

        Navigates to /upload and asserts the upload form (file input) is visible.
        """
        upload = UploadPage(authenticated_page)
        upload.navigate(config.base_url)

        assert upload.is_upload_form_visible(), (
            "Upload form (file input) is not visible after navigating to /upload. "
            f"Current URL: {upload.current_url()}"
        )

    def test_choose_file_button_triggers_file_chooser(
        self, authenticated_page: Page, config: WebConfig
    ) -> None:
        """Clicking the Choose File button must open the OS file picker dialog.

        Uses page.expect_file_chooser() to intercept the file chooser that the
        browser opens when the file input is clicked.  If the button is invisible
        or non-interactive, no file chooser event will fire and the assertion fails.
        """
        page = authenticated_page
        upload = UploadPage(page)
        upload.navigate(config.base_url)

        # Ensure the file input is present and visible
        file_input = page.locator('input[id="video-file"]')
        file_input.wait_for(state="attached", timeout=_PAGE_LOAD_TIMEOUT)

        # Click the file input and intercept the file chooser dialog.
        # expect_file_chooser raises an error if no chooser appears within the timeout.
        try:
            with page.expect_file_chooser(timeout=_FILE_CHOOSER_TIMEOUT) as fc_info:
                file_input.click()
            file_chooser = fc_info.value
        except Exception as exc:
            pytest.fail(
                f"No file chooser dialog appeared within {_FILE_CHOOSER_TIMEOUT}ms "
                f"after clicking the Choose File button (input#video-file). "
                f"The button may be invisible, disabled, or non-interactive. "
                f"Error: {exc}"
            )

        assert file_chooser is not None, (
            "File chooser dialog was not intercepted after clicking input#video-file."
        )

    def test_file_selection_updates_filename_hint(
        self, authenticated_page: Page, config: WebConfig
    ) -> None:
        """After selecting a file via the file picker, the filename hint must appear.

        Steps:
        1. Navigate to /upload.
        2. Open the file chooser by clicking the file input.
        3. Select a minimal MP4 fixture file via the intercepted chooser.
        4. Assert the hint paragraph shows the fixture filename (confirming the
           React onChange handler fired and updated the UI state).

        This verifies the full interaction chain: visible button → clickable →
        file chooser opens → file selected → UI updates.
        """
        page = authenticated_page
        upload = UploadPage(page)
        upload.navigate(config.base_url)

        fixture_path = _create_fixture_video_file()
        try:
            file_input = page.locator('input[id="video-file"]')
            file_input.wait_for(state="attached", timeout=_PAGE_LOAD_TIMEOUT)

            # Intercept the file chooser and set the fixture file.
            with page.expect_file_chooser(timeout=_FILE_CHOOSER_TIMEOUT) as fc_info:
                file_input.click()
            file_chooser = fc_info.value
            file_chooser.set_files(fixture_path)

            # After file selection, the React component renders a hint paragraph:
            #   <p class="tiny">{file.name} ({size} MB)</p>
            # Wait briefly for the React state update to re-render.
            page.wait_for_timeout(500)

            # Check: the hint paragraph containing the fixture filename is visible.
            filename_only = os.path.basename(fixture_path)
            hint_locator = page.locator("p").filter(has_text=filename_only)
            count = hint_locator.count()

            if count == 0:
                # Fallback: check via native input value to distinguish "chooser opened
                # but React didn't update" from "chooser never opened".
                native_value = file_input.evaluate("el => el.files && el.files.length > 0")
                assert native_value, (
                    f"File chooser was opened and set_files('{filename_only}') was called, "
                    f"but the file input still has no files. "
                    f"The onClick handler or onChange handler may be broken."
                )
                # If the native input has the file but React hint isn't shown, that is still
                # a bug — the UI must update to show the selected filename.
                pytest.fail(
                    f"File was selected successfully (input.files.length > 0) but the "
                    f"filename hint paragraph was not rendered. "
                    f"Expected to see a <p> element containing '{filename_only}' after "
                    f"file selection. The React onChange handler or the conditional render "
                    f"({'{file && (<p ...>{file.name}</p>)}'}) may not be functioning. "
                    f"Current URL: {upload.current_url()}"
                )

            hint_locator.first.wait_for(state="visible", timeout=3_000)

        finally:
            # Clean up the temp file.
            try:
                os.unlink(fixture_path)
            except OSError:
                pass
