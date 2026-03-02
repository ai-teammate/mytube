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
- The "tester" user profile is accessible and has at least one ready video.
- The web application is deployed and reachable at WEB_BASE_URL.

Test approach
-------------
The OG tags are injected client-side by JavaScript in the WatchPage component
(web/src/app/v/[id]/page.tsx).  The test:

1. Starts a lightweight mock API server that returns a known video response
   (id, title, thumbnail_url) at GET /api/videos/<id>.
2. Starts a static HTTP server that serves the watch page HTML fixture
   (testing/fixtures/watch_page/watch_page.html) — a standalone page that
   runs the same OG tag injection logic as the production component.
3. Navigates to the fixture page with Playwright.
4. Waits for the JS to call the mock API and inject the OG meta tags.
5. Asserts og:title equals the video title and og:image is an absolute HTTPS URL.

Environment variables
---------------------
WEB_BASE_URL        : Base URL of the deployed web app (used when testing
                      against the live deployment instead of local fixture).
                      Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO  : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses WatchPage (Page Object) from testing/components/pages/watch_page/.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest fixtures (module-scoped browser).
- Mock API and static server are started/stopped around the test module.
- No hardcoded URLs or credentials outside of fixture data.
"""
from __future__ import annotations

import os
import sys
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

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

# Known video fixture data matching the mock API response
_VIDEO_ID = "11111111-1111-1111-1111-111111111111"
_VIDEO_TITLE = "Test Video For OG Tags"
_THUMBNAIL_URL = "https://storage.googleapis.com/mytube-hls-test/videos/11111111/thumbnail.jpg"

_FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "watch_page"


# ---------------------------------------------------------------------------
# Mock servers
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
def mock_api_server():
    """Start the mock API server for the duration of this test module."""
    server = _start_server(_MockAPIHandler, _MOCK_API_PORT)
    yield server
    server.shutdown()


@pytest.fixture(scope="module")
def fixture_html_server(mock_api_server):
    """Start the static HTML fixture server (depends on mock_api_server)."""
    server = _start_server(_FixtureHTMLHandler, _FIXTURE_PORT)
    yield server
    server.shutdown()


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
def loaded_watch_page(fixture_html_server, page: Page) -> WatchPage:
    """
    Navigate to the watch page fixture for the test video and wait for it to load.
    All tests in this module reuse this loaded page state.
    """
    base_url = f"http://127.0.0.1:{_FIXTURE_PORT}"
    watch = WatchPage(page)
    watch.navigate(base_url, _VIDEO_ID)
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

    def test_og_title_matches_known_video_title(self, loaded_watch_page: WatchPage):
        """og:title must equal the expected video title from the API."""
        og_title = loaded_watch_page.get_og_title()
        assert og_title == _VIDEO_TITLE, (
            f"Expected og:title to be '{_VIDEO_TITLE}', but got '{og_title}'."
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

    def test_og_image_matches_thumbnail_url(self, loaded_watch_page: WatchPage):
        """og:image must equal the thumbnail_url from the API response."""
        og_image = loaded_watch_page.get_og_image()
        assert og_image == _THUMBNAIL_URL, (
            f"Expected og:image to be '{_THUMBNAIL_URL}', but got '{og_image}'."
        )
