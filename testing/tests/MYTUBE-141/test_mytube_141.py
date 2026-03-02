"""
MYTUBE-141: Select video file larger than 4 GB — client-side size limit warning displayed.

Verifies that the /upload page displays a warning message when the user selects
a video file that exceeds 4 GB in size, without requiring an actual multi-GB file.

Preconditions
-------------
- A registered Firebase user is available (FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD).
- The web application is deployed and reachable at WEB_BASE_URL.
- The /upload page requires authentication; test authenticates via /login first.

Test steps
----------
1. Navigate to the /login page and sign in with valid credentials.
2. Navigate to the /upload page.
3. Simulate selecting a video file that exceeds 4 GB in size.
4. Assert a warning message (role="note") is displayed on the page.
5. Assert the warning message contains "larger than 4.0 GB".

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
- Uses LoginPage (Page Object) from testing/components/pages/login_page/.
- Uses UploadPage (Page Object) from testing/components/pages/upload_page/.
- WebConfig from testing/core/config/web_config.py centralises all env var access.
- Playwright sync API with pytest-style fixtures.
- No hardcoded URLs or credentials.
- File size is simulated via JavaScript to avoid needing a real 4 GB file.
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

_NAVIGATION_TIMEOUT = 30_000   # ms — max time to wait for post-login redirect
_PAGE_LOAD_TIMEOUT = 30_000    # ms — max time for initial page load

# 4 GB in bytes + 1 to exceed the limit
_FOUR_GB = 4 * 1024 * 1024 * 1024
_FILE_SIZE_OVER_LIMIT = _FOUR_GB + 1

# Expected warning text fragment from the upload page source:
# "Warning: file is larger than 4.0 GB. Uploads may take a long time on slow connections."
_EXPECTED_WARNING_FRAGMENT = "larger than 4.0 GB"


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
            "FIREBASE_TEST_EMAIL not set — skipping test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping test. "
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
def page(browser: Browser) -> Page:
    """Open a fresh browser context and page."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def authenticated_page(web_config: WebConfig, page: Page) -> Page:
    """Sign in via /login and return the authenticated page.

    Performs login once for the entire module so all tests share a
    single authenticated session.
    """
    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)
    return page


@pytest.fixture(scope="module")
def upload_page(authenticated_page: Page, web_config: WebConfig) -> UploadPage:
    """Navigate to /upload and return the UploadPage object."""
    up = UploadPage(authenticated_page)
    up.navigate(web_config.base_url.rstrip("/") + "/upload/")
    return up


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFileSizeLimitWarning:
    """MYTUBE-141: File size warning is shown for files exceeding 4 GB."""

    def test_warning_is_displayed_for_file_over_4gb(self, upload_page: UploadPage):
        """A file-size warning must appear after selecting a file larger than 4 GB.

        The upload page checks the selected file's size against
        UPLOAD_SIZE_WARNING_BYTES (4 GB). If exceeded, it renders a
        <div role="note"> with the warning message. This test simulates
        selecting a file of 4 GB + 1 byte without needing a real large file.
        """
        upload_page.simulate_large_file_selection(
            size_bytes=_FILE_SIZE_OVER_LIMIT,
            filename="large_video.mp4",
        )

        assert upload_page.is_file_size_warning_visible(), (
            "Expected a file size warning (role='note') to be visible after selecting "
            f"a file of {_FILE_SIZE_OVER_LIMIT} bytes, but no warning was shown."
        )

    def test_warning_message_contains_expected_text(self, upload_page: UploadPage):
        """The warning message must mention the '4.0 GB' size threshold.

        This confirms the message is informative and matches the UI copy:
        'Warning: file is larger than 4.0 GB. Uploads may take a long time
        on slow connections.'
        """
        warning_text = upload_page.get_file_size_warning_text()

        assert warning_text is not None, (
            "Expected a file size warning message to be present, but got None."
        )
        assert _EXPECTED_WARNING_FRAGMENT in warning_text, (
            f"Expected warning to contain '{_EXPECTED_WARNING_FRAGMENT}', "
            f"but got: {warning_text!r}"
        )

    def test_no_warning_for_file_under_4gb(self, web_config: WebConfig, page: Page):
        """No warning should appear when selecting a file smaller than 4 GB.

        Opens a fresh upload page session to reset state, then simulates
        selecting a file of exactly 1 MB (well under the 4 GB threshold).
        """
        up = UploadPage(page)
        up.navigate(web_config.base_url.rstrip("/") + "/upload/")

        _ONE_MB = 1 * 1024 * 1024
        up.simulate_large_file_selection(
            size_bytes=_ONE_MB,
            filename="small_video.mp4",
        )

        assert not up.is_file_size_warning_visible(timeout=2_000), (
            "Expected no file size warning for a 1 MB file, but a warning was shown."
        )
