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
2. Intercept POST /api/videos to return a fake GCS signed URL (no live backend needed).
3. Intercept the fake GCS PUT request to simulate upload completion:
   a. Expire the Firebase in-memory token via React fiber introspection.
   b. Register a route intercept for securetoken.googleapis.com to block token refresh.
   c. Return HTTP 200 to the XHR so the frontend considers the upload finished.
4. The frontend calls getIdToken() after upload; Firebase tries to refresh the expired
   token, the refresh is blocked, getIdToken() returns null, and the app redirects to /login.
5. Verify the browser redirects to /login instead of /dashboard.

Test structure
--------------
- Uses Playwright's sync API for direct browser automation.
- Uses WebConfig to centralize environment variable access (base URLs, test credentials).
- Uses UploadPage and LoginPage Page Objects for high-level actions.
- No hardcoded URLs or credentials outside of config/env vars.
- Route interception makes the test fully self-contained (no live GCS backend required).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.upload_page.upload_page import UploadPage
from testing.components.pages.login_page.login_page import LoginPage

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

# Fake GCS constants used by the route-interception approach for the integration test.
_FAKE_GCS_BUCKET_URL = "https://storage.googleapis.com/fake-test-bucket"
_FAKE_GCS_OBJECT = "test-upload-object"
_FAKE_GCS_URL = f"{_FAKE_GCS_BUCKET_URL}/{_FAKE_GCS_OBJECT}"
_FAKE_VIDEO_ID = "00000000-0000-0000-0000-000000000001"

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
    """Expire the Firebase in-memory token and block forced refresh via network interception.

    Uses two complementary techniques so that the next call to getIdToken() in the
    frontend returns null:

    1. React fiber introspection — walks the React fiber tree to locate the Firebase
       User object and sets stsTokenManager.expirationTime to 10 minutes in the past.
       This forces the Firebase SDK to attempt a token refresh on the next
       getIdToken() call instead of returning the cached token.

       The walk starts from multiple candidate root elements (document, document.body,
       div#__next) to handle both Next.js App Router and Pages Router deployments.
       For each fiber node, the full memoizedState hooks linked list is scanned so
       that the User object is found regardless of its hook position in the component.

    2. securetoken.googleapis.com interception — registers a Playwright route handler
       that responds with HTTP 400 TOKEN_EXPIRED to every token-refresh request.
       This makes the forced refresh fail, causing getIdToken() to throw, which the
       AuthContext getIdToken wrapper catches and converts to null.

    Parameters
    ----------
    page : Page
        The Playwright page object (must be on the upload page when called).
    """
    # Step 1: Expire the cached in-memory Firebase token so the SDK forces a refresh.
    page.evaluate("""
        () => {
            const expiredTime = Date.now() - 10 * 60 * 1000;  // 10 minutes ago
            let patched = 0;

            function checkAndPatch(val) {
                if (!val || typeof val !== 'object') return;
                try {
                    if (val.stsTokenManager &&
                            typeof val.stsTokenManager.expirationTime === 'number') {
                        val.stsTokenManager.expirationTime = expiredTime;
                        patched++;
                    }
                } catch (_) {}
            }

            function walkFiber(fiber) {
                if (!fiber) return;
                try {
                    // Walk the full hooks linked list for this fiber node.
                    let hook = fiber.memoizedState;
                    while (hook) {
                        checkAndPatch(hook.memoizedState);
                        hook = hook.next;
                    }
                } catch (_) {}
                try { walkFiber(fiber.child); } catch (_) {}
                try { walkFiber(fiber.sibling); } catch (_) {}
            }

            // Next.js App Router: hydrateRoot(document, ...) attaches the fiber root
            // to `document` itself.  Pages Router attaches it to div#__next.
            // We try all known containers so the walk works for both.
            const candidates = [
                document,
                document.documentElement,
                document.body,
                document.getElementById('__next'),
            ].filter(Boolean);

            for (const el of candidates) {
                try {
                    const fiberKey = Object.keys(el).find(
                        k => k.startsWith('__reactFiber')
                    );
                    if (fiberKey) {
                        walkFiber(el[fiberKey]);
                    }
                } catch (_) {}
            }

            return patched;
        }
    """)

    # Step 2: Block the forced token refresh so getIdToken() returns null.
    page.route(
        "https://securetoken.googleapis.com/**",
        lambda route: route.fulfill(
            status=400,
            content_type="application/json",
            body='{"error":{"code":400,"message":"TOKEN_EXPIRED","status":"INVALID_ARGUMENT"}}',
        ),
    )


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

        Uses Playwright route interception to make the test fully self-contained
        without requiring a live GCS backend:

        1. POST /api/videos is intercepted to return a fake GCS signed URL.
        2. The fake GCS PUT request is intercepted; before fulfilling it with HTTP 200,
           the handler expires the Firebase in-memory token via React fiber introspection
           and registers a securetoken.googleapis.com block to prevent token refresh.
        3. After the XHR completes, the frontend calls getIdToken() — Firebase detects
           the expired token, attempts a refresh, the refresh is blocked, and
           getIdToken() returns null, triggering router.replace('/login').

        Steps
        -----
        1. Sign in a test user and navigate to /upload page.
        2. Register route interceptions for POST /api/videos and the fake GCS PUT.
        3. Fill and submit the upload form.
        4. Verify the browser redirects to /login instead of /dashboard.
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
        assert upload_page.is_on_upload_page(), "Not on upload page after navigation"

        # Step 2: Register route interceptions so the test does not require a live
        #         backend or GCS service.

        # Intercept POST /api/videos → return a fake video ID and GCS upload URL.
        page.route(
            "**/api/videos",
            lambda route: route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({
                    "video_id": _FAKE_VIDEO_ID,
                    "upload_url": _FAKE_GCS_URL,
                }),
            ) if route.request.method == "POST" else route.continue_(),
        )

        # Intercept the fake GCS PUT → expire the session BEFORE returning 200 so
        # that the subsequent getIdToken() call in the frontend returns null.
        def _handle_fake_gcs_put(route) -> None:
            invalidate_session(page)
            route.fulfill(status=200)

        page.route(f"{_FAKE_GCS_URL}**", _handle_fake_gcs_put)

        # Step 3: Submit the upload form.
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
                f"The web app may be unavailable or the user may not have upload permissions."
            )

        # Step 4: Wait for redirect and verify the browser lands on /login (not /dashboard).
        # The route handlers ensure the session expires during upload completion, so the
        # frontend should redirect to /login rather than /dashboard.
        try:
            page.wait_for_url(
                lambda url: "/login" in url or "/dashboard" in url,
                timeout=_PAGE_LOAD_TIMEOUT,
            )
            current_url = page.url

            assert "/login" in current_url, (
                f"Expected redirect to /login after session expiry, but got {current_url}. "
                f"Session validation was not enforced during upload completion."
            )

        except Exception as e:
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
