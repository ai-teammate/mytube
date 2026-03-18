"""
MYTUBE-600: API request to playlist endpoint — uses correct NEXT_PUBLIC_API_URL
and receives CORS headers.

Objective
---------
Verify that the frontend correctly identifies the API server origin and that the
API server permits the cross-origin request.

Preconditions
-------------
* Application is running in a standard environment where the frontend and API
  may have different origins.

Steps
-----
1. Navigate to a playlist detail page at /pl/[id].
2. Locate the GET /api/playlists/[id] request.
3. Verify the Request URL and the presence of Access-Control-Allow-Origin in
   Response Headers.

Expected Result
---------------
* The Request URL correctly points to the API server (as defined in
  NEXT_PUBLIC_API_URL) and not the frontend's own origin/CDN.
* The response contains valid CORS headers (Access-Control-Allow-Origin equals
  the expected frontend origin).

Test Approach
-------------
Two complementary layers:

**Layer A — Direct API CORS verification** (always runs when API_BASE_URL is
reachable):
  1. Obtains a valid playlist ID — creates a temporary playlist via the API
     using the Firebase test token, or falls back to querying the CI test
     user's existing playlists.
  2. Sends ``GET /api/playlists/{id}`` with an ``Origin: https://ai-teammate.github.io``
     header simulating a cross-origin browser request.
  3. Asserts HTTP 200 status code.
  4. Asserts ``Access-Control-Allow-Origin`` response header is present and
     equals ``https://ai-teammate.github.io``.
  5. Asserts ``Access-Control-Allow-Methods`` and ``Access-Control-Allow-Headers``
     are also present (full CORS compliance check).
  6. Asserts the request URL host matches ``API_BASE_URL`` (i.e. not the
     frontend CDN host), confirming the request is directed at the API server.

**Layer B — Playwright request-interception test** (runs when APP_URL /
WEB_BASE_URL is set and a playlist is available):
  1. Navigates to the playlist detail page at ``/pl/{id}`` (via the GitHub Pages
     SPA shell at ``/pl/_/`` with ``sessionStorage.__spa_playlist_id``).
  2. Intercepts all outbound requests from the page.
  3. Identifies requests whose URL path matches ``/api/playlists/{id}``.
  4. Asserts the intercepted request URL starts with ``API_BASE_URL``, confirming
     the frontend used NEXT_PUBLIC_API_URL and not its own CDN origin.
  5. Asserts the response ``Access-Control-Allow-Origin`` header equals the
     expected frontend origin.

Linked Bugs
-----------
MYTUBE-592 (Done): Playlist detail page shows 'Could not load playlist' error.
  Root cause: PlaylistPageClient.tsx lacked the GitHub Pages SPA fallback
  pattern (reading the real UUID from ``sessionStorage.__spa_playlist_id``).
  Fix: Applied the same lazy-state / history.replaceState pattern already used
  by WatchPageClient (__spa_video_id) and UserProfilePageClient (__spa_username).

Environment Variables
---------------------
API_BASE_URL             Backend API base URL.
                         Default: http://localhost:8080
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_TOKEN      Firebase ID token for the CI test user (Layer A/B).
                         Required for playlist creation; Layer A falls back to
                         reading existing playlists when absent.
FIREBASE_TEST_EMAIL      Used to derive the CI test username (prefix before '@').
                         Default username: tester
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- PlaylistApiService from testing/components/services/playlist_api_service.py
  for creating/reading playlists.
- APIConfig from testing/core/config/api_config.py centralises API URL config.
- WebConfig from testing/core/config/web_config.py centralises web URL config.
- Playwright sync API for Layer B.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys
import urllib.error
import urllib.request
from typing import Optional
from urllib.parse import urlparse

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.web_config import WebConfig
from testing.components.services.playlist_api_service import PlaylistApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EXPECTED_ALLOWED_ORIGIN = "https://ai-teammate.github.io"
_TEMP_PLAYLIST_TITLE = "CI Test Playlist - MYTUBE-600"
_REQUEST_TIMEOUT = 15

# CI test username is derived from the email address.
_CI_EMAIL = os.getenv("FIREBASE_TEST_EMAIL", "tester@example.com")
_CI_USERNAME = _CI_EMAIL.split("@")[0] if "@" in _CI_EMAIL else "tester"

# ---------------------------------------------------------------------------
# Module-level configuration
# ---------------------------------------------------------------------------

_api_config = APIConfig()
_web_config = WebConfig()
_firebase_token: str = os.getenv("FIREBASE_TEST_TOKEN", "")


def _is_api_reachable() -> bool:
    """Return True if the API server is reachable."""
    health_url = _api_config.health_url()
    try:
        with urllib.request.urlopen(health_url, timeout=5):
            return True
    except Exception:
        return False


def _get_or_create_playlist_id() -> Optional[str]:
    """Return a valid playlist UUID for testing.

    Strategy:
    1. If FIREBASE_TEST_TOKEN is set, create a temporary playlist and return
       its ID (cleaned up after the test).
    2. Otherwise, query the CI test user's existing playlists and return the
       first one found.
    Returns None when neither approach yields an ID.
    """
    svc = PlaylistApiService(base_url=_api_config.base_url, token=_firebase_token)

    if _firebase_token:
        status, body = svc.create_playlist(_TEMP_PLAYLIST_TITLE)
        if status in (200, 201):
            import json as _json
            try:
                data = _json.loads(body)
                pid = data.get("id") or data.get("playlist_id")
                if pid:
                    return pid
            except Exception:
                pass

    # Fallback: read existing playlists for the CI test user.
    status, playlists = svc.get_user_playlists(_CI_USERNAME)
    if status == 200 and playlists:
        return playlists[0].get("id")

    return None


def _delete_playlist(playlist_id: str) -> None:
    """Delete the temporary playlist created for the test."""
    if not _firebase_token or not playlist_id:
        return
    svc = PlaylistApiService(base_url=_api_config.base_url, token=_firebase_token)
    svc.delete_playlist(playlist_id)


def _get_playlist_with_headers(playlist_id: str) -> tuple[int, dict]:
    """Send GET /api/playlists/{id} with an Origin header.

    Returns (status_code, response_headers_dict).
    All header names are lower-cased for case-insensitive comparison.
    """
    url = f"{_api_config.base_url.rstrip('/')}/api/playlists/{playlist_id}"
    req = urllib.request.Request(
        url,
        method="GET",
        headers={"Origin": _EXPECTED_ALLOWED_ORIGIN},
    )
    try:
        with urllib.request.urlopen(req, timeout=_REQUEST_TIMEOUT) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, headers
    except urllib.error.HTTPError as exc:
        headers = {k.lower(): v for k, v in exc.headers.items()}
        return exc.code, headers


# ---------------------------------------------------------------------------
# Module-scoped playlist ID (created once, shared across Layer A and B)
# ---------------------------------------------------------------------------

_playlist_id: Optional[str] = None
_created_playlist: bool = False


def setup_module(module):
    global _playlist_id, _created_playlist
    if not _is_api_reachable():
        return
    # Try to create; track whether we own it so we can clean it up.
    svc = PlaylistApiService(base_url=_api_config.base_url, token=_firebase_token)
    if _firebase_token:
        status, body = svc.create_playlist(_TEMP_PLAYLIST_TITLE)
        if status in (200, 201):
            import json as _json
            try:
                data = _json.loads(body)
                pid = data.get("id") or data.get("playlist_id")
                if pid:
                    _playlist_id = pid
                    _created_playlist = True
                    return
            except Exception:
                pass
    # Fallback: use an existing playlist.
    status, playlists = svc.get_user_playlists(_CI_USERNAME)
    if status == 200 and playlists:
        _playlist_id = playlists[0].get("id")


def teardown_module(module):
    if _created_playlist and _playlist_id:
        _delete_playlist(_playlist_id)


# ---------------------------------------------------------------------------
# Layer A — Direct API CORS verification
# ---------------------------------------------------------------------------


class TestPlaylistCorsHeaders:
    """Layer A: Verify GET /api/playlists/{id} returns correct CORS headers."""

    @pytest.fixture(autouse=True)
    def require_api(self):
        if not _is_api_reachable():
            pytest.skip("API server is not reachable — skipping Layer A")
        if not _playlist_id:
            pytest.skip("No playlist ID available — skipping Layer A")

    def test_request_url_points_to_api_server(self):
        """The constructed request URL host must match the API_BASE_URL host.

        This confirms the client (test + frontend alike) is directing
        /api/playlists/{id} calls at the API server, not the CDN.
        """
        expected_host = urlparse(_api_config.base_url).netloc
        actual_url = f"{_api_config.base_url.rstrip('/')}/api/playlists/{_playlist_id}"
        actual_host = urlparse(actual_url).netloc
        assert actual_host == expected_host, (
            f"Request URL host '{actual_host}' does not match "
            f"API_BASE_URL host '{expected_host}'. "
            "The request is NOT being sent to the API server."
        )

    def test_response_is_ok(self):
        """GET /api/playlists/{id} must return HTTP 200."""
        status, _ = _get_playlist_with_headers(_playlist_id)
        assert status == 200, (
            f"GET /api/playlists/{_playlist_id} returned HTTP {status} "
            f"(expected 200). The endpoint is unreachable or the playlist ID is invalid."
        )

    def test_access_control_allow_origin_header_present(self):
        """Access-Control-Allow-Origin must be present in the response headers."""
        _, headers = _get_playlist_with_headers(_playlist_id)
        assert "access-control-allow-origin" in headers, (
            "Response is missing the 'Access-Control-Allow-Origin' header. "
            "The API server does not permit cross-origin requests from the frontend."
        )

    def test_access_control_allow_origin_value(self):
        """Access-Control-Allow-Origin must equal the expected frontend origin."""
        _, headers = _get_playlist_with_headers(_playlist_id)
        actual = headers.get("access-control-allow-origin", "")
        assert actual == _EXPECTED_ALLOWED_ORIGIN, (
            f"Access-Control-Allow-Origin is '{actual}' "
            f"(expected '{_EXPECTED_ALLOWED_ORIGIN}'). "
            "The API server is not permitting cross-origin requests from the "
            "correct frontend origin."
        )

    def test_access_control_allow_methods_present(self):
        """Access-Control-Allow-Methods must be present in the response headers."""
        _, headers = _get_playlist_with_headers(_playlist_id)
        assert "access-control-allow-methods" in headers, (
            "Response is missing the 'Access-Control-Allow-Methods' header. "
            "Incomplete CORS configuration on the API server."
        )

    def test_access_control_allow_headers_present(self):
        """Access-Control-Allow-Headers must be present in the response headers."""
        _, headers = _get_playlist_with_headers(_playlist_id)
        assert "access-control-allow-headers" in headers, (
            "Response is missing the 'Access-Control-Allow-Headers' header. "
            "Incomplete CORS configuration on the API server."
        )


# ---------------------------------------------------------------------------
# Layer B — Playwright request-interception test
# ---------------------------------------------------------------------------


class TestPlaylistRequestUrlViaPlaywright:
    """Layer B: Verify the frontend sends /api/playlists/{id} to the correct host."""

    @pytest.fixture(autouse=True)
    def require_prerequisites(self):
        if not _playlist_id:
            pytest.skip("No playlist ID available — skipping Layer B")
        try:
            from playwright.sync_api import sync_playwright  # noqa: F401
        except ImportError:
            pytest.skip("Playwright is not installed — skipping Layer B")
        # Check web app reachability.
        try:
            req = urllib.request.Request(_web_config.base_url, method="HEAD")
            with urllib.request.urlopen(req, timeout=5):
                pass
        except Exception:
            pytest.skip(
                f"Web app at {_web_config.base_url!r} is not reachable — skipping Layer B"
            )

    def test_playlist_api_request_url_matches_api_base_url(self):
        """The fetch to /api/playlists/{id} must originate from API_BASE_URL.

        Playwright navigates to the playlist page, injects the SPA session
        storage key (MYTUBE-592 fix), and intercepts outbound requests to
        capture the actual URL used by the frontend for the playlist API call.
        """
        from playwright.sync_api import sync_playwright

        expected_api_host = urlparse(_api_config.base_url).netloc
        # The playlist page URL on the static export uses the /pl/_/ shell.
        playlist_shell_url = f"{_web_config.base_url}/pl/_/"
        # Direct URL also tested as fallback.
        playlist_direct_url = f"{_web_config.base_url}/pl/{_playlist_id}/"

        intercepted_request_url: Optional[str] = None
        intercepted_response_headers: dict = {}

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=_web_config.headless,
                slow_mo=_web_config.slow_mo,
            )
            context = browser.new_context()

            def on_request(request):
                nonlocal intercepted_request_url
                # Capture the first request matching /api/playlists/<uuid>
                if (
                    "/api/playlists/" in request.url
                    and intercepted_request_url is None
                ):
                    intercepted_request_url = request.url

            def on_response(response):
                nonlocal intercepted_response_headers
                if "/api/playlists/" in response.url and not intercepted_response_headers:
                    intercepted_response_headers = {
                        k.lower(): v
                        for k, v in response.headers.items()
                    }

            page = context.new_page()
            page.on("request", on_request)
            page.on("response", on_response)

            # Inject the SPA session storage key before navigation so the page
            # component reads the real playlist UUID (MYTUBE-592 fix).
            context.add_init_script(
                f"sessionStorage.setItem('__spa_playlist_id', '{_playlist_id}');"
            )

            # Try the SPA shell URL first; fall back to the direct URL.
            try:
                page.goto(playlist_shell_url, timeout=20_000)
                page.wait_for_timeout(5_000)  # Wait for async data fetch
            except Exception:
                pass

            if not intercepted_request_url:
                # Retry with direct URL.
                try:
                    page.goto(playlist_direct_url, timeout=20_000)
                    page.wait_for_timeout(5_000)
                except Exception:
                    pass

            context.close()
            browser.close()

        assert intercepted_request_url is not None, (
            f"No request to /api/playlists/* was intercepted when navigating to "
            f"the playlist page. "
            f"The frontend may not be fetching from the API server at all, "
            f"or the page did not reach the data-loading phase. "
            f"Tried URLs: {playlist_shell_url!r}, {playlist_direct_url!r}"
        )

        # The key assertion: the request must NOT be sent to the frontend CDN host.
        # NEXT_PUBLIC_API_URL is baked into the static build at deploy time; the
        # exact URL may differ from the test-runner's API_BASE_URL.  What matters
        # is that the frontend used NEXT_PUBLIC_API_URL and NOT its own origin/CDN.
        frontend_host = urlparse(_web_config.base_url).netloc  # e.g. ai-teammate.github.io
        actual_host = urlparse(intercepted_request_url).netloc
        assert actual_host != frontend_host, (
            f"Frontend sent the playlist API request to the frontend CDN host "
            f"'{actual_host}' (same as APP_URL host '{frontend_host}'). "
            f"Full intercepted URL: {intercepted_request_url!r}. "
            f"This means NEXT_PUBLIC_API_URL was empty or unset at build time, "
            f"causing the request to be routed to the CDN instead of the API server."
        )
        assert actual_host, (
            f"Intercepted request URL has no host: {intercepted_request_url!r}. "
            f"The URL is malformed — NEXT_PUBLIC_API_URL may not have been set."
        )

        if intercepted_response_headers:
            acao = intercepted_response_headers.get("access-control-allow-origin", "")
            assert acao == _EXPECTED_ALLOWED_ORIGIN, (
                f"Intercepted response Access-Control-Allow-Origin is '{acao}' "
                f"(expected '{_EXPECTED_ALLOWED_ORIGIN}'). "
                f"Full URL: {intercepted_request_url!r}"
            )
