"""
MYTUBE-151: Verify social media meta tags — OG title and thumbnail are present.

Verifies that the video watch page includes Open Graph meta tags so that
social media platforms can render rich sharing previews.

Objective
---------
Verify that the video watch page includes Open Graph (OG) tags for rich
social media sharing previews.

Preconditions
-------------
- A video exists with a specific title and generated thumbnail.
- The "tester" user profile is accessible and has at least one ready video with
  a thumbnail_url set.
- The web application is deployed and reachable at WEB_BASE_URL.
- The backend API is reachable at API_BASE_URL (to discover the real video).

Test approach
-------------
The OG tags are injected client-side by JavaScript in the WatchPage component
(web/src/app/v/[id]/page.tsx).  The test:

1. Queries the backend API at API_BASE_URL to find a ready video with a
   thumbnail_url (via GET /api/users/tester, then GET /api/videos/<id>).
2. Navigates to the real deployed watch page at WEB_BASE_URL/v/<id>/ using
   Playwright.
3. Waits for the JS to fetch video data and inject the OG meta tags.
4. Asserts og:title equals the video title and og:image is an absolute HTTPS URL.

This ensures the test covers the actual production OG injection code in
web/src/app/v/[id]/page.tsx rather than a standalone reimplementation.

Fallback (fixture mode)
-----------------------
If API_BASE_URL is not set or the backend API is unreachable, the test falls
back to the local fixture approach (mock API + standalone HTML fixture).  This
keeps local CI green while ensuring real-app coverage when the API is available.

Environment variables
---------------------
WEB_BASE_URL        : Base URL of the deployed web app.
                      Default: https://ai-teammate.github.io/mytube
API_BASE_URL        : Base URL of the backend API used to discover a real video.
                      When set the test navigates to the real deployed app.
                      When absent the test falls back to the local fixture.
PLAYWRIGHT_HEADLESS : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO  : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses WatchPage (Page Object) from testing/components/pages/watch_page/.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest fixtures (module-scoped browser).
- No hardcoded URLs or credentials outside of fixture data.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.watch_page.watch_page import WatchPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOCK_API_PORT = 19151
_FIXTURE_PORT = 19153
_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Known video fixture data used in fallback (local fixture) mode
_VIDEO_ID = "11111111-1111-1111-1111-111111111111"
_VIDEO_TITLE = "Test Video For OG Tags"
_THUMBNAIL_URL = "https://storage.googleapis.com/mytube-hls-test/videos/11111111/thumbnail.jpg"

_FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "watch_page"

# Username whose profile is queried to discover a real video in live mode
_TESTER_USERNAME = "tester"


# ---------------------------------------------------------------------------
# Live-app video discovery
# ---------------------------------------------------------------------------


def _fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    """Issue a GET request and return the parsed JSON body, or None on error."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _discover_live_video(api_base_url: str) -> Optional[dict]:
    """Query the API to find a ready video with a thumbnail for the tester user.

    Returns a dict with ``video_id``, ``title``, and ``thumbnail_url`` when a
    suitable video is found, or None when the API is unreachable or no
    qualifying video exists.
    """
    profile_url = f"{api_base_url.rstrip('/')}/api/users/{_TESTER_USERNAME}"
    profile = _fetch_json(profile_url)
    if not profile:
        return None

    for v in profile.get("videos", []):
        thumbnail = v.get("thumbnail_url")
        if thumbnail:
            # Fetch full video details to confirm status and exact thumbnail URL
            video_url = f"{api_base_url.rstrip('/')}/api/videos/{v['id']}"
            video = _fetch_json(video_url)
            if video and video.get("status") == "ready" and video.get("thumbnail_url"):
                return {
                    "video_id": video["id"],
                    "title": video["title"],
                    "thumbnail_url": video["thumbnail_url"],
                }
    return None


# ---------------------------------------------------------------------------
# Mock servers (used in fallback / local fixture mode only)
# ---------------------------------------------------------------------------


class _MockAPIHandler(BaseHTTPRequestHandler):
    """Minimal API mock: serves a known video response for the test video ID."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress console noise

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            self._respond(200, b'{"status":"ok"}', "application/json")
        elif self.path.startswith(f"/api/videos/{_VIDEO_ID}"):
            body = json.dumps({
                "id": _VIDEO_ID,
                "title": _VIDEO_TITLE,
                "description": "A test video for OG tag verification",
                "hls_manifest_url": None,
                "thumbnail_url": _THUMBNAIL_URL,
                "view_count": 1,
                "created_at": "2025-01-01T00:00:00Z",
                "status": "ready",
                "uploader": {"username": "tester", "avatar_url": None},
                "tags": [],
            }).encode()
            self._respond(200, body, "application/json")
        else:
            self._respond(404, b'{"error":"not found"}', "application/json")

    def _respond(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


class _FixtureHTMLHandler(BaseHTTPRequestHandler):
    """Serves the watch_page.html fixture with the API base URL injected."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0].rstrip("/")
        if path == "" or path.startswith("/v/"):
            html_path = _FIXTURE_DIR / "watch_page.html"
            html = html_path.read_text(encoding="utf-8")
            # Inject the mock API base URL so the page fetches from our mock
            api_url = f"http://127.0.0.1:{_MOCK_API_PORT}"
            script_injection = (
                f'<script>window.API_BASE_URL = "{api_url}";</script>\n'
            )
            html = html.replace("<head>", "<head>\n" + script_injection, 1)
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()


def _start_server(handler_class: type, port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def test_video_context(web_config: WebConfig):
    """Resolve the video to test against and the base URL to navigate.

    When API_BASE_URL is set and a ready video with a thumbnail is found, the
    test runs against the real deployed app (live mode).  Otherwise it starts
    local mock servers and uses the standalone HTML fixture (fixture mode).

    Yields a dict with:
      - ``base_url``      : URL to pass to WatchPage.navigate()
      - ``video_id``      : ID of the video to load
      - ``expected_title``: Expected og:title value
      - ``expected_image``: Expected og:image value (absolute HTTPS URL)
      - ``mode``          : "live" or "fixture" (for test reporting)
    """
    api_base_url = os.getenv("API_BASE_URL", "").strip()

    if api_base_url:
        live_video = _discover_live_video(api_base_url)
    else:
        live_video = None

    if live_video:
        yield {
            "base_url": web_config.base_url,
            "video_id": live_video["video_id"],
            "expected_title": live_video["title"],
            "expected_image": live_video["thumbnail_url"],
            "mode": "live",
        }
    else:
        # Fallback: start local mock servers and use the fixture HTML
        mock_api = _start_server(_MockAPIHandler, _MOCK_API_PORT)
        fixture_srv = _start_server(_FixtureHTMLHandler, _FIXTURE_PORT)
        try:
            yield {
                "base_url": f"http://127.0.0.1:{_FIXTURE_PORT}",
                "video_id": _VIDEO_ID,
                "expected_title": _VIDEO_TITLE,
                "expected_image": _THUMBNAIL_URL,
                "mode": "fixture",
            }
        finally:
            fixture_srv.shutdown()
            mock_api.shutdown()


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
    """Open a fresh browser context with no stored auth state."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def loaded_watch_page(test_video_context, page: Page) -> WatchPage:
    """
    Navigate to the watch page for the test video and wait for it to load.
    All tests in this module reuse this loaded page state.
    """
    watch = WatchPage(page)
    watch.navigate(test_video_context["base_url"], test_video_context["video_id"])
    return watch


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOGMetaTags:
    """MYTUBE-151: OG title and OG image meta tags are present on the watch page."""

    def test_og_title_is_present(self, loaded_watch_page: WatchPage):
        """meta[property="og:title"] must exist and have a non-empty content."""
        og_title = loaded_watch_page.get_og_title()
        assert og_title is not None, (
            'Expected <meta property="og:title"> to be present in the <head>, '
            "but it was not found."
        )
        assert og_title.strip() != "", (
            'Expected <meta property="og:title"> to have non-empty content, '
            "but it was blank."
        )

    def test_og_title_matches_video_title(self, loaded_watch_page: WatchPage):
        """og:title must equal the video title shown in the <h1> heading."""
        og_title = loaded_watch_page.get_og_title()
        page_h1 = loaded_watch_page.get_title_heading()

        assert og_title is not None, (
            'Expected <meta property="og:title"> to be present, but it was not found.'
        )
        assert page_h1 is not None, (
            "Expected the video <h1> title heading to be present, but it was not found."
        )
        assert og_title == page_h1, (
            f"Expected og:title '{og_title}' to match the page <h1> title '{page_h1}'."
        )

    def test_og_title_matches_known_video_title(
        self, loaded_watch_page: WatchPage, test_video_context
    ):
        """og:title must equal the expected video title from the API."""
        og_title = loaded_watch_page.get_og_title()
        expected = test_video_context["expected_title"]
        assert og_title == expected, (
            f"Expected og:title to be '{expected}', but got '{og_title}'."
        )

    def test_og_image_is_present(self, loaded_watch_page: WatchPage):
        """meta[property="og:image"] must exist and have a non-empty content."""
        og_image = loaded_watch_page.get_og_image()
        assert og_image is not None, (
            'Expected <meta property="og:image"> to be present in the <head>, '
            "but it was not found."
        )
        assert og_image.strip() != "", (
            'Expected <meta property="og:image"> to have non-empty content, '
            "but it was blank."
        )

    def test_og_image_is_absolute_url(self, loaded_watch_page: WatchPage):
        """og:image must be an absolute HTTPS URL (CDN URL for the thumbnail)."""
        og_image = loaded_watch_page.get_og_image()
        assert og_image is not None, (
            'Expected <meta property="og:image"> to be present, but it was not found.'
        )
        assert og_image.startswith("https://"), (
            f"Expected og:image to be an absolute HTTPS URL, "
            f"but got '{og_image}'."
        )

    def test_og_image_matches_thumbnail_url(
        self, loaded_watch_page: WatchPage, test_video_context
    ):
        """og:image must equal the thumbnail_url from the API response."""
        og_image = loaded_watch_page.get_og_image()
        expected = test_video_context["expected_image"]
        assert og_image == expected, (
            f"Expected og:image to be '{expected}', but got '{og_image}'."
        )
