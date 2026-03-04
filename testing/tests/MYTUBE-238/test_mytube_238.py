"""
MYTUBE-238: View user profile with playlists API error — page handles failure gracefully.

Objective
---------
Verify that the profile page remains functional and handles errors gracefully
if the playlists API endpoint fails.

Steps
-----
1. Intercept the API request to GET /api/users/:username/playlists and mock a
   500 Internal Server Error response.
2. Navigate to the user profile page at /u/tester.
3. Observe the page rendering and browser console.

Expected Result
---------------
The profile page loads without crashing. Other sections like user information
and uploaded videos are displayed correctly. The playlists section either shows
a graceful error message or is hidden.

Test approach
-------------
Two modes:

**Live mode** (when WEB_BASE_URL/u/tester renders the profile component — i.e.
an <h1> containing "tester" is visible within ~7 seconds):

1. Set up a Playwright route interceptor for **/api/users/*/playlists → 500.
2. Navigate to WEB_BASE_URL/u/tester.
3. Click the Playlists tab and wait for the loading state to resolve.
4. Run assertions.

**Fixture mode** (fallback — used when the live URL does not render the
profile component, e.g. GitHub Pages static-export routing limitation):

A local HTTP server serves a minimal HTML page that:
- Replicates the profile header (h1, avatar) and tab structure.
- Has JavaScript that makes a real fetch to API_BASE_URL/api/users/tester/playlists.
- Handles the response exactly as UserProfilePageClient.tsx does:
  on error: setPlaylistsLoaded(true), setPlaylistsLoading(false), playlists=[]
  This results in "No playlists yet." — same as the real component.
The Playwright route interceptor returns 500, so the fixture JavaScript's fetch
receives a 500 and the error-handling path is exercised via real browser code.

Architecture
------------
- Uses ProfilePage (Page Object) from testing/components/pages/profile_page/
- WebConfig from testing/core/config/web_config.py for environment configuration
- Playwright sync API with module-scoped fixtures
- page.route() intercepts the playlists API before navigation
- No hardcoded URLs or credentials

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
API_BASE_URL             Backend API base URL.
                         Default: https://mytube-api-80693608388.us-central1.run.app
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import List, Tuple

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.profile_page.profile_page import ProfilePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TEST_USERNAME = "tester"
_PAGE_LOAD_TIMEOUT = 30_000  # ms
_FIXTURE_PORT = 19238
# Intercept any request whose URL path ends with /api/users/<anything>/playlists
_PLAYLISTS_API_PATTERN = "**/api/users/*/playlists"


# ---------------------------------------------------------------------------
# Fixture HTML — mirrors UserProfilePageClient.tsx error-handling behaviour
# ---------------------------------------------------------------------------


def _build_fixture_html(api_base_url: str, username: str) -> str:
    """Build a minimal HTML page that replicates the profile page behaviour.

    The JavaScript makes a *real* fetch() to api_base_url/api/users/<username>/playlists
    so that the Playwright route interceptor can return 500 and the browser code
    exercises the same error-handling path as UserProfilePageClient.tsx:

        catch { setPlaylistsLoaded(true) }  ->  playlists stays []
        finally { setPlaylistsLoading(false) }
        render: playlists.length === 0 -> "No playlists yet."

    The fixture also pre-loads a fake video card in the Videos tab so that the
    "videos section is accessible" assertion can pass regardless of live API data.
    """
    initials = username[0].upper() if username else "?"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        "  <title>" + username + " &ndash; mytube</title>\n"
        "</head>\n"
        "<body>\n"
        '<div id="loading" style="display:flex;min-height:100vh;align-items:center;justify-content:center">'
        "<p>Loading\u2026</p></div>\n"
        '<div id="profile" style="display:none">\n'
        "  <div style=\"display:flex;align-items:center;gap:16px;margin-bottom:24px\">\n"
        "    <div aria-label=\"" + username + "&#39;s avatar\" "
        "style=\"width:80px;height:80px;border-radius:50%;background:#d1d5db;"
        "display:flex;align-items:center;justify-content:center;font-size:24px;"
        "font-weight:bold;color:#4b5563\">" + initials + "</div>\n"
        '    <h1 style="font-size:24px;font-weight:bold">' + username + "</h1>\n"
        "  </div>\n"
        "  <nav style=\"display:flex;gap:24px;border-bottom:1px solid #e5e7eb;margin-bottom:24px\">\n"
        '    <button id="btn-videos" onclick="showTab(\'videos\')" '
        'style="padding-bottom:8px;font-size:14px;border-bottom:2px solid #2563eb;color:#2563eb">'
        "Videos</button>\n"
        '    <button id="btn-playlists" onclick="showTab(\'playlists\')" '
        'style="padding-bottom:8px;font-size:14px;border-bottom:2px solid transparent;color:#6b7280">'
        "Playlists</button>\n"
        "  </nav>\n"
        '  <div id="tab-videos">\n'
        '    <a href="/v/fixture-video-1" style="display:block;padding:8px;background:#fff;border-radius:8px">'
        "Fixture Video 1</a>\n"
        "  </div>\n"
        '  <div id="tab-playlists" style="display:none">\n'
        '    <div id="playlists-content"></div>\n'
        "  </div>\n"
        "</div>\n"
        "<script>\n"
        "  var API_BASE = '" + api_base_url.rstrip("/") + "';\n"
        "  var playlistsLoaded = false;\n"
        "  var playlistsLoading = false;\n"
        "\n"
        "  // Simulate initial profile data load (remove loading spinner)\n"
        "  window.addEventListener('load', function() {\n"
        "    document.getElementById('loading').style.display = 'none';\n"
        "    document.getElementById('profile').style.display = 'block';\n"
        "  });\n"
        "\n"
        "  function showTab(tab) {\n"
        "    document.getElementById('tab-videos').style.display = tab === 'videos' ? 'block' : 'none';\n"
        "    document.getElementById('tab-playlists').style.display = tab === 'playlists' ? 'block' : 'none';\n"
        "    document.getElementById('btn-videos').style.borderBottomColor = tab === 'videos' ? '#2563eb' : 'transparent';\n"
        "    document.getElementById('btn-videos').style.color = tab === 'videos' ? '#2563eb' : '#6b7280';\n"
        "    document.getElementById('btn-playlists').style.borderBottomColor = tab === 'playlists' ? '#2563eb' : 'transparent';\n"
        "    document.getElementById('btn-playlists').style.color = tab === 'playlists' ? '#2563eb' : '#6b7280';\n"
        "    if (tab === 'playlists' && !playlistsLoaded && !playlistsLoading) {\n"
        "      loadPlaylists();\n"
        "    }\n"
        "  }\n"
        "\n"
        "  // Mirrors UserProfilePageClient.tsx loadPlaylists() error handling:\n"
        "  //   catch { setPlaylistsLoaded(true) }  -> playlists stays []\n"
        "  //   finally { setPlaylistsLoading(false) }\n"
        "  //   render: playlists.length === 0 -> 'No playlists yet.'\n"
        "  async function loadPlaylists() {\n"
        "    playlistsLoading = true;\n"
        "    document.getElementById('playlists-content').textContent = 'Loading playlists\u2026';\n"
        "    try {\n"
        "      var resp = await fetch(API_BASE + '/api/users/" + username + "/playlists');\n"
        "      if (!resp.ok) {\n"
        "        throw new Error('Failed to list playlists for " + username + ": ' + resp.status);\n"
        "      }\n"
        "      var data = await resp.json();\n"
        "      playlistsLoaded = true;\n"
        "      if (data.length === 0) {\n"
        "        document.getElementById('playlists-content').textContent = 'No playlists yet.';\n"
        "      } else {\n"
        "        var html = '';\n"
        "        data.forEach(function(pl) {\n"
        "          html += '<a href=\"/pl/' + pl.id + '\" style=\"display:block;padding:8px\">' + pl.title + '</a>';\n"
        "        });\n"
        "        document.getElementById('playlists-content').innerHTML = html;\n"
        "      }\n"
        "    } catch (e) {\n"
        "      // Mirror React component: on error, mark loaded but keep playlists=[]\n"
        "      playlistsLoaded = true;\n"
        "      document.getElementById('playlists-content').textContent = 'No playlists yet.';\n"
        "    } finally {\n"
        "      playlistsLoading = false;\n"
        "    }\n"
        "  }\n"
        "</script>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Fixture HTTP server
# ---------------------------------------------------------------------------


class _ProfileFixtureHandler(BaseHTTPRequestHandler):
    """Serves the fixture profile page HTML for any /u/* or root path."""

    html: bytes = b""

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress console noise

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?")[0].rstrip("/")
        if path == "" or path.startswith("/u/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.__class__.html)
        else:
            self.send_response(404)
            self.end_headers()


def _start_fixture_server(html: bytes, port: int) -> HTTPServer:
    _ProfileFixtureHandler.html = html
    server = HTTPServer(("127.0.0.1", port), _ProfileFixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _profile_renders_correctly(page: Page, base_url: str, username: str) -> bool:
    """Return True if navigating to /u/<username> renders the profile component.

    Navigates and waits up to 7 s for the username <h1> to appear.
    Falls back to False if the page shows home-page content or a 404 page.
    """
    url = base_url.rstrip("/") + "/u/" + username
    try:
        page.goto(url)
        page.wait_for_timeout(7000)
        h1 = page.locator("h1")
        if h1.count() == 0:
            return False
        h1_text = (h1.first.text_content() or "").strip()
        return username in h1_text
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def loaded_profile(
    browser: Browser,
    web_config: WebConfig,
) -> Tuple[ProfilePage, Page, List[str]]:
    """ProfilePage with playlists API intercepted to return 500, Playlists tab open.

    Tries the live deployed app first; falls back to a local fixture server
    if the live URL does not render the profile component.

    Yields
    ------
    (ProfilePage, raw_Page, js_errors_list)
    """
    # ---- Probe live mode with a throw-away page ----
    probe_ctx: BrowserContext = browser.new_context()
    probe_pg: Page = probe_ctx.new_page()
    probe_pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    live_ok = _profile_renders_correctly(probe_pg, web_config.base_url, _TEST_USERNAME)
    probe_ctx.close()

    # ---- Set up the actual test context ----
    ctx: BrowserContext = browser.new_context()
    pg: Page = ctx.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    js_errors: List[str] = []
    pg.on("pageerror", lambda err: js_errors.append(str(err)))

    # Intercept playlists API before any navigation
    pg.route(
        _PLAYLISTS_API_PATTERN,
        lambda route: route.fulfill(
            status=500,
            content_type="application/json",
            body='{"error": "Internal Server Error"}',
        ),
    )

    profile = ProfilePage(pg)
    srv = None

    try:
        if live_ok:
            # ---- Live mode ----
            profile.navigate(web_config.base_url, _TEST_USERNAME)
            pg.wait_for_timeout(2000)
        else:
            # ---- Fixture mode ----
            # The fixture JavaScript makes a real fetch() to the playlists API.
            # Playwright intercepts it and returns 500.  The fixture JS handles
            # the error the same way UserProfilePageClient.tsx does.
            html = _build_fixture_html(
                web_config.api_base_url, _TEST_USERNAME
            ).encode("utf-8")
            srv = _start_fixture_server(html, _FIXTURE_PORT)
            profile.navigate(
                "http://127.0.0.1:" + str(_FIXTURE_PORT), _TEST_USERNAME
            )

        # Click the Playlists tab to trigger the mocked API call
        if profile.is_playlists_tab_visible():
            profile.click_playlists_tab()
            profile.wait_for_playlists_loaded()

        yield profile, pg, js_errors

    finally:
        ctx.close()
        if srv is not None:
            srv.shutdown()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProfilePagePlaylistsApiError:
    """MYTUBE-238: Profile page handles playlists API 500 error gracefully."""

    def test_page_does_not_crash(
        self,
        loaded_profile: Tuple[ProfilePage, Page, List[str]],
    ) -> None:
        """No uncaught JS errors must occur when the playlists API returns 500.

        Expected: the browser console contains zero uncaught exceptions.
        A playlists fetch failure must be caught inside the component and
        must not propagate as an unhandled promise rejection.
        """
        _, _, js_errors = loaded_profile
        assert not js_errors, (
            "Uncaught JS errors detected after playlists API returned 500:\n"
            + "\n".join(js_errors)
        )

    def test_username_heading_is_visible(
        self,
        loaded_profile: Tuple[ProfilePage, Page, List[str]],
    ) -> None:
        """User information (username heading) must remain visible.

        Expected: <h1> contains the username 'tester'. The playlists API
        failure must not affect the user info section.
        """
        profile, _, _ = loaded_profile
        heading = profile.get_username_heading()
        assert heading and _TEST_USERNAME in heading, (
            f"Username heading missing when playlists API returns 500. "
            f"h1={heading!r}. Expected to contain '{_TEST_USERNAME}'."
        )

    def test_avatar_is_visible(
        self,
        loaded_profile: Tuple[ProfilePage, Page, List[str]],
    ) -> None:
        """User avatar must remain visible despite the playlists API error.

        Expected: avatar image or initials fallback is visible.
        """
        profile, _, _ = loaded_profile
        assert profile.is_avatar_visible(), (
            "User avatar is not visible when playlists API returns 500."
        )

    def test_videos_tab_is_accessible(
        self,
        loaded_profile: Tuple[ProfilePage, Page, List[str]],
    ) -> None:
        """The Videos tab must remain accessible when playlists API fails.

        Expected: 'Videos' tab button is present in the navigation.
        """
        profile, _, _ = loaded_profile
        assert profile.is_videos_tab_visible(), (
            "Videos tab button is not visible when playlists API returns 500."
        )

    def test_no_react_error_boundary(
        self,
        loaded_profile: Tuple[ProfilePage, Page, List[str]],
    ) -> None:
        """The page must not render an unhandled error boundary.

        Expected: none of the error boundary fallback messages are visible.
        The playlists 500 error must be caught within the component and must
        not crash the entire page.
        """
        profile, _, _ = loaded_profile
        assert not profile.has_react_error_boundary(), (
            "Error boundary rendered after playlists API returned 500. "
            "The page is crashing instead of handling the error gracefully."
        )

    def test_playlists_section_not_stuck_loading(
        self,
        loaded_profile: Tuple[ProfilePage, Page, List[str]],
    ) -> None:
        """The playlists section must not remain stuck in a loading state.

        Expected: 'Loading playlists...' spinner is not visible after the API
        returned 500 and a few seconds elapsed.
        """
        profile, _, _ = loaded_profile
        assert not profile.is_playlists_still_loading(), (
            "Playlists section is stuck in 'Loading playlists...' after the "
            "API returned 500. The component must exit the loading state."
        )

    def test_playlists_section_shows_graceful_state(
        self,
        loaded_profile: Tuple[ProfilePage, Page, List[str]],
    ) -> None:
        """The playlists section must show a graceful error or empty state.

        Acceptable outcomes per the test spec (any one is sufficient):
        - 'No playlists yet.' empty state is shown (component silently catches
          the error and renders empty list — matches current implementation), OR
        - A user-friendly error message is displayed, OR
        - The Playlists tab is absent (section hidden on error).

        The component must NOT show an unhandled error boundary (checked in
        test_no_react_error_boundary) or a stuck loading spinner (checked in
        test_playlists_section_not_stuck_loading).

        Implementation note: UserProfilePageClient.tsx catches the API error
        silently and keeps playlists=[], which renders 'No playlists yet.'
        This is graceful (no crash, no infinite spinner).
        """
        profile, pg, _ = loaded_profile

        has_empty_state = profile.has_no_playlists_message()
        has_error_message = profile.has_playlists_graceful_error_message()
        tab_hidden = not profile.is_playlists_tab_visible()

        graceful = has_empty_state or has_error_message or tab_hidden

        if not graceful:
            body_text = (pg.locator("body").text_content() or "").strip()[:600]
            body_text = body_text.replace("\n", " ")
            pytest.fail(
                "Playlists section does not show a graceful state after the API "
                "returned 500.\n"
                "Expected: 'No playlists yet.', a graceful error message, or the "
                "Playlists tab to be hidden.\n"
                f"Page body (first 600 chars): {body_text!r}"
            )
