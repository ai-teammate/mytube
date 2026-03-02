"""
MYTUBE-139: Complete video upload — user redirected to dashboard with processing status.

Verifies the end-to-end upload flow:
  1. An authenticated user on /upload fills the metadata form and selects a video file.
  2. The upload progresses to 100%.
  3. After completion the application automatically redirects to /dashboard.
  4. The dashboard URL contains the ?uploaded=<videoId> query parameter.
  5. The newly uploaded video is visible on the dashboard with a "Processing" status.

Preconditions
-------------
- A registered Firebase user exists (FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD).
- The web application is deployed and reachable at WEB_BASE_URL.
- The backend API is running and accessible.

Test steps
----------
1. Navigate to /login and sign in with valid credentials.
2. Navigate to /upload.
3. Fill the metadata form (title, description, category) and select a minimal MP4 file.
4. Click "Upload video" and wait for upload to reach 100%.
5. Assert the browser redirects to a URL containing /dashboard.
6. Assert the URL contains the ?uploaded=<videoId> query parameter.
7. Assert the dashboard renders (not a 404 page).
8. Assert a "Processing" status indicator is visible for the uploaded video.

Environment variables
---------------------
FIREBASE_TEST_EMAIL     : Email of the registered Firebase test user (required).
FIREBASE_TEST_PASSWORD  : Password for the registered Firebase test user (required).
WEB_BASE_URL / APP_URL  : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses LoginPage, UploadPage, DashboardPage (Page Object pattern).
- WebConfig from testing/core/config/web_config.py centralises all env var access.
- Playwright sync API with pytest module-scoped fixtures.
- A minimal valid MP4 file is generated at test time; no large file fixtures needed.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import struct
import sys
import tempfile

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.upload_page.upload_page import UploadPage
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_LOGIN_TIMEOUT = 25_000    # ms — post-login Firebase redirect
_UPLOAD_TIMEOUT = 90_000   # ms — GCS upload + redirect to dashboard
_PAGE_LOAD_TIMEOUT = 30_000


def _make_minimal_mp4(path: str) -> None:
    """Write a minimal valid MP4/ftyp file to *path*.

    The file satisfies the browser MIME-type check (video/mp4) and passes the
    backend MIME validation without requiring a real media file.  It is too
    small to play but sufficient for upload acceptance testing.
    """
    # ftyp box: 4B size + 4B type + 4B major brand + 4B minor version + 4B compatible brand
    ftyp = struct.pack(">I", 20) + b"ftyp" + b"isom" + struct.pack(">I", 0) + b"isom"
    # mdat box: minimal media data container (8 bytes header, empty payload)
    mdat = struct.pack(">I", 8) + b"mdat"
    with open(path, "wb") as f:
        f.write(ftyp + mdat)


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
            "FIREBASE_TEST_EMAIL not set — skipping upload E2E test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping upload E2E test. "
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
    """Open a fresh browser context and page, shared across the module."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def test_video_file() -> str:
    """Create a minimal MP4 file for upload testing.

    Returns the path to the temporary file.  The file is cleaned up after the
    test module completes.
    """
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name
    _make_minimal_mp4(tmp_path)
    yield tmp_path
    try:
        os.unlink(tmp_path)
    except OSError:
        pass


@pytest.fixture(scope="module")
def after_upload(
    web_config: WebConfig,
    page: Page,
    test_video_file: str,
) -> Page:
    """
    Perform the full upload flow once and yield the page after the redirect to /dashboard.

    Steps:
      1. Login with test credentials.
      2. Navigate to /upload.
      3. Fill form with minimal valid data.
      4. Submit and wait for redirect to /dashboard.

    All tests in this module share this fixture — the flow is executed exactly once.
    """
    login_page = LoginPage(page)
    upload_page = UploadPage(page)

    # Step 1: Login
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

    # Step 2: Navigate to upload page
    upload_url = f"{web_config.base_url}/upload"
    upload_page.navigate(upload_url)

    # Step 3: Fill the form and select the test video file
    upload_page.fill_form_and_upload(
        file_path=test_video_file,
        title="MYTUBE-139 Automated Test Upload",
        description="Automated test upload for MYTUBE-139 — safe to delete.",
        category_value="5",  # "Other"
        tags="automated-test,mytube-139",
    )

    # Step 4: Wait for upload to complete and redirect to /dashboard
    upload_page.wait_for_upload_complete_and_redirect(
        dashboard_url_fragment="/dashboard",
        timeout=_UPLOAD_TIMEOUT,
    )

    yield page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadRedirectsToDashboard:
    """MYTUBE-139: After a complete upload the user is redirected to the dashboard."""

    def test_redirected_to_dashboard_url(self, after_upload: Page) -> None:
        """The browser URL must contain /dashboard after the upload completes."""
        current_url = after_upload.url
        assert "/dashboard" in current_url, (
            f"Expected redirect to a URL containing '/dashboard' after upload, "
            f"but the current URL is: {current_url!r}"
        )

    def test_dashboard_url_has_uploaded_query_param(self, after_upload: Page) -> None:
        """The redirect URL must include the ?uploaded=<videoId> query parameter."""
        import urllib.parse

        parsed = urllib.parse.urlparse(after_upload.url)
        params = urllib.parse.parse_qs(parsed.query)
        assert "uploaded" in params, (
            f"Expected the dashboard URL to contain '?uploaded=<videoId>', "
            f"but no 'uploaded' param was found. Current URL: {after_upload.url!r}"
        )
        video_id = params["uploaded"][0]
        assert video_id, (
            "Expected a non-empty video ID in the 'uploaded' query param, "
            f"but got an empty value. Current URL: {after_upload.url!r}"
        )

    def test_dashboard_page_renders_not_404(self, after_upload: Page) -> None:
        """The dashboard must render actual content, not a 404 not-found page."""
        dashboard_page = DashboardPage(after_upload)
        dashboard_page.wait_for_load(timeout=10_000)
        assert not dashboard_page.is_404_page(), (
            f"The /dashboard page returned a 404 or 'not found' response. "
            f"Current URL: {after_upload.url!r}. "
            "This indicates the /dashboard route is not implemented."
        )

    def test_uploaded_video_shows_processing_status(self, after_upload: Page) -> None:
        """The newly uploaded video must appear on the dashboard with 'Processing' status."""
        dashboard_page = DashboardPage(after_upload)
        dashboard_page.wait_for_load(timeout=10_000)
        assert dashboard_page.has_processing_status(timeout=8_000), (
            f"Expected to find a 'Processing' status indicator for the uploaded video "
            f"on the dashboard, but none was found. "
            f"Current URL: {after_upload.url!r}. "
            "Check that the dashboard displays videos with their current status."
        )
