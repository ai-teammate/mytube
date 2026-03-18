"""
MYTUBE-598: Access playlist detail page with invalid UUID format —
system returns 400 error and handles it gracefully.

Objective
---------
Verify that the backend UUID validation prevents the application from entering
a failed state when provided with malformed IDs.

Steps
-----
1. Log in as an authenticated user.
2. Navigate to a URL with a malformed ID: /pl/not-a-valid-uuid-123.
3. Observe the network response for the API call and the UI error message.

Expected Result
---------------
The API request to GET /api/playlists/not-a-valid-uuid-123 returns a 400 Bad
Request status.  The UI should display a specific error or a 404 message rather
than a generic connection failure error.

Architecture
------------
- PlaylistApiService: direct HTTP call to verify 400 status for invalid UUID.
- Playwright web test: navigate with a logged-in user, intercept the API
  response, and verify the UI does not display a generic connection failure.
- WebConfig / APIConfig: centralised environment variable access.
- LoginPage: handles authentication in the browser.
- PlaylistPage: page-object wrapper for /pl/:id assertions.

Environment variables
---------------------
APP_URL / WEB_BASE_URL    Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
API_BASE_URL              Deployed API base URL.
                          Default: https://mytube-api-80693608388.us-central1.run.app
FIREBASE_TEST_EMAIL       Test user email.
FIREBASE_TEST_PASSWORD    Test user password.
PLAYWRIGHT_HEADLESS       Run headless (default: true).
PLAYWRIGHT_SLOW_MO        Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-598/test_mytube_598.py -v
"""
from __future__ import annotations

import os
import sys
import urllib.request

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.playlist_page.playlist_page import PlaylistPage
from testing.components.services.playlist_api_service import PlaylistApiService
from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_INVALID_UUID = "not-a-valid-uuid-123"

_GENERIC_FAILURE_TEXT = "Could not load playlist"

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_POST_NAV_SETTLE = 3_000     # ms — wait for SPA redirect + React hydration


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_reachable(url: str, timeout: int = 10) -> bool:
    try:
        resp = urllib.request.urlopen(url, timeout=timeout)
        return resp.status < 500
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Test class — API layer
# ---------------------------------------------------------------------------


class TestMytube598InvalidUuidApi:
    """MYTUBE-598 — Direct API: GET /api/playlists/<invalid-uuid> returns 400."""

    def test_invalid_uuid_returns_400(self, config: WebConfig) -> None:
        """
        Step 3 (API side): Call GET /api/playlists/not-a-valid-uuid-123 directly
        and assert the backend returns HTTP 400 Bad Request.

        This verifies that the isValidUUID guard in getPlaylistHandler fires
        correctly for a malformed ID and prevents the backend from executing
        a DB query against junk input.
        """
        if not _is_url_reachable(f"{config.api_base_url}/health"):
            pytest.skip(
                f"API at {config.api_base_url} is not reachable — skipping API test."
            )

        svc = PlaylistApiService(base_url=config.api_base_url)
        result = svc.get_playlist(_INVALID_UUID)

        assert result.status_code == 400, (
            f"Expected HTTP 400 for GET /api/playlists/{_INVALID_UUID} "
            f"but received HTTP {result.status_code}.\n"
            f"Response body: {result.raw_body!r}"
        )


# ---------------------------------------------------------------------------
# Test class — Web UI layer
# ---------------------------------------------------------------------------


class TestMytube598InvalidUuidUi:
    """MYTUBE-598 — Web UI: navigating to /pl/<invalid-uuid> shows a graceful error."""

    def test_invalid_uuid_ui_shows_graceful_error(self, config: WebConfig) -> None:
        """
        Steps 1–3 (UI side):
        1. Log in as an authenticated user.
        2. Navigate to /pl/not-a-valid-uuid-123.
        3. Capture the API response status code via network interception.
        4. Verify the UI does NOT display the generic connection-failure error.
        5. Verify the UI shows either 'Playlist not found.' or an error alert.

        Note on SPA routing
        -------------------
        The app is hosted on GitHub Pages as a static export.  Navigating to
        /pl/<id>/ causes GitHub Pages to serve public/404.html, which stores
        the requested path in sessionStorage and redirects to the base URL.
        The React SPA then restores the URL via history.replaceState and the
        PlaylistPageClient reads the playlist ID from sessionStorage or the
        URL.  We therefore wait for a short settle period after navigation
        to let the SPA redirect complete and the component fetch the API.
        """
        if not config.test_email or not config.test_password:
            pytest.skip(
                "FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD are not set — "
                "skipping UI test."
            )

        if not _is_url_reachable(config.base_url):
            pytest.skip(
                f"Web app at {config.base_url} is not reachable — skipping UI test."
            )

        captured_api_statuses: list[int] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=config.headless, slow_mo=config.slow_mo
            )
            context = browser.new_context()
            page = context.new_page()

            try:
                # -- Step 1: log in ---------------------------------------------------
                login_page = LoginPage(page)
                login_page.navigate(config.login_url())
                login_page.wait_for_form(timeout=_PAGE_LOAD_TIMEOUT)
                login_page.login_as(config.test_email, config.test_password)

                # Wait for redirect to home after successful login.
                try:
                    page.wait_for_url(
                        lambda u: "/login" not in u,
                        timeout=15_000,
                    )
                except Exception as exc:
                    # Timeout is acceptable if the redirect already completed,
                    # but log so flakiness is visible in CI.
                    print(f"[MYTUBE-598] wait_for_url after login timed out ({exc}); continuing.")

                # -- Step 2: navigate to invalid-UUID playlist URL --------------------
                # Intercept API responses to capture status codes.
                def _on_response(resp) -> None:
                    if f"/api/playlists/{_INVALID_UUID}" in resp.url:
                        captured_api_statuses.append(resp.status)

                page.on("response", _on_response)

                playlist_page = PlaylistPage(page)
                playlist_page.navigate(config.base_url, _INVALID_UUID)

                # Allow time for the SPA redirect chain (404.html → base → replaceState)
                # and React to hydrate + issue the API call.
                page.wait_for_timeout(_POST_NAV_SETTLE)

                # -- Step 3: assert API responded with 400 ----------------------------
                if captured_api_statuses:
                    assert 400 in captured_api_statuses, (
                        f"Expected the intercepted API call to "
                        f"GET /api/playlists/{_INVALID_UUID} to return HTTP 400, "
                        f"but received status codes: {captured_api_statuses}.\n"
                        f"The backend isValidUUID guard may not be firing correctly."
                    )
                # If no API call was captured the SPA may have short-circuited
                # before reaching the fetch (e.g., showed 404 immediately) —
                # we still assert on the UI below.

                # -- Step 4: verify the UI does NOT show the generic failure text -----
                page_text = page.evaluate("() => document.body.innerText")
                assert _GENERIC_FAILURE_TEXT not in page_text, (
                    f"The UI displayed the generic connection failure message "
                    f"'{_GENERIC_FAILURE_TEXT}' when navigating to "
                    f"/pl/{_INVALID_UUID}.\n"
                    f"Expected: 'Playlist not found.' or a specific validation error.\n"
                    f"Actual UI text (truncated):\n{page_text[:500]}"
                )

                # -- Step 5: verify the UI shows a meaningful error state -------------
                shows_not_found = playlist_page.is_not_found()
                shows_error_alert = playlist_page.is_error_displayed()

                assert shows_not_found or shows_error_alert, (
                    f"The UI did not display either 'Playlist not found.' or an "
                    f"error alert after navigating to /pl/{_INVALID_UUID}.\n"
                    f"shows_not_found={shows_not_found}, "
                    f"shows_error_alert={shows_error_alert}.\n"
                    f"Page text (truncated):\n{page_text[:500]}"
                )
            finally:
                browser.close()
