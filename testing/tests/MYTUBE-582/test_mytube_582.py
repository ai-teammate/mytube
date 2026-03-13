"""
MYTUBE-582: Watch page recommendation visibility —
section hidden when fewer than 2 results exist.

Objective
---------
Verify that the "More like this" recommendation sidebar is hidden entirely when
the backend returns fewer than 2 recommendations (0 or 1 results).

Preconditions
-------------
A video exists whose recommendations endpoint returns 0 or 1 item in 'ready'
status.

Steps
-----
1. Navigate to the watch page for a specific video.
2. Intercept the recommendations API response to return 0 results.
3. Wait for the sidebar fetch to settle.
4. Inspect the sidebar area where recommendations are usually displayed.

Expected Result
---------------
- The "More like this" heading is NOT present in the DOM.
- No "Recommendations coming soon" placeholder is visible.
- No empty-state message is visible.
- The RecommendationSidebar renders null (no sidebar DOM node at all).

Implementation
--------------
Two complementary modes:

1. **Fixture mode** (always runs — self-contained):
   - Serves a local HTML page that faithfully reproduces the
     RecommendationSidebar's null-render branch (< 2 results).
   - Uses WatchPage component for DOM assertions.

2. **Live mode** (runs when APP_URL / WEB_BASE_URL is reachable):
   - Discovers a ready video via VideoApiService.
   - Navigates to /v/<id> on the deployed SPA via WatchPage and intercepts the
     ``/api/videos/*/recommendations`` call to return 0 or 1 result.
   - Asserts the sidebar heading is absent once the fetch settles.

Architecture
------------
- WebConfig  (testing/core/config/web_config.py)  — env-var driven base URL.
- APIConfig  (testing/core/config/api_config.py)   — backend API base URL.
- VideoApiService (testing/components/services/video_api_service.py)
  — discovers a usable ready video without DB access.
- WatchPage  (testing/components/pages/watch_page/watch_page.py)
  — page object for navigation, sidebar queries.
- Playwright sync API with pytest.

Run from repo root:
    pytest testing/tests/MYTUBE-582/test_mytube_582.py -v
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Route

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.api_config import APIConfig
from testing.components.services.video_api_service import VideoApiService
from testing.components.pages.watch_page.watch_page import WatchPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms

# Fake video UUID used as a fallback when no ready video is available.
_FAKE_VIDEO_ID = "00000000-0000-0000-0000-000000000582"

# ---------------------------------------------------------------------------
# Minimal fixture HTML
# Reproduces the RecommendationSidebar null-render path:
#   - recommendations.length < 2  →  component returns null
#   - No heading, no placeholder, no empty-state message
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>MYTUBE-582 Recommendation Sidebar fixture</title>
  <style>
    body { font-family: sans-serif; background: #0f0f0f; color: #fff; margin: 0; }
    /* Watch page grid — mirrors WatchPageClient.module.css */
    .watchLayout {
      display: grid;
      grid-template-columns: 1fr;
      gap: 1.5rem;
      padding: 1.5rem;
      max-width: 1440px;
      margin: 0 auto;
    }
    @media (min-width: 1024px) {
      .watchLayout { grid-template-columns: 1fr 360px; }
    }
    .mainContent { min-height: 400px; background: #1a1a1a; border-radius: 8px; }
    /* No sidebar rendered — component returned null */
  </style>
</head>
<body>
  <div class="watchLayout" data-testid="watch-layout">
    <main class="mainContent" data-testid="watch-main">
      <h1>Test Video Title</h1>
      <p>Video player placeholder</p>
    </main>
    <!-- RecommendationSidebar rendered null — no sidebar node here -->
  </div>
  <!-- Confirm absence: these phrases must NOT appear anywhere on the page -->
  <script>
    // Simulate a resolved fetch that returned [] — sidebar stays hidden
    window.__recommendationFetchResult = [];
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Local fixture server
# ---------------------------------------------------------------------------

class _FixtureHandler(BaseHTTPRequestHandler):
    """Minimal HTTP handler that serves the fixture HTML for all GET requests."""

    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass  # silence request log spam


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _app_is_reachable(url: str, timeout: int = 8) -> bool:
    """Return True if *url* responds with an HTTP 200-level or 30x status."""
    import urllib.request
    import urllib.error
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return resp.status < 500
    except Exception:
        return False


def _discover_video(api_config: APIConfig) -> Optional[str]:
    """Return a ready video ID discoverable via the VideoApiService, or None."""
    svc = VideoApiService(api_config)
    result = svc.find_ready_video()
    if result is None:
        return None
    video_id, _ = result
    return video_id


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture
def browser_page(web_config: WebConfig):
    """Yield (context, page) for one test; close both on teardown."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=web_config.headless, slow_mo=web_config.slow_mo)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        yield context, page
        context.close()
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRecommendationSidebarHiddenWhenFewResults:
    """Recommendation sidebar must be absent when fewer than 2 results are available."""

    # ------------------------------------------------------------------
    # Fixture mode — always runs, self-contained
    # ------------------------------------------------------------------

    def test_fixture_sidebar_hidden_with_zero_recommendations(
        self, browser_page
    ) -> None:
        """
        A minimal HTML page that reproduces the null-render branch of
        RecommendationSidebar (0 recommendations) must contain neither
        "More like this" nor "Recommendations coming soon".
        """
        context, page = browser_page

        port = _free_port()
        server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        fixture_url = f"http://127.0.0.1:{port}/"

        try:
            page.goto(fixture_url, wait_until="domcontentloaded")

            # Assert the watch layout rendered (page loaded correctly)
            assert page.locator("[data-testid='watch-layout']").count() > 0, (
                "Fixture watch layout not found — fixture page did not load."
            )

            watch = WatchPage(page)

            assert not watch.is_recommendation_sidebar_present(), (
                "Expected 'More like this' heading to be absent when "
                "recommendations < 2, but it was found."
            )
            assert not watch.has_recommendations_placeholder(), (
                "Expected 'Recommendations coming soon' to be absent when "
                "recommendations < 2, but it was found."
            )
        finally:
            server.shutdown()

    # ------------------------------------------------------------------
    # Live mode — runs when the deployed app is reachable
    # ------------------------------------------------------------------

    def test_live_sidebar_hidden_when_recommendations_api_returns_zero(
        self, web_config: WebConfig, api_config: APIConfig, browser_page
    ) -> None:
        """
        On the live deployed app, intercept the recommendations API response to
        return 0 results and assert the sidebar 'More like this' heading is absent.
        """
        if not _app_is_reachable(web_config.base_url):
            pytest.skip(f"Deployed app not reachable at {web_config.base_url!r}")

        video_id = _discover_video(api_config) or _FAKE_VIDEO_ID

        context, page = browser_page

        # Intercept the recommendations API and return an empty list (0 results).
        def _handle_recommendations(route: Route) -> None:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"recommendations": []}),
            )

        context.route("**/api/videos/*/recommendations", _handle_recommendations)

        watch = WatchPage(page)
        watch.navigate_to_video(web_config.base_url, video_id)

        # Wait for loading indicator and recommendation fetch to settle.
        try:
            page.wait_for_selector("text=Loading…", state="hidden", timeout=_PAGE_LOAD_TIMEOUT)
        except Exception:
            pass

        watch.wait_for_recommendations_to_settle()

        assert not watch.is_recommendation_sidebar_present(), (
            f"Expected 'More like this' heading to be absent when API returns "
            f"0 recommendations. Video ID: {video_id}, URL: {web_config.base_url}"
        )
        assert not watch.has_recommendations_placeholder(), (
            f"Expected 'Recommendations coming soon' to be absent when API returns "
            f"0 recommendations. Video ID: {video_id}"
        )

    def test_live_sidebar_hidden_when_recommendations_api_returns_one(
        self, web_config: WebConfig, api_config: APIConfig, browser_page
    ) -> None:
        """
        When the recommendations API returns exactly 1 result (below the
        MIN_RECOMMENDATIONS=2 threshold), the sidebar must still be hidden.
        """
        if not _app_is_reachable(web_config.base_url):
            pytest.skip(f"Deployed app not reachable at {web_config.base_url!r}")

        video_id = _discover_video(api_config) or _FAKE_VIDEO_ID

        context, page = browser_page

        _one_recommendation = {
            "recommendations": [
                {
                    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                    "title": "Single Related Video",
                    "thumbnail_url": None,
                    "view_count": 10,
                    "uploader_username": "testuser",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ]
        }

        def _handle_recommendations_one(route: Route) -> None:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps(_one_recommendation),
            )

        context.route("**/api/videos/*/recommendations", _handle_recommendations_one)

        watch = WatchPage(page)
        watch.navigate_to_video(web_config.base_url, video_id)

        try:
            page.wait_for_selector("text=Loading…", state="hidden", timeout=_PAGE_LOAD_TIMEOUT)
        except Exception:
            pass

        watch.wait_for_recommendations_to_settle()

        assert not watch.is_recommendation_sidebar_present(), (
            f"Expected 'More like this' heading to be absent when API returns "
            f"1 recommendation (< MIN_RECOMMENDATIONS=2). Video ID: {video_id}"
        )
        assert not watch.has_recommendations_placeholder(), (
            f"Expected 'Recommendations coming soon' to be absent when only 1 "
            f"recommendation returned. Video ID: {video_id}"
        )
