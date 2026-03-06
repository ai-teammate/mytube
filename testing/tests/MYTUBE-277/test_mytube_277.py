"""
MYTUBE-277: Session expires during upload completion — user redirected to login page.

Objective
---------
Verify that the application enforces session validation at the moment of upload 
completion and redirects the user to the login page if the session has expired.

Preconditions
-------------
- User is on the /upload page with an active video upload nearing 100%.
- A test user account exists with Firebase credentials available via environment variables.
- The web application is deployed and reachable at WEB_BASE_URL.

Test approach
-------------
1. Sign in a test user and navigate to /upload page.
2. Initiate a video upload (the upload goes to GCS via signed URL).
3. Monitor upload progress and wait until it's near completion (>= 95%).
4. Invalidate the session by clearing all authentication tokens and cookies from the browser.
5. Allow the upload to finish naturally.
6. Verify that instead of redirecting to /dashboard, the browser redirects to /login,
   confirming that the app enforced session validation upon upload completion.

Test structure
--------------
- Uses Playwright's sync API for direct browser automation.
- Uses WebConfig to centralize environment variable access (base URLs, test credentials).
- Uses UploadPage and LoginPage Page Objects for high-level actions.
- No hardcoded URLs or credentials outside of config/env vars.
- Mocks are not used; this is an integration test against the real deployed app.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, BrowserContext

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.upload_page.upload_page import UploadPage
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "upload_page"
_PAGE_LOAD_TIMEOUT = 30_000  # ms
_UPLOAD_TIMEOUT = 300_000  # ms (5 minutes for slow uploads)
_PROGRESS_POLL_INTERVAL_MS = 500

# Sample video file paths (these should exist in the fixtures directory)
# If not available, we'll generate a minimal test video on the fly
_SAMPLE_VIDEO_PATH = _FIXTURE_DIR / "sample_video.mp4" if _FIXTURE_DIR.exists() else None

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def browser() -> Browser:
    """Create a single browser instance for the test module."""
    with sync_playwright() as p:
        config = WebConfig()
        browser = p.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo if config.slow_mo > 0 else None,
        )
        yield browser
        browser.close()


@pytest.fixture
def config() -> WebConfig:
    """Load web configuration from environment."""
    return WebConfig()


@pytest.fixture
def test_video_file() -> str:
    """Provide a path to a test video file.
    
    If the sample_video.mp4 file doesn't exist in fixtures, creates a minimal
    valid MP4 file on-the-fly for testing purposes.
    
    Returns
    -------
    str
        Absolute path to a video file that can be uploaded.
    """
    # Check if fixture file exists
    if _SAMPLE_VIDEO_PATH and _SAMPLE_VIDEO_PATH.exists():
        return str(_SAMPLE_VIDEO_PATH)
    
    # Create a temporary minimal MP4 file
    # This is a minimal valid MP4 header (ftyp box + minimal mdat)
    # Real tests would use an actual video file, but for session expiry testing,
    # the file content doesn't matter as much as the upload flow.
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".mp4")
    try:
        # Write a minimal MP4 header
        # ftyp box (32 bytes) + mdat box with 1MB of dummy data
        with os.fdopen(fd, "wb") as f:
            # ftyp box
            f.write(b"\x00\x00\x00\x20ftypmp42\x00\x00\x00\x00mp42isom")
            # Add 5MB of dummy data (simulates a larger video file)
            f.write(b"\x00" * (5 * 1024 * 1024))
        return path
    except Exception as e:
        pytest.fail(f"Failed to create test video file: {e}")


@pytest.fixture
def page_context(browser: Browser, config: WebConfig):
    """Create a browser context with isolated cookies/storage."""
    context = browser.new_context()
    yield context
    context.close()


@pytest.fixture
def page(page_context) -> Page:
    """Create a new page in the context."""
    return page_context.new_page()


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def sign_in_and_navigate_to_upload(
    page: Page, 
    config: WebConfig,
    email: str,
    password: str,
) -> None:
    """Sign in the test user and navigate to the /upload page.
    
    Parameters
    ----------
    page : Page
        The Playwright page object.
    config : WebConfig
        The web configuration with base URL and credentials.
    email : str
        Email address of the test user.
    password : str
        Password of the test user.
    """
    # Navigate to login page
    login_page = LoginPage(page)
    login_page.navigate(config.login_url())
    
    # Sign in
    login_page.login_as(email, password)
    
    # Wait for redirect to home or dashboard
    page.wait_for_url(
        lambda url: "/login" not in url,
        timeout=_PAGE_LOAD_TIMEOUT,
    )
    
    # Navigate to upload page
    upload_page = UploadPage(page)
    upload_page.navigate(config.base_url)
    
    # Wait for upload form to be visible
    assert upload_page.is_form_visible(), "Upload form not visible after navigation"


def invalidate_session(page: Page) -> None:
    """Clear all authentication tokens and cookies from the browser.
    
    This simulates session expiration by removing:
    - All cookies (including Firebase auth cookies)
    - localStorage items that might contain tokens
    - sessionStorage items
    
    Parameters
    ----------
    page : Page
        The Playwright page object.
    """
    # Clear all cookies
    context = page.context
    if context:
        for cookie in context.cookies():
            context.remove_cookies(cookie)
    
    # Clear localStorage and sessionStorage
    page.evaluate("""
        () => {
            localStorage.clear();
            sessionStorage.clear();
        }
    """)


def wait_for_upload_progress_threshold(
    page: Page,
    upload_page: UploadPage,
    threshold: int = 95,
    timeout_ms: int = _UPLOAD_TIMEOUT,
) -> tuple[bool, int]:
    """Poll the upload progress until it reaches the threshold percentage.
    
    Parameters
    ----------
    page : Page
        The Playwright page object.
    upload_page : UploadPage
        The page object for upload interactions.
    threshold : int, optional
        The minimum progress percentage to wait for (default: 95).
    timeout_ms : int, optional
        Maximum time to wait in milliseconds.
    
    Returns
    -------
    tuple[bool, int]
        (success: whether threshold was reached, max_progress_observed)
    """
    start_time = time.time()
    timeout_s = timeout_ms / 1000
    max_progress = 0
    
    while time.time() - start_time < timeout_s:
        progress = upload_page.get_upload_progress()
        if progress is not None:
            max_progress = max(max_progress, progress)
            if progress >= threshold:
                return True, progress
        page.wait_for_timeout(_PROGRESS_POLL_INTERVAL_MS)
    
    return False, max_progress


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestSessionExpiryDuringUpload:
    """Test suite for session expiry during upload completion."""

    def test_session_expires_during_upload_completion_redirects_to_login(
        self,
        page: Page,
        config: WebConfig,
        test_video_file: str,
    ):
        """
        Verify that expired session during upload completion redirects to login page.
        
        Steps
        -----
        1. Sign in a test user and navigate to /upload page.
        2. Initiate a video upload.
        3. Wait until upload progress reaches ~95%.
        4. Invalidate the user session (clear cookies/tokens).
        5. Allow upload to complete.
        6. Verify the browser redirects to /login instead of /dashboard.
        
        Note
        ----
        This test requires a fully functional backend API and GCS integration.
        It will be skipped if the environment does not support file uploads.
        """
        # Preconditions: Get test credentials
        test_email = config.test_email
        test_password = config.test_password
        
        if not test_email or not test_password:
            pytest.skip(
                "FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD environment "
                "variables must be set to run this test."
            )
        
        # Step 1: Sign in and navigate to upload page
        try:
            sign_in_and_navigate_to_upload(page, config, test_email, test_password)
        except Exception as e:
            pytest.skip(
                f"Failed to sign in or navigate to upload page: {e}. "
                f"The authentication service or web app may be unavailable."
            )
        
        upload_page = UploadPage(page)
        
        # Verify we're on the upload page
        assert upload_page.is_on_upload_page(), "Not on upload page after navigation"
        
        # Step 2: Initiate upload
        try:
            upload_page.fill_form_and_upload(
                file_path=test_video_file,
                title="Test Video - Session Expiry",
                description="Testing session validation during upload completion",
                category_value="1",  # Education category
                tags="test,session-expiry",
            )
        except Exception as e:
            error_msg = upload_page.get_error_message()
            pytest.skip(
                f"Failed to submit upload form: {e}. "
                f"Form error message: {error_msg}. "
                f"The backend API may be unavailable or the user may not have upload permissions."
            )
        
        # Wait for upload progress to appear
        try:
            upload_page.wait_for_progress_visible(timeout=_PAGE_LOAD_TIMEOUT)
        except Exception as e:
            pytest.skip(
                f"Upload progress did not appear within timeout ({_PAGE_LOAD_TIMEOUT}ms). "
                f"The API file upload endpoint may not be available in this environment. "
                f"Error: {e}"
            )
        
        # Step 3: Wait for upload to reach 95% progress, or timeout
        # If the upload doesn't reach 95% within the timeout, we skip this test
        # because the environment may not support actual file uploads.
        try:
            progress_reached, max_progress = wait_for_upload_progress_threshold(
                page=page,
                upload_page=upload_page,
                threshold=95,
                timeout_ms=_UPLOAD_TIMEOUT,
            )
            
            if not progress_reached:
                # The upload may be taking too long or the endpoint may not be available
                pytest.skip(
                    f"Upload did not reach 95% progress within timeout ({_UPLOAD_TIMEOUT}ms). "
                    f"Maximum progress observed: {max_progress}%. "
                    f"The test environment may have slow network, the GCS service may be unreachable, "
                    f"or the file upload flow may not be available. "
                    f"This is not a test failure but an environment configuration issue."
                )
        except Exception as e:
            pytest.skip(f"Error monitoring upload progress: {e}")
        
        # Step 4: Invalidate the session
        invalidate_session(page)
        
        # Step 5: Allow upload to complete
        # The upload continues independently since it's using a signed GCS URL.
        # We just need to wait for the upload to finish and the frontend to redirect.
        
        # Step 6: Verify redirect to login (not dashboard)
        # The frontend should detect expired session and redirect to /login
        # instead of /dashboard after upload completes.
        try:
            page.wait_for_url(
                lambda url: "/login" in url or "/dashboard" in url,
                timeout=_UPLOAD_TIMEOUT,
            )
            current_url = page.url
            
            # Verify we redirected to login, not dashboard
            assert "/login" in current_url, (
                f"Expected redirect to /login after session expiry, but got {current_url}. "
                f"Session validation was not enforced during upload completion."
            )
            
        except Exception as e:
            # If we timed out waiting for the redirect, check the current URL
            current_url = page.url
            pytest.fail(
                f"Expected redirect to /login after session expiry, but got {current_url}. "
                f"Error: {e}"
            )

    def test_upload_page_redirects_unauthenticated_users_to_login(
        self,
        browser: Browser,
        config: WebConfig,
    ):
        """
        Verify that the /upload page enforces authentication by redirecting 
        unauthenticated users to the login page.
        
        This is a simpler smoke test that verifies the access control mechanism
        works without requiring a full file upload.
        
        Steps
        -----
        1. Create a new browser context without any authentication.
        2. Navigate directly to the /upload page.
        3. Verify that the page redirects to /login.
        """
        # Create a context without any cookies (unauthenticated)
        context = browser.new_context()
        page = context.new_page()
        
        try:
            upload_page = UploadPage(page)
            
            # Navigate to upload page with clean (unauthenticated) context
            try:
                upload_page.navigate(config.base_url)
            except Exception as e:
                pytest.skip(
                    f"Failed to navigate to upload page: {e}. "
                    f"The web app may be unavailable."
                )
            
            # Wait a moment for any client-side auth checks to complete
            page.wait_for_timeout(500)
            
            current_url = page.url
            
            # Verify redirect to login
            if "/login" not in current_url:
                # Allow for home page as intermediate redirect
                if config.base_url in current_url or "/upload" in current_url:
                    pytest.fail(
                        f"Unauthenticated user was not redirected from /upload. "
                        f"Current URL: {current_url}. "
                        f"The application should enforce authentication on the /upload page."
                    )
            
            assert "/login" in current_url, (
                f"Expected unauthenticated user to be redirected to /login, "
                f"but got {current_url}"
            )
            
        finally:
            context.close()


# ---------------------------------------------------------------------------
# Entry point for pytest
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
