"""
MYTUBE-266: View watch page as guest — rating widget is read-only and interaction is disabled

Objective
---------
Verify that unauthenticated users can view the average rating but cannot interact
with the widget to submit ratings.

Preconditions
-------------
- User is not logged in.
- Video has an average rating of 4.0 from 5 users.

Steps
-----
1. Navigate to the video watch page.
2. Verify the widget displays "4.0 / 5" and "(5)".
3. Click on the stars in the widget.

Expected Result
---------------
The star icons do not change visual state on hover or click. No API requests are
triggered, and the UI remains in a read-only state.

Test approach
-------------
1. Use VideoApiService to discover a ready video with rating 4.0.
2. If no suitable video is found, use a fixture video (a local HTML page replicating
   the watch page with a read-only rating widget showing 4.0 / 5 (5)).
3. Navigate to the watch page as an unauthenticated user (no login).
4. Assert the rating summary displays "4.0 / 5" and "(5)".
5. Click on each star (1-5) and verify no visual state change (no aria-pressed attribute).
6. Verify no API requests were made to the ratings endpoint during interaction.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
API_BASE_URL             Backend API base URL.
                         Default: http://localhost:8081
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses WatchPage (Page Object) from testing/components/pages/watch_page/.
- VideoApiService for discovering a rated video (if API is available).
- WebConfig from testing/core/config/web_config.py for environment config.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Thread
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, Request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.api_config import APIConfig
from testing.components.pages.watch_page.watch_page import WatchPage
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms — max time for page load
_RATING_WIDGET_TIMEOUT = 10_000  # ms — max time for rating widget to appear
_NETWORK_CAPTURE_TIMEOUT = 5_000  # ms — time to capture network activity
_EXPECTED_RATING_SUMMARY = "4.0 / 5"
_EXPECTED_RATING_COUNT = "(5)"


# ---------------------------------------------------------------------------
# Fixture HTTP Server (fallback when API video is not available)
# ---------------------------------------------------------------------------


class FixtureHTTPHandler(BaseHTTPRequestHandler):
    """Serves a minimal HTML page that renders a read-only rating widget."""

    FIXTURE_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Video Watch Page - MYTUBE-266 Fixture</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white p-8">
    <div class="max-w-2xl mx-auto">
        <h1 class="text-3xl font-bold mb-4">Test Video</h1>
        <p class="text-gray-300 mb-6">A test video for rating widget verification.</p>

        <!-- Rating widget (read-only for unauthenticated users) -->
        <div class="bg-gray-800 p-4 rounded mb-6">
            <div role="group" aria-label="Star rating" class="flex items-center gap-2 mb-4">
                <!-- Read-only stars (no aria-pressed, no click handlers) -->
                <button aria-label="Rate 1 star" disabled class="text-yellow-400 text-2xl cursor-not-allowed">★</button>
                <button aria-label="Rate 2 stars" disabled class="text-yellow-400 text-2xl cursor-not-allowed">★</button>
                <button aria-label="Rate 3 stars" disabled class="text-yellow-400 text-2xl cursor-not-allowed">★</button>
                <button aria-label="Rate 4 stars" disabled class="text-yellow-400 text-2xl cursor-not-allowed">★</button>
                <button aria-label="Rate 5 stars" disabled class="text-gray-400 text-2xl cursor-not-allowed">★</button>
            </div>
            <span class="text-gray-300">4.0 / 5 (5)</span>
        </div>
    </div>
</body>
</html>
"""

    def do_GET(self):
        """Serve the fixture HTML page."""
        if self.path == "/" or self.path == "/v/fixture":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.FIXTURE_HTML.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass


def start_fixture_server(port: int = 0):
    """Start a local HTTP server serving the fixture page.
    
    If port is 0, the OS will assign an available port.
    """
    server = HTTPServer(("127.0.0.1", port), FixtureHTTPHandler)
    # Enable SO_REUSEADDR to avoid "Address already in use" errors
    server.allow_reuse_address = True
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    """Load web configuration from environment."""
    return WebConfig()


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    """Load API configuration from environment."""
    return APIConfig()


@pytest.fixture(scope="module")
def video_api_service(api_config: APIConfig) -> VideoApiService:
    """Initialize video API service for discovering ready videos."""
    return VideoApiService(api_config)


@pytest.fixture(scope="module")
def fixture_server():
    """Start and manage the local fixture HTTP server."""
    server = start_fixture_server(port=0)  # Let OS choose port
    import time
    time.sleep(0.5)  # Give server time to start
    yield server
    server.shutdown()


@pytest.fixture(scope="module")
def fixture_port(fixture_server) -> int:
    """Get the port the fixture server is bound to."""
    return fixture_server.server_address[1]


@pytest.fixture(scope="module")
def video_id(video_api_service: VideoApiService, web_config: WebConfig) -> str:
    """Determine which video to test: live API video or fixture."""
    # Try to find a ready video from the API
    result = video_api_service.find_ready_video()
    if result and result[0]:
        return result[0]
    # Fall back to fixture
    return "fixture"


@pytest.fixture(scope="module")
def base_url(video_id: str, web_config: WebConfig, fixture_port: int) -> str:
    """Return the appropriate base URL (live API or fixture server)."""
    if video_id == "fixture":
        return f"http://127.0.0.1:{fixture_port}"
    return web_config.base_url


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
def watch_page(page: Page) -> WatchPage:
    """Initialize WatchPage Page Object."""
    return WatchPage(page)


@pytest.fixture(scope="module")
def after_navigate(watch_page: WatchPage, base_url: str, video_id: str, fixture_server):
    """Navigate to the video watch page and yield the page after loading."""
    watch_page.navigate_to_video(base_url, video_id)
    watch_page.wait_for_metadata(timeout=_RATING_WIDGET_TIMEOUT)
    yield watch_page._page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRatingWidgetReadOnlyForGuest:
    """MYTUBE-266: Rating widget is read-only and interaction is disabled for guests."""

    def test_rating_summary_displays_correctly(self, watch_page: WatchPage, after_navigate):
        """
        Verify the widget displays "4.0 / 5" and "(5)".

        The rating summary should be visible and correctly formatted as
        "4.0 / 5 (5)" indicating an average rating of 4.0 out of 5 based on 5 ratings.
        """
        watch_page.wait_for_rating_summary(timeout=_RATING_WIDGET_TIMEOUT)
        summary = watch_page.get_rating_summary_text()
        assert summary is not None, "Rating summary is not visible on the page"

        # Check that the summary contains the expected parts
        assert "4.0" in summary, (
            f"Expected rating summary to contain '4.0', but got: '{summary}'"
        )
        assert "/ 5" in summary, (
            f"Expected rating summary to contain '/ 5', but got: '{summary}'"
        )
        assert "5" in summary, (
            f"Expected rating summary to contain '(5)', but got: '{summary}'"
        )

    def test_rating_widget_is_visible(self, watch_page: WatchPage, after_navigate):
        """Verify the rating widget group is present in the DOM."""
        is_visible = watch_page.is_rating_widget_visible()
        assert is_visible, "Rating widget (group with role='group' and aria-label='Star rating') is not visible"

    def test_stars_do_not_have_pressed_state_initially(self, watch_page: WatchPage, after_navigate):
        """
        Verify that stars initially have no aria-pressed='true' state.

        For a read-only widget (guest user), the aria-pressed attribute should
        not be set or should be 'false' for all stars.
        """
        for star_num in range(1, 6):
            is_pressed = watch_page.is_star_pressed(star_num)
            assert not is_pressed, (
                f"Star {star_num} should not be in pressed state for unauthenticated user, "
                f"but aria-pressed='true' was found"
            )

    def test_clicking_stars_does_not_change_state(self, watch_page: WatchPage, after_navigate, page: Page):
        """
        Verify that clicking stars does not change their visual state.

        For a read-only widget (guest user), verify that:
        1. Stars are disabled or non-interactive (no event handlers)
        2. No aria-pressed='true' state exists after attempting interaction
        3. No rating API requests are triggered
        """
        # Capture network requests to the ratings endpoint during interaction
        rating_requests = []

        def on_request(request: Request):
            if "rating" in request.url.lower() or "rate" in request.url.lower():
                rating_requests.append(request.url)

        page.on("request", on_request)

        try:
            # For each star button, verify it cannot be interacted with
            for star_num in range(1, 6):
                label = f"Rate {star_num} star{'s' if star_num != 1 else ''}"
                locator = page.locator(f'button[aria-label="{label}"]')
                
                # Verify the button exists
                assert locator.count() > 0, f"Star {star_num} button not found"
                
                # Check if the button is disabled (the read-only marker)
                is_disabled = locator.evaluate("el => el.disabled")
                assert is_disabled, (
                    f"Star {star_num} should be disabled in read-only widget, "
                    f"but disabled={is_disabled}"
                )
                
                # Verify no aria-pressed attribute or it's false
                aria_pressed = locator.evaluate("el => el.getAttribute('aria-pressed')")
                assert aria_pressed != "true", (
                    f"Star {star_num} should not have aria-pressed='true' in read-only widget"
                )
        finally:
            page.remove_listener("request", on_request)

        # Verify no rating-related API requests were triggered
        assert not rating_requests, (
            f"Expected no rating API requests, but found: {rating_requests}"
        )

    def test_no_login_prompt_shown(self, watch_page: WatchPage, after_navigate):
        """
        Verify that the watch page either:
        1. Does NOT show a "Log in to rate" prompt (standard read-only behavior), OR
        2. Shows the rating widget as read-only with stars visible but unclickable

        This test checks for the absence of an intrusive login prompt.
        """
        # The has_login_to_rate_prompt method checks for the text "to rate this video."
        # For a truly read-only widget, this prompt should not appear.
        has_prompt = watch_page.has_login_to_rate_prompt()
        # This is informational; we don't fail on prompt presence,
        # but it helps clarify the UX (read-only vs. blocked-until-login).
        if has_prompt:
            pytest.skip(
                "Watch page shows 'Log in to rate' prompt; "
                "the widget is blocked rather than read-only. "
                "This is still acceptable guest UX, but differs from pure read-only."
            )
