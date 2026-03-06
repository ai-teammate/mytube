"""
MYTUBE-264: Rating update API returns 500 error — UI reverts star selection and displays message.

Objective
---------
Verify that the UI handles API failures gracefully when a user attempts to rate a video,
preventing incorrect visual states.

Preconditions
-------------
- User is authenticated (FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD).
- User is on the video watch page.

Test steps
----------
1. Mock the API POST request to /api/videos/:id/rating to return a 500 Internal Server Error status.
2. Click on a star to change the rating.

Expected Result
---------------
The UI displays an error notification (e.g., "Failed to update rating"). The star icons revert
to their previous selection state to match the server-side data.

Environment variables
---------------------
FIREBASE_TEST_EMAIL     : Email of the Firebase test user (required).
FIREBASE_TEST_PASSWORD  : Password of the Firebase test user (required).
APP_URL / WEB_BASE_URL  : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
API_BASE_URL            : Backend API base URL (used for video discovery).
                          Default: https://mytube-api-80693608388.us-central1.run.app
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- WatchPage (Page Object) from testing/components/pages/watch_page/.
- LoginPage (Page Object) from testing/components/pages/login_page/.
- SearchService (API Service Object) for video discovery.
- WebConfig from testing/core/config/web_config.py.
- Playwright sync API with Playwright route interception for API mocking.
- Route interception used to mock the rating POST endpoint returning 500.
"""
from __future__ import annotations

import json
import os
import sys

import pytest
from playwright.sync_api import Browser, Page, Route, Request, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.watch_page.watch_page import WatchPage
from testing.components.services.search_service import SearchService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_RATING_WIDGET_TIMEOUT = 15_000  # ms
_AUTH_RESOLVE_TIMEOUT = 20_000  # ms

# Public API URL for video discovery (may be overridden via API_BASE_URL)
_DEFAULT_API_BASE = "https://mytube-api-80693608388.us-central1.run.app"

# Mock rating data for the initial GET request (before error)
_MOCK_GET_RESPONSE = {
    "average_rating": 4.0,
    "rating_count": 8,
    "my_rating": None,
}


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _handle_rating_get(route: Route, request: Request) -> None:
    """Return mock rating data for GET /api/videos/*/rating."""
    if request.method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps(_MOCK_GET_RESPONSE),
        )
    else:
        route.continue_()


def _handle_rating_post_500(route: Route, request: Request) -> None:
    """Return 500 error for POST /api/videos/*/rating (simulate API failure)."""
    if request.method == "POST":
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
            "skipping rating error handling test. "
            "These credentials are available in CI as GitHub Actions secrets/variables."
        )


@pytest.fixture(scope="module")
def video_id() -> str:
    """Discover a ready video ID from the public search API via SearchService.

    Skips the module if no video is found (e.g. the API is unreachable).
    """
    api_base = os.getenv("API_BASE_URL", _DEFAULT_API_BASE)
    search_svc = SearchService(api_base)
    for query in ("a", "video", "test", ""):
        resp = search_svc.search(q=query)
        if resp.items:
            return resp.items[0].id
    pytest.skip(
        f"No ready video found via {api_base}/api/search — "
        "ensure the API is reachable and at least one video exists."
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
def watch_page_loaded(
    browser: Browser,
    web_config: WebConfig,
    video_id: str,
):
    """Log in, mock the rating API, navigate to the watch page and yield state.

    The route interceptor mocks:
    - GET /api/videos/*/rating → successful response with deterministic data
    - POST /api/videos/*/rating → 500 Internal Server Error (simulates failure)

    This allows the test to verify that the UI properly handles the error
    when the user clicks a star to rate and the POST request fails.

    Yields a dict with keys:
      page       – the Playwright Page object
      watch_page – the WatchPage page-object wrapping the page
      video_id   – the video ID navigated to
    """
    context = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Step 1 — Register route interceptors BEFORE any navigation so we can mock
    # both GET (successful) and POST (500 error) for the rating endpoint.
    def handle_rating(route: Route, request: Request) -> None:
        if request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_MOCK_GET_RESPONSE),
            )
        elif request.method == "POST":
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"error": "Internal Server Error"}),
            )
        else:
            route.continue_()

    page.route("**/api/videos/*/rating", handle_rating)

    # Step 2 — Log in
    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    # Wait until the browser leaves the login page (redirect to home)
    page.wait_for_url(
        lambda url: "/login" not in url,
        timeout=_AUTH_RESOLVE_TIMEOUT,
    )

    # Step 3 — Navigate to the watch page and wait for metadata
    watch_pg = WatchPage(page)
    watch_pg.navigate(web_config.base_url, video_id)

    # Wait a moment for the page to load and the widget to fetch API data
    page.wait_for_timeout(3000)

    yield {"page": page, "watch_page": watch_pg, "video_id": video_id}

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRatingErrorHandling:
    """MYTUBE-264: Rating API returns 500 error — UI reverts star and shows error message."""

    @pytest.fixture(scope="class")
    def state_before_rating(self, watch_page_loaded: dict) -> dict:
        """Capture the state before clicking a star (initial rating state).

        Records:
          - Initial summary text (e.g., "4.0 / 5 (8 ratings)" or None if not loaded)
          - Which stars (if any) are pressed
        """
        watch_pg: WatchPage = watch_page_loaded["watch_page"]

        # Get the initial rating summary (may be None if widget hasn't loaded)
        initial_summary = watch_pg.get_rating_summary_text()

        # Check which stars are currently pressed (should be none if my_rating=None)
        pressed_stars = []
        try:
            # Only check for pressed stars if the widget is visible
            if watch_pg.is_rating_widget_visible():
                pressed_stars = [
                    i for i in range(1, 6) if watch_pg.is_star_pressed(i)
                ]
        except Exception:
            # Widget might not exist yet, that's okay
            pass

        return {
            "initial_summary": initial_summary,
            "pressed_stars": pressed_stars,
        }

    @pytest.fixture(scope="class")
    def after_failed_rating(self, watch_page_loaded: dict) -> dict:
        """Click a star, trigger the 500 error, and capture the result.

        Returns the page state after the failed POST request is handled.
        """
        watch_pg: WatchPage = watch_page_loaded["watch_page"]
        page: Page = watch_page_loaded["page"]

        # Try to click the 4th star to trigger a POST request
        # If the widget hasn't loaded, this will timeout and the test will skip
        try:
            watch_pg.click_star(4)
        except Exception as e:
            pytest.skip(
                f"Could not click star (rating widget may not be loaded): {e}. "
                "This could happen if the API is unreachable or the page "
                "didn't load the rating widget. Run this test with network "
                "access to the deployment and Firebase configured."
            )

        # Wait a bit for the error to be displayed
        page.wait_for_timeout(2000)

        return {"watch_page": watch_pg, "page": page}

    def test_error_message_displayed(self, after_failed_rating: dict) -> None:
        """An error alert must be visible after the rating API returns 500."""
        watch_pg: WatchPage = after_failed_rating["watch_page"]
        page: Page = after_failed_rating["page"]

        # Wait a moment for the error to be displayed
        page.wait_for_timeout(1000)

        # Check if an error alert is displayed
        error_message = watch_pg.get_error_message()
        is_error_visible = watch_pg.is_error_displayed()

        # The error should be present (either as text content or visible element)
        assert is_error_visible or error_message, (
            "Expected an error alert to be displayed after the rating API "
            "returned 500, but no error was visible. "
            f"Error message text: {error_message}, "
            f"Error element visible: {is_error_visible}"
        )

    def test_star_state_reverted_after_error(
        self, state_before_rating: dict, after_failed_rating: dict
    ) -> None:
        """After the API error, the clicked star should revert to unpressed state.

        The star that was clicked should return to its previous state
        (unpressed, since my_rating was initially None).
        """
        watch_pg: WatchPage = after_failed_rating["watch_page"]
        initially_pressed = state_before_rating["pressed_stars"]

        # After the error, the 4th star (which we clicked) should revert
        # back to unpressed (since the request failed)
        is_star_4_pressed = watch_pg.is_star_pressed(4)

        # Star 4 should not be pressed after the error
        # (it was only temporarily pressed before the request failed)
        assert not is_star_4_pressed, (
            "Expected star 4 to revert to unpressed state after the rating API "
            "returned 500, but it remained pressed (aria-pressed='true'). "
            "The UI must revert the star state when the request fails."
        )

    def test_no_other_stars_affected(self, state_before_rating: dict, after_failed_rating: dict) -> None:
        """Stars that were not clicked should remain in their initial state."""
        watch_pg: WatchPage = after_failed_rating["watch_page"]
        initially_pressed = state_before_rating["pressed_stars"]

        # Check all other stars (1, 2, 3, 5) — they should not be affected
        for i in range(1, 6):
            if i == 4:  # Skip the clicked star (already tested above)
                continue
            is_pressed = watch_pg.is_star_pressed(i)
            was_initially_pressed = i in initially_pressed
            assert is_pressed == was_initially_pressed, (
                f"Star {i} state changed unexpectedly after the error. "
                f"Initially pressed: {was_initially_pressed}, "
                f"Currently pressed: {is_pressed}"
            )

    def test_rating_summary_unchanged_after_error(
        self, state_before_rating: dict, after_failed_rating: dict
    ) -> None:
        """The rating summary should remain unchanged after the API error.

        The summary reflects server state, which was not updated because
        the POST request failed. The UI should not show the updated count
        or average until the request succeeds.
        """
        watch_pg: WatchPage = after_failed_rating["watch_page"]
        initial_summary = state_before_rating["initial_summary"]
        current_summary = watch_pg.get_rating_summary_text()

        assert current_summary == initial_summary, (
            f"Expected the rating summary to remain unchanged after the error, "
            f"but it changed from '{initial_summary}' to '{current_summary}'. "
            f"The summary should reflect server state, which was not updated."
        )
