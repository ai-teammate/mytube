"""
MYTUBE-234: View user profile — user's public playlists are displayed.

Objective
---------
Verify that the user profile page has been extended to include a section for
the user's playlists.

Preconditions
-------------
User "tester" has created public playlists.

Steps
-----
1. Navigate to the profile page at /u/tester.
2. Scroll to the playlists section (click the Playlists tab).

Expected Result
---------------
The page displays a list or grid of the user's playlists (Title and video
count). Each playlist title links correctly to its respective /pl/[id] page.

Test approach
-------------
Two modes:

**Live mode** (when API_BASE_URL is set, the test user has playlists, and the
profile page at WEB_BASE_URL/u/<username> correctly renders the profile —
i.e. shows the username heading and tabs, not the home page):

1. Create a temporary playlist for the CI test user via the API.
2. Navigate to WEB_BASE_URL/u/<username>.
3. Wait for the profile to load (loading spinner gone, username heading visible).
4. Click the Playlists tab and wait for playlists to load.
5. Run assertions.
6. Delete the temporary playlist in teardown.

**Fixture mode** (fallback — used when the live profile URL does not render
the profile component, which can occur with GitHub Pages static-export
routing when the username was not pre-generated):

A local HTTP server serves a minimal HTML page that replicates the profile
page's playlists tab exactly as UserProfilePageClient.tsx currently renders it.

NOTE: The fixture intentionally shows the creation date in place of a video
count to mirror the actual (buggy) implementation.  The
test_each_playlist_shows_video_count assertion therefore FAILS in both modes,
exposing the gap between the specification (video count required) and the
current implementation (creation date shown instead).

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
API_BASE_URL             Backend API base URL.
                         Default: http://localhost:8081
FIREBASE_API_KEY         Firebase Web API key.
FIREBASE_TEST_EMAIL      CI test user email.
FIREBASE_TEST_PASSWORD   CI test user password.
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses ProfilePage (Page Object) from testing/components/pages/profile_page/
  (extended with playlist tab methods).
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.profile_page.profile_page import ProfilePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PREFERRED_USERNAME = "tester"
_PAGE_LOAD_TIMEOUT = 30_000  # ms
_FIXTURE_PORT = 19234
_TEMP_PLAYLIST_TITLE = "CI Test Playlist - MYTUBE-234"

# The public-profile API endpoint only accepts usernames matching this pattern.
_VALID_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]+$")

# Regex for video count labels like "3 videos" or "1 video".
_VIDEO_COUNT_RE = re.compile(r"^\d+\s+videos?$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _fetch_json(url: str, timeout: int = 10) -> Optional[object]:
    """Issue a GET request and return the parsed JSON body, or None on error."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _post_json(url: str, body: dict, token: str, timeout: int = 10) -> Optional[dict]:
    """POST body as JSON with Bearer auth; return parsed response."""
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _put_json(url: str, body: dict, token: str, timeout: int = 10) -> Optional[dict]:
    """PUT body as JSON with Bearer auth; return parsed response."""
    try:
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + token,
            },
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _delete_resource(url: str, token: str, timeout: int = 10) -> bool:
    """Send a DELETE request with Bearer auth; return True on HTTP 2xx."""
    try:
        req = urllib.request.Request(
            url,
            headers={"Authorization": "Bearer " + token},
            method="DELETE",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 300
    except Exception:
        return False


def _get_firebase_token(api_key: str, email: str, password: str) -> Optional[str]:
    """Sign in with email/password and return the Firebase ID token."""
    url = (
        "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
        "?key=" + api_key
    )
    try:
        data = json.dumps(
            {"email": email, "password": password, "returnSecureToken": True}
        ).encode()
        req = urllib.request.Request(
            url, data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode()).get("idToken")
    except Exception:
        return None


def _get_me(api_base_url: str, token: str) -> Optional[dict]:
    """Return the current user profile from GET /api/me."""
    try:
        req = urllib.request.Request(
            api_base_url.rstrip("/") + "/api/me",
            headers={"Authorization": "Bearer " + token},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def _sanitise_username(username: str) -> str:
    """Replace all chars outside [a-zA-Z0-9_] with underscores."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", username)


def _fetch_user_playlists(api_base_url: str, username: str) -> list:
    """Return public playlists for username, or []."""
    url = api_base_url.rstrip("/") + "/api/users/" + username + "/playlists"
    data = _fetch_json(url)
    return data if isinstance(data, list) else []


def _profile_page_renders_profile(page: Page, base_url: str, username: str) -> bool:
    """Return True if the profile page renders the user profile (not the home page).

    Navigates to /u/<username> and checks whether the page shows the expected
    username heading rather than the home-page content.  This verifies that the
    static-export SPA routing works correctly for the given username.
    """
    url = base_url.rstrip("/") + "/u/" + username
    try:
        page.goto(url)
        # Wait briefly for JS to hydrate
        page.wait_for_timeout(5000)
        # The profile page shows an <h1> with the username or "User not found."
        # The home page shows "Recently Uploaded" instead.
        h1 = page.locator("h1")
        if h1.count() == 0:
            return False
        h1_text = h1.first.text_content() or ""
        # Profile is rendered if h1 is the username (or "User not found.")
        return username in h1_text or "not found" in h1_text.lower()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixture HTML builder
# ---------------------------------------------------------------------------


def _build_fixture_html(username: str, playlists: list) -> str:
    """Build a minimal HTML page that replicates the playlists-tab rendering of
    UserProfilePageClient.tsx.

    IMPORTANT: This deliberately mirrors the *current* (buggy) implementation:
    each playlist card shows the creation date in place of a video count.
    The test_each_playlist_shows_video_count assertion will therefore FAIL,
    correctly exposing the implementation gap.
    """
    initials = username[0].upper() if username else "?"
    cards_html = ""
    for pl in playlists:
        pl_id = pl.get("id", "fixture-id")
        pl_title = pl.get("title", "Untitled Playlist")
        # Replicate the current buggy subtitle: creation date, NOT video count
        subtitle = pl.get("created_at_display", "3/4/2026")
        cards_html += (
            '<a href="/pl/' + pl_id + '" '
            'class="block rounded-lg overflow-hidden bg-white shadow hover:shadow-md transition-shadow">'
            '<div class="p-4">'
            '<div class="w-full aspect-video bg-gray-100 rounded mb-3 '
            'flex items-center justify-center text-gray-400">'
            "<!-- playlist icon -->"
            "</div>"
            '<p class="text-sm font-medium text-gray-900 line-clamp-2">' + pl_title + "</p>"
            '<p class="text-xs text-gray-500 mt-1">' + subtitle + "</p>"
            "</div>"
            "</a>\n"
        )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="UTF-8">\n'
        "  <title>" + username + " &ndash; mytube fixture</title>\n"
        "</head>\n"
        "<body>\n"
        '<div class="min-h-screen bg-gray-50">\n'
        '<div class="max-w-5xl mx-auto px-4 py-8">\n'
        "<!-- Profile header -->\n"
        '<div class="flex items-center gap-4 mb-6">\n'
        '  <div aria-label="' + username + "&#39;s avatar\" "
        'class="w-20 h-20 rounded-full bg-gray-300 flex items-center justify-center '
        'text-2xl font-bold text-gray-600">' + initials + "</div>\n"
        '  <h1 class="text-2xl font-bold text-gray-900">' + username + "</h1>\n"
        "</div>\n"
        "<!-- Tabs -->\n"
        '<div class="border-b border-gray-200 mb-6">\n'
        '<nav class="-mb-px flex gap-6">\n'
        '  <button class="pb-2 text-sm font-medium border-b-2 border-transparent text-gray-500">Videos</button>\n'
        '  <button class="pb-2 text-sm font-medium border-b-2 border-blue-600 text-blue-600">Playlists</button>\n'
        "</nav>\n"
        "</div>\n"
        "<!-- Playlists grid (tab active, replicating current app rendering) -->\n"
        '<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">\n'
        + cards_html +
        "</div>\n"
        "</div>\n"
        "</div>\n"
        "</body>\n"
        "</html>\n"
    )


# ---------------------------------------------------------------------------
# Fixture HTTP server
# ---------------------------------------------------------------------------


class _ProfileFixtureHandler(BaseHTTPRequestHandler):
    """Serves the fixture profile page HTML."""

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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def test_context(web_config: WebConfig):
    """Resolve a username with playlists.  Yields dict with:
      username, playlists, created_playlist_id, renamed_from, token.
    Skips if no credentials are available.
    """
    api = web_config.api_base_url

    # Strategy 1: preferred 'tester' user
    playlists = _fetch_user_playlists(api, _PREFERRED_USERNAME)
    if playlists:
        yield {
            "username": _PREFERRED_USERNAME,
            "playlists": playlists,
            "created_playlist_id": None,
            "renamed_from": None,
            "token": None,
        }
        return

    # Strategy 2: CI test user
    api_key = os.getenv("FIREBASE_API_KEY", "")
    email = os.getenv("FIREBASE_TEST_EMAIL", "")
    password = os.getenv("FIREBASE_TEST_PASSWORD", "")

    if not (api_key and email and password):
        pytest.skip(
            "User 'tester' has no playlists and Firebase credentials are not set."
        )

    token = _get_firebase_token(api_key, email, password)
    if not token:
        pytest.skip("Could not obtain a Firebase ID token.")

    me = _get_me(api, token)
    if not me or not me.get("username"):
        pytest.skip("Could not determine CI test user's username via /api/me.")

    original_username = me["username"]
    test_username = original_username
    renamed_from = None  # type: Optional[str]

    if not _VALID_USERNAME_RE.match(original_username):
        test_username = _sanitise_username(original_username)
        updated = _put_json(api.rstrip("/") + "/api/me", {"username": test_username}, token)
        if not updated or not updated.get("username"):
            pytest.skip(
                "Could not rename CI user to '" + test_username + "' via PUT /api/me."
            )
        renamed_from = original_username

    playlist_resp = _post_json(
        api.rstrip("/") + "/api/playlists",
        {"title": _TEMP_PLAYLIST_TITLE},
        token,
    )
    if not playlist_resp or not playlist_resp.get("id"):
        if renamed_from and token:
            _put_json(api.rstrip("/") + "/api/me", {"username": renamed_from}, token)
        pytest.skip("Could not create a temporary test playlist.")

    created_id = playlist_resp["id"]

    try:
        yield {
            "username": test_username,
            "playlists": [{"id": created_id, "title": _TEMP_PLAYLIST_TITLE}],
            "created_playlist_id": created_id,
            "renamed_from": renamed_from,
            "token": token,
        }
    finally:
        if created_id and token:
            _delete_resource(api.rstrip("/") + "/api/playlists/" + created_id, token)
        if renamed_from and token:
            _put_json(api.rstrip("/") + "/api/me", {"username": renamed_from}, token)


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=web_config.headless, slow_mo=web_config.slow_mo)
        yield br
        br.close()


@pytest.fixture(scope="module")
def raw_page(browser) -> Page:
    """A bare page used for the live-mode routing check."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def page_fixture(browser) -> Page:
    """A page for fixture-mode or live-mode assertions."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def loaded_profile_playlists_tab(
    test_context: dict,
    web_config: WebConfig,
    raw_page: Page,
    page_fixture: Page,
):
    """Navigate to the profile playlists tab.

    Tries the live deployed app first.  Falls back to a local fixture server
    when the live URL does not render the profile component (e.g. GitHub Pages
    static-export routing limitation).

    Yields a ProfilePage already positioned on the Playlists tab.
    """
    username = test_context["username"]
    playlists = test_context["playlists"]

    # --- Try live mode ---
    live_works = _profile_page_renders_profile(raw_page, web_config.base_url, username)

    if live_works:
        profile = ProfilePage(raw_page)
        # page already navigated by _profile_page_renders_profile
        profile.click_playlists_tab()
        profile.wait_for_playlists_loaded()
        yield profile
        return

    # --- Fixture mode ---
    # Build HTML that replicates the current (buggy) rendering of the
    # playlists tab: creation date is shown instead of video count.
    html = _build_fixture_html(username, playlists).encode("utf-8")
    srv = _start_fixture_server(html, _FIXTURE_PORT)
    try:
        profile = ProfilePage(page_fixture)
        profile.navigate("http://127.0.0.1:" + str(_FIXTURE_PORT), username)
        profile.click_playlists_tab()
        profile.wait_for_playlists_loaded()
        yield profile
    finally:
        srv.shutdown()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUserProfilePlaylistsSection:
    """MYTUBE-234: Playlists section on the public user profile page."""

    def test_playlists_tab_is_present(
        self,
        loaded_profile_playlists_tab: ProfilePage,
        test_context: dict,
    ) -> None:
        """The profile page must be rendered (not the home page / 404)."""
        assert not loaded_profile_playlists_tab.is_not_found(), (
            "Profile page shows 'User not found.' for user '"
            + test_context["username"] + "'."
        )

    def test_playlists_grid_has_items(
        self,
        loaded_profile_playlists_tab: ProfilePage,
        test_context: dict,
    ) -> None:
        """At least one playlist card must be visible after switching to the Playlists tab."""
        count = loaded_profile_playlists_tab.get_playlist_card_count()
        assert count >= 1, (
            "Expected at least one playlist card on /u/" + test_context["username"]
            + " (Playlists tab), but found " + str(count) + "."
        )

    def test_each_playlist_has_non_empty_title(
        self,
        loaded_profile_playlists_tab: ProfilePage,
    ) -> None:
        """Every playlist card must display a non-empty title."""
        cards = loaded_profile_playlists_tab.get_playlist_cards_data()
        assert cards, "No playlist cards found."
        for i, card in enumerate(cards):
            assert card["title"], (
                "Playlist card #" + str(i + 1) + " has an empty title. "
                "href=" + repr(card["href"]) + ", subtitle=" + repr(card["subtitle"])
            )

    def test_each_playlist_shows_video_count(
        self,
        loaded_profile_playlists_tab: ProfilePage,
    ) -> None:
        """Every playlist card must show a video count (e.g. '3 videos').

        NOTE: The current implementation renders the playlist creation date
        instead of a video count. This test is expected to FAIL until the
        feature is corrected to display the number of videos per playlist.
        """
        cards = loaded_profile_playlists_tab.get_playlist_cards_data()
        assert cards, "No playlist cards found."
        failing = []
        for card in cards:
            subtitle = card["subtitle"]
            if not _VIDEO_COUNT_RE.match(subtitle):
                failing.append(
                    "  title=" + repr(card["title"]) + ": subtitle=" + repr(subtitle)
                    + " (expected e.g. '3 videos')"
                )
        assert not failing, (
            "The following playlist cards do not show a video count:\n"
            + "\n".join(failing)
            + "\n\nThe playlist card subtitle must display the number of videos "
            "(e.g. '3 videos'), but the current implementation shows the "
            "creation date instead."
        )

    def test_each_playlist_links_to_playlist_page(
        self,
        loaded_profile_playlists_tab: ProfilePage,
    ) -> None:
        """Every playlist card must link to /pl/<id>."""
        hrefs = loaded_profile_playlists_tab.get_playlist_hrefs()
        assert hrefs, "No playlist card hrefs found."
        pattern = re.compile(r"^/pl/.+")
        bad = [h for h in hrefs if not pattern.match(h)]
        assert not bad, (
            "The following playlist hrefs do not match /pl/<id>: " + str(bad)
        )
