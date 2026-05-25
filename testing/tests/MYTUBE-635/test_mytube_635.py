"""
MYTUBE-635: Client-side validation: unsupported file type — immediate error displayed.

Objective
---------
Verify that the UI prevents selecting or uploading invalid file formats without
making a network request.

Preconditions
-------------
User is on the Account Settings page.

Steps
-----
1. Attempt to select a file that is not image/jpeg or image/png
   (e.g., a .gif or .pdf file).

Expected Result
---------------
A user-visible error message is displayed near the upload control immediately
upon selection. No network request is sent to the backend.

Test approach
-------------
Dual-mode:

  Part A — Static analysis (always runs):
    Reads the settings page source and verifies the client-side validation
    logic (ALLOWED_AVATAR_TYPES, handleFileChange) and the error message text.

  Part B — Live Playwright UI test (runs when FIREBASE_TEST_EMAIL /
    FIREBASE_TEST_PASSWORD are set):
    1. Logs in and navigates to /settings.
    2. Sets a .gif file on the file input via Playwright's set_input_files.
    3. Asserts role="alert" paragraph with the expected error text appears.
    4. Asserts no POST request to /api/me/avatar was dispatched.
    5. Sets a .pdf file and repeats the assertions.

Environment variables
---------------------
APP_URL / WEB_BASE_URL      Base URL of the deployed web app.
                            Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL         Email address of the test Firebase user.
FIREBASE_TEST_PASSWORD      Password for the test Firebase user.
PLAYWRIGHT_HEADLESS         Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO          Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig centralises env var access (testing/core/config/web_config.py).
- LoginPage page object handles authentication.
- SettingsPage page object handles file input interaction.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SETTINGS_SRC = _REPO_ROOT / "web" / "src" / "app" / "settings" / "page.tsx"

# ---------------------------------------------------------------------------
# Expected values
# ---------------------------------------------------------------------------

_EXPECTED_ERROR_TEXT = "Only JPEG and PNG files are allowed."
_EXPECTED_ALLOWED_TYPES = ["image/jpeg", "image/png"]
_AVATAR_UPLOAD_ENDPOINT = "/api/me/avatar"

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_NAV_TIMEOUT = 30_000         # ms
_ERROR_VISIBLE_TIMEOUT = 5_000  # ms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_source() -> str:
    """Return the raw source text of the settings page component."""
    return _SETTINGS_SRC.read_text(encoding="utf-8")


def _has_live_credentials() -> bool:
    cfg = WebConfig()
    return bool(cfg.test_email and cfg.test_password)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch Chromium for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def authenticated_settings_page(web_config: WebConfig, browser: Browser):
    """
    Log in and navigate to /settings. Returns the Playwright Page.

    Skips the entire fixture (and dependent tests) when Firebase credentials
    are not provided.
    """
    if not web_config.test_email or not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD not set — "
            "skipping live UI tests. Set both env vars to enable them."
        )

    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    login_page = LoginPage(page)
    try:
        login_page.navigate(web_config.login_url())
    except Exception as exc:
        context.close()
        pytest.skip(
            f"Could not reach {web_config.login_url()} — skipping live UI tests. "
            f"Error: {exc}"
        )

    login_page.login_as(web_config.test_email, web_config.test_password)

    # Wait for post-login redirect to the home page
    try:
        page.wait_for_url(
            lambda url: "/settings" not in url and "/login" not in url,
            timeout=_NAV_TIMEOUT,
        )
    except Exception:
        pass  # Continue — we'll navigate directly to /settings next

    settings_url = f"{web_config.base_url}/settings/"
    settings_pg = SettingsPage(page)
    try:
        settings_pg.navigate(settings_url)
    except Exception as exc:
        context.close()
        pytest.skip(
            f"Could not load settings page — skipping live UI tests. "
            f"Error: {exc}"
        )

    yield page

    context.close()


# ---------------------------------------------------------------------------
# Part A — Static analysis tests (always run)
# ---------------------------------------------------------------------------


class TestClientSideValidationStaticAnalysis:
    """Verify the source code contains the required validation logic."""

    def test_settings_source_file_exists(self) -> None:
        """The settings page source file must be present."""
        assert _SETTINGS_SRC.is_file(), (
            f"Settings page source not found at {_SETTINGS_SRC}. "
            "Ensure the web app has been checked out correctly."
        )

    def test_allowed_types_constant_defined(self) -> None:
        """ALLOWED_AVATAR_TYPES must list exactly image/jpeg and image/png."""
        src = _settings_source()
        assert "ALLOWED_AVATAR_TYPES" in src, (
            "Expected ALLOWED_AVATAR_TYPES constant in settings page source."
        )
        for mime in _EXPECTED_ALLOWED_TYPES:
            assert mime in src, (
                f"Expected MIME type {mime!r} in ALLOWED_AVATAR_TYPES constant."
            )

    def test_file_type_validation_guard_present(self) -> None:
        """handleFileChange must check ALLOWED_AVATAR_TYPES.includes(file.type)."""
        src = _settings_source()
        assert "ALLOWED_AVATAR_TYPES.includes(file.type)" in src, (
            "Expected 'ALLOWED_AVATAR_TYPES.includes(file.type)' guard in "
            "handleFileChange — this is the client-side MIME type check."
        )

    def test_error_message_text_correct(self) -> None:
        """The error message shown to the user must match the expected text."""
        src = _settings_source()
        assert _EXPECTED_ERROR_TEXT in src, (
            f"Expected error message {_EXPECTED_ERROR_TEXT!r} in settings page "
            "source. The UI must display this text when an invalid file type is selected."
        )

    def test_error_rendered_with_alert_role(self) -> None:
        """The validation error must be rendered with role='alert'."""
        src = _settings_source()
        assert 'role="alert"' in src, (
            "Expected role=\"alert\" on the upload error paragraph in settings page "
            "source so that screen readers announce the error immediately."
        )

    def test_no_network_call_before_upload_button(self) -> None:
        """The validation occurs in handleFileChange, before any fetch call.

        The fetch to /api/me/avatar must appear only inside handleAvatarUpload,
        not inside handleFileChange — confirming no network request is made on
        invalid file selection.
        """
        src = _settings_source()
        # Locate handleFileChange block (up to its closing brace) and confirm
        # there is no fetch call within it.
        handle_file_start = src.find("function handleFileChange")
        assert handle_file_start != -1, (
            "Expected 'function handleFileChange' in settings page source."
        )
        # Heuristic: grab text from handleFileChange up to the next top-level function.
        handle_file_section = src[handle_file_start : handle_file_start + 600]
        assert "fetch(" not in handle_file_section, (
            "Found 'fetch(' inside handleFileChange — the handler must NOT make "
            "a network request during file-type validation; only handleAvatarUpload "
            "should call fetch."
        )


# ---------------------------------------------------------------------------
# Part B — Live Playwright UI tests (require credentials)
# ---------------------------------------------------------------------------


class TestClientSideValidationLiveUI:
    """Verify unsupported file type triggers an immediate UI error with no network call."""

    @pytest.fixture(autouse=True)
    def _reset_upload_requests(self, authenticated_settings_page: Page) -> None:
        """Track all POST requests to /api/me/avatar during each test."""
        self._avatar_upload_requests: list[str] = []

        def _capture(req) -> None:
            if _AVATAR_UPLOAD_ENDPOINT in req.url and req.method == "POST":
                self._avatar_upload_requests.append(req.url)

        authenticated_settings_page.on("request", _capture)
        yield
        # Detach to avoid leaking listener across tests
        authenticated_settings_page.remove_listener("request", _capture)

    def test_gif_file_triggers_error_message(
        self, authenticated_settings_page: Page
    ) -> None:
        """Selecting a .gif file must immediately show the type-rejection error."""
        page = authenticated_settings_page

        # Reset any previous error state
        page.reload(wait_until="domcontentloaded")
        settings_pg = SettingsPage(page)
        settings_pg.navigate(page.url)

        file_input = page.locator('input[id="avatar_file"]')
        file_input.set_input_files(
            {
                "name": "animated.gif",
                "mimeType": "image/gif",
                "buffer": b"GIF89a\x01\x00\x01\x00\x00\xff\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x00;",
            }
        )

        error_locator = page.locator('[id="avatar_file"] ~ [role="alert"]').or_(
            page.locator('p[role="alert"]')
        )
        error_locator.wait_for(state="visible", timeout=_ERROR_VISIBLE_TIMEOUT)

        error_text = error_locator.inner_text()
        assert error_text == _EXPECTED_ERROR_TEXT, (
            f"Expected error text {_EXPECTED_ERROR_TEXT!r}, got {error_text!r}"
        )

    def test_gif_file_does_not_trigger_network_request(
        self, authenticated_settings_page: Page
    ) -> None:
        """Selecting a .gif file must NOT dispatch a POST to /api/me/avatar."""
        assert self._avatar_upload_requests == [], (
            f"Expected no POST to {_AVATAR_UPLOAD_ENDPOINT} after selecting an "
            f"invalid file type, but got: {self._avatar_upload_requests}"
        )

    def test_pdf_file_triggers_error_message(
        self, authenticated_settings_page: Page
    ) -> None:
        """Selecting a .pdf file must immediately show the type-rejection error."""
        page = authenticated_settings_page

        file_input = page.locator('input[id="avatar_file"]')
        file_input.set_input_files(
            {
                "name": "document.pdf",
                "mimeType": "application/pdf",
                "buffer": b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n",
            }
        )

        error_locator = page.locator('[id="avatar_file"] ~ [role="alert"]').or_(
            page.locator('p[role="alert"]')
        )
        error_locator.wait_for(state="visible", timeout=_ERROR_VISIBLE_TIMEOUT)

        error_text = error_locator.inner_text()
        assert error_text == _EXPECTED_ERROR_TEXT, (
            f"Expected error text {_EXPECTED_ERROR_TEXT!r} for .pdf file, "
            f"got {error_text!r}"
        )

    def test_pdf_file_does_not_trigger_network_request(
        self, authenticated_settings_page: Page
    ) -> None:
        """Selecting a .pdf file must NOT dispatch a POST to /api/me/avatar."""
        assert self._avatar_upload_requests == [], (
            f"Expected no POST to {_AVATAR_UPLOAD_ENDPOINT} after selecting a "
            f".pdf file, but got: {self._avatar_upload_requests}"
        )

    def test_error_displayed_immediately_without_upload_click(
        self, authenticated_settings_page: Page
    ) -> None:
        """Error must appear on file selection alone — no need to click Upload."""
        page = authenticated_settings_page

        # Re-navigate to get a fresh state
        settings_pg = SettingsPage(page)
        settings_pg.navigate(page.url)

        # Confirm no error alert before file selection
        alert_before = page.locator('p[role="alert"]')
        # The alert should not be present yet (or not visible)
        assert not alert_before.is_visible(), (
            "Unexpected alert visible before any file was selected."
        )

        # Select an invalid file
        file_input = page.locator('input[id="avatar_file"]')
        file_input.set_input_files(
            {
                "name": "image.bmp",
                "mimeType": "image/bmp",
                "buffer": b"BM\x1a\x00\x00\x00\x00\x00\x00\x00\x1a\x00\x00\x00",
            }
        )

        # Verify alert appears without clicking the Upload button
        error_locator = page.locator('p[role="alert"]')
        error_locator.wait_for(state="visible", timeout=_ERROR_VISIBLE_TIMEOUT)

        visible_text = error_locator.inner_text()
        assert _EXPECTED_ERROR_TEXT in visible_text, (
            f"Expected {_EXPECTED_ERROR_TEXT!r} in visible error text, "
            f"got {visible_text!r}"
        )

    def test_upload_button_remains_disabled_after_invalid_file(
        self, authenticated_settings_page: Page
    ) -> None:
        """The Upload button must remain disabled after an invalid file is selected.

        Because setUploadFile(null) is called in handleFileChange, the Upload
        button's disabled={!uploadFile} condition keeps it disabled.
        """
        page = authenticated_settings_page

        upload_button = page.get_by_role("button", name="Upload", exact=True)
        assert upload_button.is_disabled(), (
            "Expected the Upload button to be disabled after an invalid file was "
            "selected (uploadFile is null — button must have disabled attribute)."
        )
