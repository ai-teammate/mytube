"""
MYTUBE-205: Verify UI rating widget on watch page — average rating and
interaction state visible.

Objective
---------
Verify that the star rating widget correctly renders data and allows
interaction for authenticated users.

Preconditions
-------------
- User is logged in (FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD must be set).
- The rating API response is mocked via Playwright route interception so the
  widget always receives a controlled summary: average=4.2, count=10,
  my_rating=None before interaction and average=4.3, count=11, my_rating=5
  after clicking star 5.

Steps
-----
1. Skip immediately when Firebase credentials are absent.
2. Discover any ready video ID from the public API.
3. Log in with the CI test user via the login page.
4. Register Playwright route interceptors for GET and POST
   **/api/videos/*/rating so the widget receives deterministic mock data.
5. Navigate to /v/<video_id>.
6. Wait for the star rating summary to appear.
7. Assert the widget shows "4.2 / 5 (10 ratings)".
8. Click the 5th star.
9. Assert the widget updates to the new summary from the mock POST response
   and that star 5 is aria-pressed="true".

Environment variables
---------------------
FIREBASE_TEST_EMAIL     E-mail of the Firebase CI test user.
FIREBASE_TEST_PASSWORD  Password for the Firebase CI test user.
APP_URL / WEB_BASE_URL  Deployed frontend base URL.
                        Default: https://ai-teammate.github.io/mytube
API_BASE_URL            Backend API base URL (used for video discovery only).
                        Default: https://mytube-api-80693608388.us-central1.run.app
PLAYWRIGHT_HEADLESS     Headless mode (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Architecture
------------
- WatchPage (Page Object) from testing/components/pages/watch_page/.
- LoginPage (Page Object) from testing/components/pages/login_page/.
- SearchService (API Service Object) from testing/components/services/search_service.py.
- WebConfig from testing/core/config/web_config.py.
- Playwright sync API with Playwright route interception for API mocking.
- No hardcoded URLs or credentials outside of env-var helpers.
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

# Mock rating data injected via Playwright route interception
_MOCK_GET_RESPONSE = {
    "average_rating": 4.2,
    "rating_count": 10,
    "my_rating": None,
}
_MOCK_POST_RESPONSE = {
    "average_rating": 4.3,
    "rating_count": 11,
    "my_rating": 5,
}

# Public API URL for video discovery (may be overridden via API_BASE_URL)
_DEFAULT_API_BASE = "https://mytube-api-80693608388.us-central1.run.app"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_rating_route_handler(get_body: dict, post_body: dict):
    """Return a Playwright route handler that serves mock rating data."""
    def handle(route: Route, request: Request) -> None:
        if request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(get_body),
            )
        elif request.method == "POST":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(post_body),
            )
        else:
            route.continue_()

    return handle


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
            "skipping rating widget UI test. "
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

    Yields a dict with keys:
      page       – the Playwright Page object
      watch_page – the WatchPage page-object wrapping the page
      video_id   – the video ID navigated to
    """
    context = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Step 1 — Log in
    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    # Wait until the browser leaves the login page (redirect to home)
    page.wait_for_url(
        lambda url: "/login" not in url,
        timeout=20_000,
    )

    # Step 2 — Register route interceptors so the star rating widget always
    # receives deterministic mock data regardless of the real API state.
    handler = _make_rating_route_handler(_MOCK_GET_RESPONSE, _MOCK_POST_RESPONSE)
    page.route("**/api/videos/*/rating", handler)

    # Step 3 — Navigate to the watch page and wait for metadata
    watch_pg = WatchPage(page)
    watch_pg.navigate(web_config.base_url, video_id)

    # Wait for the rating summary span to appear (widget has fetched the API)
    watch_pg.wait_for_rating_summary(timeout=_RATING_WIDGET_TIMEOUT)

    yield {"page": page, "watch_page": watch_pg, "video_id": video_id}

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRatingWidgetDisplay:
    """MYTUBE-205 — Rating widget renders the mocked average and count."""

    def test_rating_widget_is_visible(self, watch_page_loaded: dict) -> None:
        """The star rating group (role='group') must be present on the watch page."""
        watch_pg: WatchPage = watch_page_loaded["watch_page"]
        assert watch_pg.is_rating_widget_visible(), (
            "Expected the star rating widget [role='group'][aria-label='Star rating'] "
            "to be present on the watch page, but it was not found."
        )

    def test_rating_summary_shows_average(self, watch_page_loaded: dict) -> None:
        """The summary text must include '4.2 / 5'."""
        watch_pg: WatchPage = watch_page_loaded["watch_page"]
        summary = watch_pg.get_rating_summary_text()
        assert summary is not None, (
            "Expected a rating summary span (containing '/ 5') to be visible, "
            "but none was found."
        )
        assert "4.2 / 5" in summary, (
            f"Expected summary to contain '4.2 / 5', but got: '{summary}'."
        )

    def test_rating_summary_shows_count(self, watch_page_loaded: dict) -> None:
        """The summary text must include '(10 ratings)'."""
        watch_pg: WatchPage = watch_page_loaded["watch_page"]
        summary = watch_pg.get_rating_summary_text()
        assert summary is not None, (
            "Expected a rating summary span to be visible, but none was found."
        )
        assert "10" in summary, (
            f"Expected summary to contain '10' (count), but got: '{summary}'."
        )

    def test_login_to_rate_prompt_not_shown_for_logged_in_user(
        self, watch_page_loaded: dict
    ) -> None:
        """Authenticated users must NOT see the 'Log in to rate' prompt."""
        watch_pg: WatchPage = watch_page_loaded["watch_page"]
        assert not watch_pg.has_login_to_rate_prompt(), (
            "Expected the 'Log in to rate this video.' prompt to be absent "
            "for a logged-in user, but it was visible."
        )


class TestRatingWidgetInteraction:
    """MYTUBE-205 — Clicking the 5th star triggers an update."""

    @pytest.fixture(scope="class")
    def after_star_click(self, watch_page_loaded: dict):
        """Click the 5th star and yield the resulting state."""
        watch_pg: WatchPage = watch_page_loaded["watch_page"]

        watch_pg.click_star(5)

        # Wait for the summary text to update (mock POST returns 4.3 / 5)
        watch_pg.wait_for_rating_summary_text("4.3 / 5", timeout=_RATING_WIDGET_TIMEOUT)
        return watch_pg

    def test_summary_updates_after_star_click(self, after_star_click: WatchPage) -> None:
        """After clicking star 5, the summary must reflect the POST mock response."""
        summary = after_star_click.get_rating_summary_text()
        assert summary is not None, (
            "Expected a rating summary span after clicking a star, but none found."
        )
        assert "4.3 / 5" in summary, (
            f"Expected updated summary to contain '4.3 / 5', but got: '{summary}'."
        )

    def test_count_updates_after_star_click(self, after_star_click: WatchPage) -> None:
        """After clicking star 5, the rating count must reflect the POST mock response."""
        summary = after_star_click.get_rating_summary_text()
        assert summary is not None, (
            "Expected a rating summary span after clicking a star, but none found."
        )
        assert "11" in summary, (
            f"Expected updated count '11' in summary, but got: '{summary}'."
        )

    def test_fifth_star_is_pressed_after_click(self, after_star_click: WatchPage) -> None:
        """After clicking star 5, aria-pressed='true' must be set on the 5th star button."""
        assert after_star_click.is_star_pressed(5), (
            "Expected star 5 to have aria-pressed='true' after the user rated 5 stars, "
            "but it was not pressed."
        )
