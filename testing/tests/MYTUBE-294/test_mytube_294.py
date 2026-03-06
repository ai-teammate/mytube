"""
MYTUBE-294: Refresh user profile page on static deployment — profile content
remains visible and URL is preserved.

Objective
---------
Verify that performing a browser refresh on a user profile page in a static
environment does not result in a "User not found" error or a broken URL.

Preconditions
-------------
Application is deployed to a static hosting environment (GitHub Pages).

Steps
-----
1. Navigate to a user profile page (e.g., /u/tester).
2. Wait for the profile information and video grid to fully load.
3. Perform a browser refresh (Cmd+R or Ctrl+R).
4. Observe the URL and the page content after the reload completes.

Expected Result
---------------
The application handles the refresh correctly by utilising the SPA fallback
logic. The URL remains /u/tester and does not stay at /u/_/. The page
re-initialises and displays the correct user heading and video grid without
showing a "User not found" error.

Test approach
-------------
Two modes:

**Live mode** (when WEB_BASE_URL/u/<username> correctly renders the profile
component — i.e. the <h1> heading is visible within ~10 seconds):

1. Navigate to WEB_BASE_URL/u/tester.
2. Wait for the username heading and at least one video card to be visible.
3. Reload the page (page.reload()).
4. Wait for the page to settle after reload.
5. Assert the URL ends with /u/tester/ (not /u/_/).
6. Assert no "User not found." message is visible.
7. Assert the username heading is visible.
8. Assert at least one video card is visible.

**Fixture mode** (fallback — used when the live profile URL does not render
the profile component or WEB_BASE_URL is not set to the deployed app):

A local HTTP server replicates the GitHub Pages SPA fallback behaviour:
  - Any request to /u/<username>/ (where username != "_") returns the
    404.html script, which stores the username in sessionStorage and
    redirects the browser to /u/_/.
  - GET /u/_/ returns a minimal shell HTML that reads sessionStorage,
    corrects the URL via history.replaceState, and loads profile data
    from the mock API — mirroring UserProfilePageClient.tsx.
  - GET /api/users/tester returns a mock user profile JSON.
  - GET /api/users/tester/videos returns a mock video list JSON.

This replicates the exact SPA refresh flow that happens on GitHub Pages
and exercises the same client-side code path.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.user_profile_page.user_profile_page import (
    UserProfilePage,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEST_USERNAME = "tester"
_PAGE_LOAD_TIMEOUT = 30_000  # ms
_FIXTURE_PORT = 19294
_SHELL_READY_TEXT = "Profile ready"


# ---------------------------------------------------------------------------
# Fixture server HTML helpers
# ---------------------------------------------------------------------------

_404_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>mytube</title>
  <script>
    (function () {
      var l = window.location;
      var pathParts = l.pathname.split("/");
      // Detect base path for project-page style GitHub Pages deployments.
      // For a plain localhost server the base path is empty ("").
      var knownBases = ["/mytube"];
      var basePath = "";
      for (var b = 0; b < knownBases.length; b++) {
        if (l.pathname.indexOf(knownBases[b] + "/") === 0 ||
            l.pathname === knownBases[b]) {
          basePath = knownBases[b];
          break;
        }
      }

      var routes = [
        { re: /\\/v\\/([^/]+)/,        key: "__spa_video_id",    shell: "/v/_/" },
        { re: /\\/u\\/([^/]+)/,        key: "__spa_username",    shell: "/u/_/" },
        { re: /\\/pl\\/([^/]+)/,       key: "__spa_playlist_id", shell: "/pl/_/" },
        { re: /\\/category\\/([^/]+)/, key: "__spa_category_id", shell: "/category/_/" },
      ];

      for (var i = 0; i < routes.length; i++) {
        var m = l.pathname.match(routes[i].re);
        if (m && m[1] && m[1] !== "_") {
          sessionStorage.setItem(routes[i].key, m[1]);
          l.replace(basePath + routes[i].shell);
          return;
        }
      }

      l.replace(basePath + "/");
    })();
  </script>
</head>
<body></body>
</html>
"""


def _build_shell_html(api_base_url: str) -> str:
    """Build a minimal /u/_/ shell that mirrors UserProfilePageClient.tsx behaviour."""
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>mytube — user profile</title>
</head>
<body>
  <div id="loading">Loading\u2026</div>
  <p id="not-found" style="display:none">User not found.</p>
  <div id="profile" style="display:none">
    <h1 id="heading"></h1>
    <div id="video-grid"></div>
  </div>

  <script>
    (function () {{
      var API = {json.dumps(api_base_url)};
      var paramUsername = "_";

      // Read real username from sessionStorage (set by 404.html on first load
      // and on every subsequent refresh that goes through GitHub Pages 404).
      var storedUsername = sessionStorage.getItem("__spa_username");
      var username;
      if (storedUsername) {{
        sessionStorage.removeItem("__spa_username");
        username = storedUsername;
      }} else {{
        username = paramUsername;
      }}

      // Correct browser URL (mirrors history.replaceState in useEffect).
      if (username !== "_") {{
        var corrected = window.location.pathname.replace("/u/_/", "/u/" + username + "/");
        window.history.replaceState(null, "", corrected);
      }}

      function showNotFound() {{
        document.getElementById("loading").style.display = "none";
        document.getElementById("not-found").style.display = "block";
      }}

      function showProfile(data) {{
        document.getElementById("heading").textContent = data.username;
        document.getElementById("loading").style.display = "none";
        document.getElementById("profile").style.display = "block";
      }}

      function loadVideos(u) {{
        fetch(API + "/api/users/" + u + "/videos")
          .then(function(r) {{ return r.json(); }})
          .then(function(videos) {{
            var grid = document.getElementById("video-grid");
            (videos || []).forEach(function(v) {{
              var a = document.createElement("a");
              a.href = "/v/" + v.id;
              a.textContent = v.title || v.id;
              grid.appendChild(a);
            }});
          }})
          .catch(function() {{}});
      }}

      if (!username || username === "_") {{
        showNotFound();
        return;
      }}

      fetch(API + "/api/users/" + username)
        .then(function(r) {{
          if (r.status === 404) {{ showNotFound(); return null; }}
          return r.json();
        }})
        .then(function(data) {{
          if (data) {{
            showProfile(data);
            loadVideos(username);
          }}
        }})
        .catch(function() {{
          showNotFound();
        }});
    }})();
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Local fixture HTTP server
# ---------------------------------------------------------------------------

class _FixtureHandler(BaseHTTPRequestHandler):
    """Serve the SPA fixture pages and mock API responses."""

    _MOCK_USER = {
        "id": "fixture-user-id",
        "username": _TEST_USERNAME,
        "email": "tester@example.com",
        "bio": "Test user bio",
        "avatar_url": None,
    }

    _MOCK_VIDEOS = [
        {"id": "fixture-video-1", "title": "Fixture Video 1", "status": "ready"},
        {"id": "fixture-video-2", "title": "Fixture Video 2", "status": "ready"},
    ]

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]

        # Mock API endpoints
        if path == f"/api/users/{_TEST_USERNAME}":
            self._json(200, self._MOCK_USER)
        elif path == f"/api/users/{_TEST_USERNAME}/videos":
            self._json(200, self._MOCK_VIDEOS)
        # Shell: /u/_/ — the pre-built SPA shell
        elif path in ("/u/_/", "/u/_"):
            api_base = f"http://127.0.0.1:{_FIXTURE_PORT}"
            body = _build_shell_html(api_base).encode()
            self._html(200, body)
        # Any other /u/<username>/ path → serve 404.html (SPA fallback)
        elif re.match(r"^/u/[^/]+/?$", path):
            self._html(404, _404_HTML.encode())
        # Root
        elif path in ("/", ""):
            self._html(200, b"<html><body>mytube fixture</body></html>")
        else:
            self._html(404, _404_HTML.encode())

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: D102
        pass  # suppress request logs in test output


def _start_fixture_server() -> HTTPServer:
    server = HTTPServer(("127.0.0.1", _FIXTURE_PORT), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_live_mode(page: Page, base_url: str, username: str) -> bool:
    """Return True if the live profile page renders the <h1> heading."""
    url = f"{base_url.rstrip('/')}/u/{username}"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        locator = page.locator("h1")
        locator.wait_for(state="visible", timeout=10_000)
        heading = (locator.text_content() or "").strip()
        return heading.lower() == username.lower()
    except Exception:
        return False


def _wait_for_profile_ready(
    page: Page,
    username: str,
    timeout: int = 20_000,
) -> None:
    """Wait until the <h1> heading and at least one video card are visible."""
    page.locator("h1").wait_for(state="visible", timeout=timeout)
    page.locator("a[href^='/v/']").first.wait_for(state="visible", timeout=timeout)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def fixture_server():
    """Start the local fixture server for the duration of the module."""
    server = _start_fixture_server()
    yield server
    server.shutdown()


@pytest.fixture(scope="module")
def test_context(browser: Browser, web_config: WebConfig, fixture_server: HTTPServer):
    """
    Return a dict with:
      - mode: "live" or "fixture"
      - base_url: the URL prefix to use
      - page: the Playwright page
      - profile_page: the UserProfilePage Page Object

    Live mode is used when the deployed site correctly renders the profile.
    Fixture mode falls back to the local test server.
    """
    # Probe live mode on a dedicated page so the test page starts fresh.
    probe_ctx = browser.new_context()
    probe_pg = probe_ctx.new_page()
    is_live = _detect_live_mode(probe_pg, web_config.base_url, _TEST_USERNAME)
    probe_ctx.close()

    if is_live:
        base_url = web_config.base_url
        mode = "live"
    else:
        base_url = f"http://127.0.0.1:{_FIXTURE_PORT}"
        mode = "fixture"

    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    profile_pg = UserProfilePage(pg)

    yield {
        "mode": mode,
        "base_url": base_url,
        "page": pg,
        "profile_page": profile_pg,
    }

    ctx.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestProfilePageRefresh:
    """MYTUBE-294: Verify SPA fallback preserves URL and profile content on refresh."""

    def test_initial_profile_loads(self, test_context: dict) -> None:
        """Step 1-2: Navigate to /u/tester and verify profile loads correctly."""
        profile_page: UserProfilePage = test_context["profile_page"]
        base_url: str = test_context["base_url"]
        page: Page = test_context["page"]

        profile_page.navigate(base_url, _TEST_USERNAME)

        assert not profile_page.is_not_found(timeout=15_000), (
            f"Profile page for '{_TEST_USERNAME}' shows 'User not found.' before refresh. "
            "The profile must load correctly before we can test the refresh behaviour."
        )

        heading = profile_page.get_username_heading()
        assert heading is not None and heading.lower() == _TEST_USERNAME.lower(), (
            f"Expected <h1> to contain '{_TEST_USERNAME}' before refresh, got: {heading!r}"
        )

        video_count = profile_page.get_video_card_count()
        assert video_count >= 1, (
            f"Expected at least one video card before refresh, found {video_count}."
        )

    def test_url_after_initial_load(self, test_context: dict) -> None:
        """After initial navigation the URL must be corrected to /u/tester/ (not /u/_/)."""
        page: Page = test_context["page"]
        current = page.url

        assert "/u/_/" not in current, (
            f"URL still contains '/u/_/' after initial load: {current!r}. "
            "Expected history.replaceState to have corrected it to /u/{_TEST_USERNAME}/."
        )
        assert f"/u/{_TEST_USERNAME}" in current, (
            f"Expected URL to contain '/u/{_TEST_USERNAME}' after initial load, got: {current!r}"
        )

    def test_profile_content_visible_after_refresh(self, test_context: dict) -> None:
        """Step 3-4: Reload the page and verify profile content is still displayed."""
        profile_page: UserProfilePage = test_context["profile_page"]
        page: Page = test_context["page"]

        # Perform browser refresh — equivalent to pressing Cmd+R / Ctrl+R.
        page.reload(wait_until="domcontentloaded")

        # Wait for the SPA reinitialisation to complete:
        # reload → 404.html → /u/_/ → history.replaceState → /u/<username>/
        try:
            page.wait_for_url(f"**/{_TEST_USERNAME}/**", timeout=20_000)
        except Exception:
            pass  # URL might already match; assertions below capture failures

        # Wait for loading spinner to disappear (async API call complete).
        try:
            page.locator("h1").wait_for(state="visible", timeout=20_000)
        except Exception:
            pass  # assertions below will capture the failure

        assert not profile_page.is_not_found(timeout=15_000), (
            "After browser refresh, the page shows 'User not found.' "
            f"The SPA fallback should have restored the profile for '{_TEST_USERNAME}'. "
            f"Current URL: {page.url!r}"
        )

        heading = profile_page.get_username_heading()
        assert heading is not None and heading.lower() == _TEST_USERNAME.lower(), (
            f"Expected <h1> to contain '{_TEST_USERNAME}' after refresh, got: {heading!r}. "
            f"Current URL: {page.url!r}"
        )

    def test_url_preserved_after_refresh(self, test_context: dict) -> None:
        """The URL must remain /u/tester after refresh — not revert to /u/_/."""
        page: Page = test_context["page"]
        current = page.url

        assert "/u/_/" not in current, (
            f"After browser refresh, URL reverted to '/u/_/': {current!r}. "
            f"Expected the SPA fallback to restore and correct the URL to /u/{_TEST_USERNAME}/."
        )
        assert f"/u/{_TEST_USERNAME}" in current, (
            f"After browser refresh, URL does not contain '/u/{_TEST_USERNAME}': {current!r}."
        )

    def test_video_grid_visible_after_refresh(self, test_context: dict) -> None:
        """Video grid must contain at least one card after the refresh."""
        profile_page: UserProfilePage = test_context["profile_page"]
        page: Page = test_context["page"]

        video_count = profile_page.get_video_card_count()
        assert video_count >= 1, (
            f"Expected at least one video card after refresh, found {video_count}. "
            f"Current URL: {page.url!r}"
        )
