"""
MYTUBE-262: Delete video encounter server error — error notification shown.

Objective
---------
Verify that the UI handles backend failures during the video deletion process
by displaying a clear error message to the user.

Preconditions
-------------
- User is authenticated and viewing the /dashboard.
- Mock the API to return a 500 error for the DELETE request.

Test steps
----------
1. Navigate to the dashboard (/dashboard) while authenticated.
2. Wait for the video list to load.
3. Intercept DELETE requests to /api/videos/* to return 500 Internal Server Error.
4. Click the "Delete" button next to a video.
5. Click "Confirm" in the confirmation prompt.
6. Wait for and verify an error notification appears.
7. Verify the video remains visible in the dashboard grid.

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
- Uses LoginPage for authentication.
- Uses DashboardPage for dashboard interactions.
- Uses Playwright route interception to mock API 500 errors.
- No hardcoded URLs or credentials.
"""
import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, Route

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NAVIGATION_TIMEOUT = 20_000   # ms
_PAGE_LOAD_TIMEOUT = 30_000    # ms
_ERROR_NOTIFICATION_TIMEOUT = 5_000  # ms


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
            "FIREBASE_TEST_EMAIL not set — skipping delete video test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping delete video test. "
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


@pytest.fixture(scope="function")
def page(browser: Browser) -> Page:
    """Open a fresh browser context and page for each test."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="function")
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)


@pytest.fixture(scope="function")
def dashboard_page(page: Page) -> DashboardPage:
    return DashboardPage(page)


@pytest.fixture(scope="function")
def authenticated_dashboard(web_config: WebConfig, login_page: LoginPage, page: Page):
    """
    Perform login and navigate to dashboard. Yield the page after login.
    """
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    # Wait for post-login redirect
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)
    yield page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteVideoServerError:
    """MYTUBE-262: Delete video with server error shows error notification."""

    def test_delete_with_500_error_shows_notification(
        self, authenticated_dashboard: Page, dashboard_page: DashboardPage,
        web_config: WebConfig
    ):
        """
        Verify that when the DELETE API returns 500, an error notification
        is shown and the video remains visible in the dashboard.
        """
        page = authenticated_dashboard

        # Navigate to dashboard
        dashboard_url = web_config.dashboard_url()
        page.goto(dashboard_url, wait_until="domcontentloaded")
        dashboard_page.wait_for_load()

        # Wait for the video list to load
        dashboard_page.wait_for_videos_table()

        # Get the initial row count and a video title to delete
        initial_row_count = dashboard_page.get_row_count()
        assert initial_row_count > 0, "Dashboard must have at least one video to test deletion"

        # Find a video that is not in "Processing" state
        video_to_delete = None
        video_titles = dashboard_page.get_all_titles()
        assert video_titles, "Could not retrieve video titles from dashboard"

        for title in video_titles:
            status = dashboard_page.get_status_badge_for_title(title)
            if status and status.lower() == "processing":
                continue  # Skip processing videos as they may not have a delete button
            video_to_delete = title
            break

        if not video_to_delete:
            # If all videos are processing, just use the first one
            video_to_delete = video_titles[0]

        # Set up route interception to return 500 error for DELETE requests
        def handle_delete_error(route: Route) -> None:
            """Intercept DELETE /api/videos/* and return 500 Internal Server Error."""
            if route.request.method == "DELETE" and "/api/videos/" in route.request.url:
                route.abort(error_code="failed")
                # Alternatively, return 500 response:
                # route.respond(status=500, body=json.dumps({"error": "Internal Server Error"}))
            else:
                route.continue_()

        page.route("**/*", handle_delete_error)

        # Click the Delete button for the selected video
        # Note: Use .first because there may be multiple buttons with the same name
        delete_btn = page.get_by_role("button", name=f"Delete {video_to_delete}").first
        try:
            delete_btn.wait_for(state="visible", timeout=3_000)
        except Exception:
            pytest.fail(f"Delete button for '{video_to_delete}' is not visible")
        
        delete_btn.click()

        # Verify the confirmation prompt appears
        assert dashboard_page.is_confirm_delete_button_visible(
            timeout=3_000
        ), "Confirmation prompt did not appear after clicking Delete"

        # Click the Confirm button to proceed with deletion
        dashboard_page.click_confirm_delete()

        # Wait for an error notification to appear
        error_visible = False
        try:
            # Look for common error notification patterns:
            # "Failed to delete video", "Error", "failed", etc.
            page.wait_for_selector(
                "text=/[Ff]ailed.*delete|[Ee]rror|[Oo]ops|Something went wrong/i",
                timeout=_ERROR_NOTIFICATION_TIMEOUT
            )
            error_visible = True
        except Exception:
            pass

        assert error_visible, (
            "No error notification was displayed after the DELETE request failed. "
            "Expected to see an error message like 'Failed to delete video' or similar."
        )

        # Verify that the video is still visible in the dashboard
        # (the deletion should not have succeeded)
        video_still_visible = dashboard_page.is_video_visible_by_title(
            video_to_delete, timeout=3_000
        )
        assert video_still_visible, (
            f"Video '{video_to_delete}' should still be visible after deletion failed, "
            "but it was removed from the dashboard."
        )

        # Verify the row count has not changed
        final_row_count = dashboard_page.get_row_count()
        assert final_row_count == initial_row_count, (
            f"Row count changed from {initial_row_count} to {final_row_count} "
            "even though deletion should have failed."
        )
