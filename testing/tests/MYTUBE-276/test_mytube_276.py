"""
MYTUBE-276: Upload registration fails after 100% upload — redirection suppressed and error message displayed.

Objective
---------
Verify that the application correctly handles server-side registration failures at the
point of upload completion by preventing redirection and informing the user.

Preconditions
-------------
- User is authenticated and on the /upload page.

Steps
-----
1. Complete the metadata form with valid information.
2. Select a valid video file and initiate the upload.
3. Wait for the progress bar to reach 100%.
4. Simulate a 500 Internal Server Error for the subsequent API call that registers the completed upload.
5. Observe the application behavior.

Expected Result
---------------
The application remains on the upload page. Redirection to the dashboard does not occur,
and a clear error message is displayed to the user indicating the failure.

Test Approach
-------------
The test uses Playwright route interception to mock the POST /api/videos endpoint,
which is called after the file upload completes (when registering the video metadata).
We intercept and return a 500 status code to simulate a server-side registration failure.

The test:
1. Logs in with test credentials
2. Navigates to /upload
3. Sets up route interception on POST /api/videos to return 500
4. Fills the metadata form
5. Uploads a small test file
6. Waits for the upload to reach 100%
7. Verifies the error message is shown
8. Verifies the page remains on /upload (no redirect to dashboard)

Environment variables
---------------------
FIREBASE_TEST_EMAIL     : Email of the Firebase test user (required).
FIREBASE_TEST_PASSWORD  : Password of the Firebase test user (required).
WEB_BASE_URL            : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- UploadPage (Page Object) from testing/components/pages/upload_page/.
- LoginPage (Page Object) from testing/components/pages/login_page/.
- WebConfig from testing/core/config/web_config.py.
- Playwright sync API with Playwright route interception for API mocking.
- Route interception used to mock the registration POST endpoint returning 500.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, Route, Request, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.upload_page.upload_page import UploadPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_UPLOAD_PROGRESS_TIMEOUT = 120_000  # ms
_AUTH_RESOLVE_TIMEOUT = 20_000  # ms

# Small test video file size (100 KB) — fast upload in tests
_TEST_VIDEO_SIZE = 100 * 1024  # 100 KB


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _handle_video_registration_500(route: Route, request: Request) -> None:
    """Return 500 error for POST /api/videos (simulate registration failure)."""
    if request.method == "POST" and "/api/videos" in request.url:
        route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps({"error": "Internal Server Error"}),
        )
    else:
        route.continue_()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are absent."""
    if not web_config.test_email or not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_EMAIL and/or FIREBASE_TEST_PASSWORD are not set — "
            "skipping upload error handling test. "
            "These credentials are available in CI as GitHub Actions secrets/variables."
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
def upload_page_ready(
    browser: Browser,
    web_config: WebConfig,
):
    """Log in and navigate to the upload page with error mocking set up.

    The route interceptor mocks:
    - POST /api/videos → 500 Internal Server Error (simulates registration failure)

    Yields a dict with keys:
      page        – the Playwright Page object
      upload_page – the UploadPage page-object wrapping the page
    """
    context = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Register route interceptor BEFORE any navigation so we can mock the registration endpoint
    page.route("**/api/videos", _handle_video_registration_500)

    # Step 1 — Log in
    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    # Wait until the browser leaves the login page (redirect to home)
    page.wait_for_url(
        lambda url: "/login" not in url,
        timeout=_AUTH_RESOLVE_TIMEOUT,
    )

    # Step 2 — Navigate to the upload page
    upload_pg = UploadPage(page)
    upload_pg.navigate(web_config.base_url)

    yield {"page": page, "upload_page": upload_pg}

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadRegistrationError:
    """MYTUBE-276: Upload registration fails at 100% — error shown, no redirect."""

    def test_error_message_shown_on_registration_failure(
        self,
        upload_page_ready: dict,
    ):
        """Test that a registration error (500) prevents redirect and shows an error message.

        Steps:
        1. Complete the metadata form with valid information.
        2. Select a valid video file and initiate the upload.
        3. Wait for the progress bar to reach 100%.
        4. Verify error message is displayed (from the mocked 500 response).
        5. Verify the page is still on /upload (no redirect to dashboard).
        """
        upload_pg: UploadPage = upload_page_ready["upload_page"]
        page: Page = upload_page_ready["page"]

        # Step 1: Complete the metadata form with valid information.
        upload_pg.fill_title("Test Upload with Registration Error")
        upload_pg.fill_description("Testing error handling when registration fails")
        upload_pg.select_category("1")  # Education category
        upload_pg.fill_tags("test,error,handling")

        # Step 2: Select a valid video file and initiate the upload.
        # Create a temporary small video file for the test
        with tempfile.NamedTemporaryFile(
            suffix=".mp4",
            delete=False,
        ) as tmp:
            # Write minimal MP4 file signature to avoid MIME type errors
            tmp.write(b"\x00\x00\x00\x20ftypisom")  # Minimal valid MP4 header
            tmp.write(b"\x00" * (_TEST_VIDEO_SIZE - tmp.tell()))
            tmp_path = tmp.name

        try:
            upload_pg.set_video_file(tmp_path)

            # Step 2.5: Click upload to start the upload
            upload_pg.click_upload()

            # Step 3: Wait for the progress bar to reach 100%
            # The progress bar should appear, indicating the upload has started.
            upload_pg.wait_for_progress_visible(timeout=_UPLOAD_PROGRESS_TIMEOUT)

            # Wait until the progress reaches 100% or the upload completes
            # (the page may remain on /upload due to the mocked 500 error)
            try:
                page.wait_for_function(
                    "() => document.querySelector('[role=progressbar]')?.getAttribute('aria-valuenow') === '100'",
                    timeout=_UPLOAD_PROGRESS_TIMEOUT,
                )
            except Exception:
                # If progress doesn't reach 100, it may already have failed
                pass

            # Give the client a moment to handle the error response
            page.wait_for_timeout(2000)

            # Step 4 & 5: Verify error message is displayed and page didn't redirect
            # The error message should be visible in an alert
            error_message = upload_pg.get_error_message()
            assert (
                error_message is not None
            ), "Expected error message to be displayed on registration failure"

            # Verify the page is still on /upload (no redirect to dashboard)
            current_url = upload_pg.current_url()
            assert (
                "/upload" in current_url
            ), f"Expected page to remain on /upload but got {current_url}"
            assert (
                "/dashboard" not in current_url
            ), f"Expected no redirect to /dashboard but got {current_url}"

        finally:
            # Clean up the temporary file
            Path(tmp_path).unlink(missing_ok=True)

    def test_no_redirect_to_dashboard_on_registration_failure(
        self,
        upload_page_ready: dict,
    ):
        """Test that the browser does not navigate away from /upload when registration fails.

        This is a standalone test to verify that the redirect prevention works correctly
        even if the error message somehow fails to appear.
        """
        upload_pg: UploadPage = upload_page_ready["upload_page"]
        page: Page = upload_page_ready["page"]

        # Fill the form
        upload_pg.fill_title("Test No Redirect on Error")
        upload_pg.fill_description("Verify no redirect happens")
        upload_pg.select_category("2")  # Different category
        upload_pg.fill_tags("test")

        # Create and upload a test file
        with tempfile.NamedTemporaryFile(
            suffix=".mp4",
            delete=False,
        ) as tmp:
            tmp.write(b"\x00\x00\x00\x20ftypisom")  # Minimal valid MP4 header
            tmp.write(b"\x00" * (_TEST_VIDEO_SIZE - tmp.tell()))
            tmp_path = tmp.name

        try:
            upload_pg.set_video_file(tmp_path)
            upload_pg.click_upload()

            # Wait for progress to appear
            upload_pg.wait_for_progress_visible(timeout=_UPLOAD_PROGRESS_TIMEOUT)

            # Wait a bit for the upload to complete and the error to be handled
            page.wait_for_timeout(5000)

            # Verify we're still on /upload
            current_url = upload_pg.current_url()
            assert (
                "/upload" in current_url
            ), f"Expected to remain on /upload but navigated to {current_url}"

        finally:
            Path(tmp_path).unlink(missing_ok=True)
