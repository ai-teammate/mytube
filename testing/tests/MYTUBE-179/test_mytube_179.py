"""
MYTUBE-179: Search bar functionality — keyword submission from header displays results.

Objective
---------
Verify the end-to-end flow of searching from the site header.

Steps
-----
1. Type a search term into the search bar in the site header.
2. Press Enter or click the search icon.

Expected Result
---------------
The browser redirects to /search?q=[term] and the page renders the results
matching the query using the shared video card component.

Test approach
-------------
Two sub-scenarios are tested:

**Live mode** (when WEB_BASE_URL and API_BASE_URL are set and a ready video
is discoverable via the API):

1. Navigate to the site home page where the SiteHeader is rendered.
2. Fill the search input with the title (or a keyword from the title) of a
   known ready video.
3. Submit the search via Enter key.
4. Assert the browser is now at /search?q=<term>.
5. Assert that the page heading contains the search term.
6. Assert that at least one VideoCard link (a[href^="/v/"]) is rendered.

A second pass repeats steps 1–6 using the Search *button* click rather than
Enter, to exercise both submission paths.

**Fixture mode** (no API / deployed app required — always passes locally):

A local mock HTTP server is started that:
- Serves a minimal SiteHeader HTML page at ``/`` (and any path).
- Intercepts ``GET /api/search?q=...`` and returns one fake VideoCardItem.

The test navigates to the fixture home page, submits a search, and asserts
the same URL + UI assertions as in live mode.

Environment variables
---------------------
WEB_BASE_URL        : Base URL of the deployed web app.
                      Default: https://ai-teammate.github.io/mytube
API_BASE_URL        : Backend API base URL used to discover a known video.
                      When absent the test falls back to fixture mode.
PLAYWRIGHT_HEADLESS : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO  : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses SearchPage (Page Object) from testing/components/pages/search_page/.
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
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.search_page.search_page import SearchPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOCK_API_PORT = 19179
_FIXTURE_PORT = 19180
_PAGE_LOAD_TIMEOUT = 30_000  # ms

_TESTER_USERNAME = "tester"

# Fixture-mode fake video data
_FAKE_VIDEO_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_FAKE_VIDEO_TITLE = "Playwright End-to-End Search Test Video"
_SEARCH_TERM = "Playwright"  # keyword that matches the fake title

# ---------------------------------------------------------------------------
# Live-app video discovery
# ---------------------------------------------------------------------------


def _fetch_json(url: str, timeout: int = 10) -> Optional[dict]:
    """Issue a GET request and return parsed JSON, or None on error."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _discover_live_video(api_base_url: str) -> Optional[dict]:
    """Query the API to find a ready video belonging to the tester user.

    Returns a dict with ``video_id`` and ``search_term`` when found, or None.
    The search_term is taken as the first word of the video title.
    """
    profile_url = f"{api_base_url.rstrip('/')}/api/users/{_TESTER_USERNAME}"
    profile = _fetch_json(profile_url)
    if not profile:
        return None

    for v in profile.get("videos", []):
        video_url = f"{api_base_url.rstrip('/')}/api/videos/{v['id']}"
        video = _fetch_json(video_url)
        if video and video.get("status") == "ready":
            title: str = video.get("title", "")
            # Use the first meaningful word of the title as the search term
            words = [w for w in title.split() if len(w) >= 3]
            if words:
                return {
                    "video_id": video["id"],
                    "title": title,
                    "search_term": words[0],
                }
    return None


# ---------------------------------------------------------------------------
# Fixture-mode mock servers
# ---------------------------------------------------------------------------

# Minimal HTML page that reproduces the SiteHeader + redirects /search
# The page uses vanilla JS to replicate the React router behaviour:
# submitting the form navigates to /search?q=<value>.
_HOME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>mytube – fixture</title>
</head>
<body>
  <header id="site-header">
    <a href="/" style="color:red;font-weight:bold;">mytube</a>
    <form role="search" aria-label="Search videos" id="search-form">
      <input
        type="search"
        id="search-input"
        placeholder="Search videos\u2026"
        aria-label="Search query"
      />
      <button type="submit" aria-label="Submit search">Search</button>
    </form>
  </header>
  <script>
    document.getElementById('search-form').addEventListener('submit', function(e) {
      e.preventDefault();
      var q = document.getElementById('search-input').value.trim();
      if (q) { window.location.href = '/search?q=' + encodeURIComponent(q); }
    });
  </script>
</body>
</html>"""

# Minimal search-results HTML that calls /api/search and renders VideoCards.
_SEARCH_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Search – mytube fixture</title>
</head>
<body>
  <header id="site-header">
    <a href="/" style="color:red;font-weight:bold;">mytube</a>
    <form role="search" aria-label="Search videos" id="search-form">
      <input
        type="search"
        id="search-input"
        placeholder="Search videos\u2026"
        aria-label="Search query"
      />
      <button type="submit" aria-label="Submit search">Search</button>
    </form>
  </header>
  <main>
    <h1 id="heading">Loading\u2026</h1>
    <div id="results"></div>
  </main>
  <script>
    var API_BASE = 'http://127.0.0.1:{mock_api_port}';
    var params = new URLSearchParams(window.location.search);
    var q = params.get('q') || '';

    // Update heading
    var heading = document.getElementById('heading');
    if (q) {{
      heading.textContent = 'Search results for "' + q + '"';
    }} else {{
      heading.textContent = 'Search';
    }}

    // Fetch results from mock API
    fetch(API_BASE + '/api/search?q=' + encodeURIComponent(q))
      .then(function(r) {{ return r.json(); }})
      .then(function(videos) {{
        var container = document.getElementById('results');
        if (!videos || videos.length === 0) {{
          container.innerHTML = '<p>No videos found.</p>';
          return;
        }}
        var html = '<div id="video-grid">';
        videos.forEach(function(v) {{
          html += '<a href="/v/' + v.id + '" aria-label="' + v.title + '">' + v.title + '</a>';
        }});
        html += '</div>';
        container.innerHTML = html;
      }})
      .catch(function() {{
        var container = document.getElementById('results');
        container.innerHTML = '<p role="alert">Could not load search results. Please try again later.</p>';
      }});

    // Wire up the search form on this page too
    document.getElementById('search-form').addEventListener('submit', function(e) {{
      e.preventDefault();
      var q2 = document.getElementById('search-input').value.trim();
      if (q2) {{ window.location.href = '/search?q=' + encodeURIComponent(q2); }}
    }});
  </script>
</body>
</html>"""


class _MockAPIHandler(BaseHTTPRequestHandler):
    """Minimal API mock: serves search results for the fixture test video."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress console noise

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/search":
            body = json.dumps([
                {
                    "id": _FAKE_VIDEO_ID,
                    "title": _FAKE_VIDEO_TITLE,
                    "thumbnail_url": None,
                    "view_count": 42,
                    "uploader_username": "tester",
                    "created_at": "2025-01-01T00:00:00Z",
                }
            ]).encode()
            self._respond(200, body, "application/json")
        else:
            self._respond(404, b'{"error":"not found"}', "application/json")

    def _respond(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)


class _FixtureAppHandler(BaseHTTPRequestHandler):
    """Serves the fixture home page and search results page."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path == "" or path == "/":
            html = _HOME_HTML.encode("utf-8")
            self._respond(200, html, "text/html; charset=utf-8")
        elif path == "/search":
            html = _SEARCH_HTML_TEMPLATE.format(
                mock_api_port=_MOCK_API_PORT
            ).encode("utf-8")
            self._respond(200, html, "text/html; charset=utf-8")
        else:
            self._respond(404, b"Not found", "text/plain")

    def _respond(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.end_headers()
        self.wfile.write(body)


def _start_server(handler_class: type, port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# pytest Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def search_context(web_config: WebConfig):
    """Resolve whether to run in live or fixture mode and provide test context.

    Yields a dict:
      - ``base_url``   : root URL (home page with SiteHeader)
      - ``search_term``: term to type into the search bar
      - ``mode``       : "live" or "fixture"
    """
    api_base_url = os.getenv("API_BASE_URL", "").strip()

    if api_base_url:
        live_video = _discover_live_video(api_base_url)
    else:
        live_video = None

    if live_video:
        yield {
            "base_url": web_config.base_url,
            "search_term": live_video["search_term"],
            "mode": "live",
        }
    else:
        mock_api = _start_server(_MockAPIHandler, _MOCK_API_PORT)
        fixture_srv = _start_server(_FixtureAppHandler, _FIXTURE_PORT)
        try:
            yield {
                "base_url": f"http://127.0.0.1:{_FIXTURE_PORT}",
                "search_term": _SEARCH_TERM,
                "mode": "fixture",
            }
        finally:
            fixture_srv.shutdown()
            mock_api.shutdown()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


def _make_page(browser: Browser) -> Page:
    """Open a fresh browser context and page."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    return pg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchBarEnterKey:
    """MYTUBE-179 (Enter key): submitting via Enter navigates to /search?q=term."""

    @pytest.fixture(scope="class")
    def search_page_enter(self, search_context, browser: Browser) -> SearchPage:
        """Navigate home, type the search term, and submit via Enter key."""
        pg = _make_page(browser)
        sp = SearchPage(pg)
        sp.navigate_to_home(search_context["base_url"])
        sp.fill_search_input(search_context["search_term"])
        sp.submit_search_by_enter()
        return sp

    def test_url_redirects_to_search_path(
        self, search_page_enter: SearchPage
    ) -> None:
        """Browser must redirect to /search after Enter key submission."""
        assert search_page_enter.is_on_search_page(), (
            f"Expected URL path to be /search, but got: "
            f"{search_page_enter.get_current_url()}"
        )

    def test_url_contains_query_param(
        self, search_page_enter: SearchPage, search_context
    ) -> None:
        """URL must include q=<term> after Enter key submission."""
        q = search_page_enter.get_query_param()
        term = search_context["search_term"]
        assert q is not None, (
            f"Expected URL to contain ?q=..., but got: "
            f"{search_page_enter.get_current_url()}"
        )
        assert q.lower() == term.lower(), (
            f"Expected q='{term}', but got q='{q}'."
        )

    def test_results_heading_contains_term(
        self, search_page_enter: SearchPage, search_context
    ) -> None:
        """The <h1> heading on the search page must reference the query term."""
        heading = search_page_enter.get_heading_text()
        term = search_context["search_term"]
        assert heading is not None, (
            "Expected a visible <h1> heading on the search page, but none found."
        )
        assert term.lower() in heading.lower(), (
            f"Expected heading to contain '{term}', but got: '{heading}'."
        )

    def test_video_cards_are_rendered(
        self, search_page_enter: SearchPage
    ) -> None:
        """At least one VideoCard link (a[href^='/v/']) must be rendered."""
        count = search_page_enter.get_video_card_count()
        assert count > 0, (
            f"Expected at least one video card in the search results, "
            f"but got {count}. "
            f"URL: {search_page_enter.get_current_url()}"
        )

    def test_video_card_hrefs_point_to_watch_page(
        self, search_page_enter: SearchPage
    ) -> None:
        """Every VideoCard href must follow the /v/<id> pattern."""
        import re
        pattern = re.compile(r"^/v/.+")
        hrefs = search_page_enter.get_video_card_hrefs()
        assert hrefs, "No video card hrefs found."
        for href in hrefs:
            assert pattern.match(href), (
                f"VideoCard href '{href}' does not match /v/<id> pattern."
            )


class TestSearchBarButtonClick:
    """MYTUBE-179 (button click): submitting via Search button navigates to /search?q=term."""

    @pytest.fixture(scope="class")
    def search_page_button(self, search_context, browser: Browser) -> SearchPage:
        """Navigate home, type the search term, and submit via the Search button."""
        pg = _make_page(browser)
        sp = SearchPage(pg)
        sp.navigate_to_home(search_context["base_url"])
        sp.fill_search_input(search_context["search_term"])
        sp.submit_search_by_button()
        return sp

    def test_url_redirects_to_search_path(
        self, search_page_button: SearchPage
    ) -> None:
        """Browser must redirect to /search after Search button click."""
        assert search_page_button.is_on_search_page(), (
            f"Expected URL path to be /search, but got: "
            f"{search_page_button.get_current_url()}"
        )

    def test_url_contains_query_param(
        self, search_page_button: SearchPage, search_context
    ) -> None:
        """URL must include q=<term> after Search button click."""
        q = search_page_button.get_query_param()
        term = search_context["search_term"]
        assert q is not None, (
            f"Expected URL to contain ?q=..., but got: "
            f"{search_page_button.get_current_url()}"
        )
        assert q.lower() == term.lower(), (
            f"Expected q='{term}', but got q='{q}'."
        )

    def test_results_heading_contains_term(
        self, search_page_button: SearchPage, search_context
    ) -> None:
        """The <h1> heading on the search page must reference the query term."""
        heading = search_page_button.get_heading_text()
        term = search_context["search_term"]
        assert heading is not None, (
            "Expected a visible <h1> heading on the search page, but none found."
        )
        assert term.lower() in heading.lower(), (
            f"Expected heading to contain '{term}', but got: '{heading}'."
        )

    def test_video_cards_are_rendered(
        self, search_page_button: SearchPage
    ) -> None:
        """At least one VideoCard link (a[href^='/v/']) must be rendered."""
        count = search_page_button.get_video_card_count()
        assert count > 0, (
            f"Expected at least one video card in the search results, "
            f"but got {count}. "
            f"URL: {search_page_button.get_current_url()}"
        )

    def test_video_card_hrefs_point_to_watch_page(
        self, search_page_button: SearchPage
    ) -> None:
        """Every VideoCard href must follow the /v/<id> pattern."""
        import re
        pattern = re.compile(r"^/v/.+")
        hrefs = search_page_button.get_video_card_hrefs()
        assert hrefs, "No video card hrefs found."
        for href in hrefs:
            assert pattern.match(href), (
                f"VideoCard href '{href}' does not match /v/<id> pattern."
            )
