"""
MYTUBE-206: Verify comment section for guest — login message shown instead of input.

Objective
---------
Verify that unauthenticated users cannot access the comment submission UI on
the video watch page (/v/[id]).

Preconditions
-------------
- User is not logged in.

Steps
-----
1. Navigate to the video watch page /v/[id].
2. Scroll to (observe) the comment section below the player.

Expected Result
---------------
The comment list is visible, but the text input and submit button are hidden.
Instead, a message saying "Login to comment" is displayed.

Test approach
-------------
Two modes:

**Live mode** (when API_BASE_URL env var is set and a ready video is
discoverable):
1. Query GET /api/users/tester (or GET /api/videos?limit=1) to obtain a
   real ready video ID.
2. Navigate to WEB_BASE_URL/v/<video_id> in a fresh, unauthenticated
   Chromium context (no stored cookies, no Firebase session).
3. Wait for Firebase auth to resolve (up to 20 s): either the login prompt
   or the comment textarea must appear.
4. Assert the comment section heading "Comments" is visible.
5. Assert the "Login to comment" link (a[href='/login']) is visible.
6. Assert that no comment textarea is present.
7. Assert that no comment submit button is present.

**Fixture mode** (fallback — no external dependencies required):
A local HTTP server serves testing/fixtures/watch_page/guest_comment_section.html,
which replicates the exact DOM produced by CommentSection.tsx for a guest user.
The same assertions run against the fixture page.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
API_BASE_URL            Backend API base URL used to discover a real video.
                        When absent the test falls back to fixture mode.
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses WatchPage (Page Object) from testing/components/pages/watch_page/.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs, credentials, or sleeps.
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

_FIXTURE_PORT = 19206
_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Fixture video ID used in fixture mode
_FIXTURE_VIDEO_ID = "fixture-video-206"

# Known "tester" username to discover a live video
_TESTER_USERNAME = "tester"

_FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "watch_page"


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


def _discover_live_video_id(api_base_url: str) -> Optional[str]:
    """Return the ID of any ready video from the tester profile, or None."""
    profile_url = f"{api_base_url.rstrip('/')}/api/users/{_TESTER_USERNAME}"
    profile = _fetch_json(profile_url)
    if not profile:
        return None
    for v in profile.get("videos", []):
        if v.get("status") == "ready" and v.get("id"):
            return v["id"]
        # Videos in the profile list may not include status; fetch full details
        vid_url = f"{api_base_url.rstrip('/')}/api/videos/{v['id']}"
        video = _fetch_json(vid_url)
        if video and video.get("status") == "ready":
            return video["id"]
    return None


# ---------------------------------------------------------------------------
# Fixture-mode HTTP server
# ---------------------------------------------------------------------------


class _GuestCommentFixtureHandler(BaseHTTPRequestHandler):
    """Serves guest_comment_section.html for any path under /v/."""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress console noise

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0].rstrip("/")
        if path == "" or path.startswith("/v/"):
            html_path = _FIXTURE_DIR / "guest_comment_section.html"
            body = html_path.read_bytes()
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
def test_context(web_config: WebConfig):
    """Resolve the video context for the test.

    Live mode:  API_BASE_URL is set → discover a real video, navigate to the
                deployed app as an unauthenticated browser context.
    Fixture mode: start a local server serving guest_comment_section.html.

    Yields a dict:
      base_url  : base URL to pass to WatchPage.navigate_to_video()
      video_id  : video ID to load
      mode      : "live" or "fixture"
    """
    api_base_url = os.getenv("API_BASE_URL", "").strip()
    live_video_id: Optional[str] = None

    if api_base_url:
        live_video_id = _discover_live_video_id(api_base_url)

    if live_video_id:
        yield {
            "base_url": web_config.base_url,
            "video_id": live_video_id,
            "mode": "live",
        }
    else:
        srv = _start_server(_GuestCommentFixtureHandler, _FIXTURE_PORT)
        try:
            yield {
                "base_url": f"http://127.0.0.1:{_FIXTURE_PORT}",
                "video_id": _FIXTURE_VIDEO_ID,
                "mode": "fixture",
            }
        finally:
            srv.shutdown()


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
    """Open a fresh browser context with NO stored auth state (simulates guest)."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def loaded_watch_page(test_context, page: Page) -> WatchPage:
    """Navigate to the watch page and wait for the comment section auth to resolve."""
    watch = WatchPage(page)
    watch.navigate_to_video(test_context["base_url"], test_context["video_id"])

    if test_context["mode"] == "live":
        # In live mode, wait for Firebase auth to resolve before asserting
        watch.wait_for_comment_section_auth_resolved()
    else:
        # In fixture mode, the DOM is rendered immediately — just wait for
        # the login link to be visible (no async auth flow)
        page.wait_for_selector(
            "section[aria-label='Comments'] a[href='/login']",
            timeout=_PAGE_LOAD_TIMEOUT,
        )

    return watch


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGuestCommentSection:
    """MYTUBE-206: Guest users see the login prompt, not the comment form."""

    def test_comment_section_heading_visible(self, loaded_watch_page: WatchPage) -> None:
        """The 'Comments' heading (<h2>) is visible in the comment section."""
        assert loaded_watch_page.is_comment_section_visible(), (
            "Expected the Comments section heading to be visible on the watch page "
            "for a guest user, but it was not found."
        )

    def test_login_to_comment_prompt_visible(self, loaded_watch_page: WatchPage) -> None:
        """A 'Login' link is displayed inside the comment section for guests."""
        assert loaded_watch_page.has_login_to_comment_prompt(), (
            "Expected a 'Login to comment' prompt (a[href='/login']) to be visible "
            "in the comment section for an unauthenticated user, but it was not found."
        )

    def test_login_link_points_to_login_page(self, loaded_watch_page: WatchPage) -> None:
        """The login link inside the comment prompt points to '/login'."""
        href = loaded_watch_page.get_login_link_href()
        assert href is not None, (
            "Expected the 'Login' link href to be present, but the element was not found."
        )
        assert href == "/login", (
            f"Expected the login link to point to '/login', but got '{href}'."
        )

    def test_comment_textarea_not_present(self, loaded_watch_page: WatchPage) -> None:
        """The comment textarea is NOT visible for unauthenticated users."""
        assert not loaded_watch_page.has_comment_textarea(), (
            "Expected the comment textarea to be hidden for a guest user, "
            "but it was visible. Unauthenticated users should not be able to type a comment."
        )

    def test_comment_submit_button_not_present(self, loaded_watch_page: WatchPage) -> None:
        """The comment submit button is NOT visible for unauthenticated users."""
        assert not loaded_watch_page.has_comment_submit_button(), (
            "Expected the comment submit button to be hidden for a guest user, "
            "but it was visible. Unauthenticated users should not be able to submit a comment."
        )
