"""
MYTUBE-140: Upload file with unsupported MIME type — system prevents upload or returns error.

Verifies that the upload page only accepts specific video file formats (MP4, MOV,
AVI, WebM) and rejects unsupported types such as PDF and PNG by displaying a
validation error message and clearing the selected file.

Preconditions
-------------
- A user account is already registered in Firebase.
- The web application is deployed and reachable at WEB_BASE_URL.
- The user must be authenticated to access /upload.

Test steps
----------
1. Log in using test Firebase credentials.
2. Navigate to the /upload page.
3. Simulate selecting an unsupported file (document.pdf, MIME: application/pdf).
4. Assert that a validation error message is displayed mentioning supported formats.
5. Navigate again and simulate selecting another unsupported file (image.png).
6. Assert that a validation error message is displayed.
7. Assert that the file input ``accept`` attribute only lists supported MIME types.

Environment variables
---------------------
- FIREBASE_TEST_EMAIL    : Email of the registered Firebase test user (required).
- FIREBASE_TEST_PASSWORD : Password of the registered Firebase test user (required).
- WEB_BASE_URL           : Base URL of the deployed web app.
                           Default: https://ai-teammate.github.io/mytube
- PLAYWRIGHT_HEADLESS    : Run browser headless (default: true).
- PLAYWRIGHT_SLOW_MO     : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses LoginPage (Page Object) to authenticate before navigating to /upload.
- Uses UploadPage (Page Object) from testing/components/pages/upload_page/.
- WebConfig from testing/core/config/web_config.py centralises all env var access.
- Playwright sync API with pytest-style fixtures.
- No hardcoded URLs or credentials.
"""
import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.upload_page.upload_page import UploadPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_NAVIGATION_TIMEOUT = 20_000  # ms — max time to wait for post-login redirect

# MIME types under test
_UNSUPPORTED_MIME_PDF = "application/pdf"
_UNSUPPORTED_MIME_PNG = "image/png"

_SUPPORTED_MIMES = {
    "video/mp4",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are not provided."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping upload MIME type test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping upload MIME type test. "
            "Set FIREBASE_TEST_PASSWORD to run this test."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def authenticated_page(browser: Browser, web_config: WebConfig) -> Page:
    """Open a browser context, log in once, and yield the authenticated page.

    All tests in this module share this authenticated session — login is
    executed exactly once per test run.
    """
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    login_page = LoginPage(pg)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)

    yield pg
    context.close()


@pytest.fixture(scope="function")
def upload_page(authenticated_page: Page) -> UploadPage:
    return UploadPage(authenticated_page)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _upload_url(web_config: WebConfig) -> str:
    return web_config.base_url.rstrip("/") + "/upload/"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadUnsupportedMimeType:
    """MYTUBE-140: Upload file with unsupported MIME type is rejected."""

    def test_pdf_file_triggers_mime_error(
        self, upload_page: UploadPage, web_config: WebConfig
    ):
        """Selecting a PDF file must display a MIME type validation error."""
        upload_page.navigate(_upload_url(web_config))
        assert upload_page.is_upload_form_visible(), (
            "Upload form is not visible — ensure the user is authenticated and "
            "/upload page is accessible."
        )

        upload_page.set_input_file_by_mime(
            filename="document.pdf",
            mime_type=_UNSUPPORTED_MIME_PDF,
            content=b"%PDF-1.4 fake pdf content",
        )

        assert upload_page.has_mime_error(), (
            "Expected a MIME type validation error after selecting a PDF file, "
            "but no error alert was displayed."
        )

        error_text = upload_page.get_mime_error_message()
        assert error_text is not None
        assert any(
            fmt.lower() in error_text.lower()
            for fmt in ("mp4", "mov", "avi", "webm")
        ), (
            f"Error message does not mention supported formats. Got: {error_text!r}"
        )

    def test_png_file_triggers_mime_error(
        self, upload_page: UploadPage, web_config: WebConfig
    ):
        """Selecting a PNG image must display a MIME type validation error."""
        upload_page.navigate(_upload_url(web_config))
        assert upload_page.is_upload_form_visible(), (
            "Upload form is not visible — ensure the user is authenticated and "
            "/upload page is accessible."
        )

        upload_page.set_input_file_by_mime(
            filename="image.png",
            mime_type=_UNSUPPORTED_MIME_PNG,
            content=b"\x89PNG\r\n\x1a\n fake png content",
        )

        assert upload_page.has_mime_error(), (
            "Expected a MIME type validation error after selecting a PNG image, "
            "but no error alert was displayed."
        )

    def test_file_input_accept_attribute_restricts_types(
        self, upload_page: UploadPage, web_config: WebConfig
    ):
        """The file input ``accept`` attribute must only list supported video MIME types."""
        upload_page.navigate(_upload_url(web_config))
        assert upload_page.is_upload_form_visible(), (
            "Upload form is not visible — ensure the user is authenticated and "
            "/upload page is accessible."
        )

        accept = upload_page.get_file_input_accept_attribute()
        assert accept is not None, (
            "File input is missing the ``accept`` attribute."
        )

        declared_types = {t.strip() for t in accept.split(",")}
        assert declared_types == _SUPPORTED_MIMES, (
            f"File input ``accept`` attribute mismatch.\n"
            f"  Expected: {_SUPPORTED_MIMES}\n"
            f"  Got:      {declared_types}"
        )
