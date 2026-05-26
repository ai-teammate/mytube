"""
MYTUBE-633: Upload valid avatar image — URL updated and success message shown.

Objective
---------
Verify that selecting a valid JPEG/PNG file and clicking "Upload" correctly:
  * Triggers a POST request to /api/me/avatar with multipart/form-data.
  * On success, populates the "Avatar URL" text field with the returned URL.
  * Displays a brief success notification ("Avatar uploaded successfully.").
  * Updates the existing avatar preview to show the new image.

Preconditions
-------------
User is on the Account Settings page (/settings).

Test steps
----------
1. Log in with a valid Firebase test account.
2. Navigate to /settings.
3. Select a valid JPEG file (< 5 MB) using the file input control.
4. Verify the Upload button becomes enabled once a file is selected.
5. Click the "Upload" button.
6. Assert the success message "Avatar uploaded successfully." is displayed.
7. Assert the "Avatar URL" field is populated with the URL returned by the API.
8. Assert the avatar preview image is visible and has the new URL as its src.

Architecture
------------
- Playwright sync API via pytest module-scoped fixtures.
- LoginPage, SettingsPage: page-object wrappers for all DOM interactions.
- WebConfig: centralises env var access (APP_URL, FIREBASE_TEST_EMAIL, etc.).
- Route interception:
    * GET /api/me → returns a stable empty-avatar profile (prevents side-effects).
    * POST /api/me/avatar → returns a mocked 200 with avatar_url (isolates from live GCS).
    * The returned CDN URL is also intercepted to serve a valid 1×1 GIF (prevents
      onError in AvatarPreview).

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Test user email (required — test skips when absent).
FIREBASE_TEST_PASSWORD   Test user password (required — test skips when absent).
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-633/test_mytube_633.py -v
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys
import tempfile

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Route, Request, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_LOGIN_TIMEOUT = 20_000        # ms — max time to wait for post-login redirect
_UPLOAD_TIMEOUT = 10_000       # ms — max time to wait for success message

# Mocked avatar URL returned by the intercepted POST /api/me/avatar handler.
_MOCK_AVATAR_URL = "https://cdn.test.example.com/mytube-633/avatars/test-user.jpg"

# Stable profile returned by GET /api/me (no avatar initially).
_STABLE_PROFILE_JSON: bytes = json.dumps(
    {"username": "testuser633", "avatar_url": None}
).encode()

# Regex matching any /api/me URL (covers any origin prefix the app uses).
_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")

# Regex matching /api/me/avatar  (POST endpoint for avatar upload).
_API_ME_AVATAR_PATTERN = re.compile(r"/api/me/avatar")

# Regex for the mocked CDN URL — we serve a valid GIF to prevent onError.
_MOCK_CDN_PATTERN = re.compile(r"mytube-633")

# Minimal valid 1×1 transparent GIF (35 bytes).
_GIF_1X1 = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

# Minimal valid 1×1 white JPEG (standard test image).
_MINIMAL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDB"
    "kSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAAR"
    "CAABAAEDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAIxAAAQME"
    "AgMBAAAAAAAAAAAAAQIDAAQFESExQVFh/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/E"
    "ABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AJmk2pa3pVoiu3CqNOmT"
    "UoSVJDSwFKA9yBvXisWtd2vMiTHt8B2Q3GdLTi0DYSobBH3rF0/wBwAAD/2Q=="
)
_JPEG_BYTES = base64.b64decode(_MINIMAL_JPEG_B64)


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _api_me_route_handler(route: Route, request: Request) -> None:
    """Intercept /api/me requests.

    * GET  → return stable empty-avatar profile to prevent form state changes.
    * POST (avatar upload) → pass through; handled by _api_me_avatar_route_handler.
    * PUT  → pass through (save settings should not be triggered in this test).
    """
    if request.method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_STABLE_PROFILE_JSON,
        )
    else:
        route.continue_()


def _api_me_avatar_route_handler(route: Route, request: Request) -> None:
    """Intercept POST /api/me/avatar and return a mocked success response."""
    if request.method == "POST":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"avatar_url": _MOCK_AVATAR_URL}).encode(),
        )
    else:
        route.continue_()


def _cdn_image_route_handler(route: Route, request: Request) -> None:
    """Serve a valid 1×1 GIF for the mocked CDN avatar URL.

    This prevents the AvatarPreview <img> onError handler from firing and
    switching the component to its SVG fallback state — ensuring the avatar
    image is actually shown after a successful upload.
    """
    route.fulfill(
        status=200,
        content_type="image/gif",
        body=_GIF_1X1,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_url(config: WebConfig) -> str:
    return f"{config.base_url}/settings/"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig) -> None:
    """Skip the entire module when Firebase test credentials are not provided."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping avatar upload UI test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping avatar upload UI test. "
            "Set FIREBASE_TEST_PASSWORD to run this test."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def tmp_jpeg_file() -> str:
    """Write a minimal JPEG to a temporary file and return its path."""
    fd, path = tempfile.mkstemp(suffix=".jpg", prefix="mytube_633_avatar_")
    try:
        os.write(fd, _JPEG_BYTES)
        os.close(fd)
        yield path
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


@pytest.fixture(scope="module")
def authenticated_settings_page(
    browser: Browser, web_config: WebConfig
) -> dict:
    """
    Log in, navigate to /settings, install route interceptors, and yield
    ``{page, settings_page}`` for all tests in the module.

    Route interceptors installed:
    * GET  /api/me            → stable empty-avatar profile JSON.
    * POST /api/me/avatar     → mocked 200 with _MOCK_AVATAR_URL.
    * Any URL containing "mytube-633" → valid 1×1 GIF (prevents onError).
    """
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Route: intercept /api/me (GET → stable profile; others pass through).
    page.route(_API_ME_PATTERN, _api_me_route_handler)

    # Route: intercept POST /api/me/avatar → mocked success.
    # This must be registered BEFORE the broader /api/me pattern so it matches first.
    page.route(_API_ME_AVATAR_PATTERN, _api_me_avatar_route_handler)

    # Route: intercept the mocked CDN image URL → serve valid GIF.
    page.route(_MOCK_CDN_PATTERN, _cdn_image_route_handler)

    # Log in.
    login_pg = LoginPage(page)
    login_pg.navigate(web_config.login_url())
    login_pg.login_as(web_config.test_email, web_config.test_password)
    login_pg.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

    # Navigate to /settings.
    settings_pg = SettingsPage(page)
    settings_pg.navigate(_settings_url(web_config))

    yield {"page": page, "settings_page": settings_pg}

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarUploadSuccess:
    """MYTUBE-633: Upload valid avatar image — URL updated and success message shown."""

    def test_upload_button_disabled_before_file_selected(
        self, authenticated_settings_page: dict
    ) -> None:
        """Upload button must be disabled when no file is selected."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        assert not settings_pg.is_upload_button_enabled(), (
            "Upload button should be disabled before a file is selected. "
            "The button should only become enabled once a valid file is chosen."
        )

    def test_upload_button_enabled_after_file_selected(
        self, authenticated_settings_page: dict, tmp_jpeg_file: str
    ) -> None:
        """Upload button must be enabled once a valid JPEG file is selected."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        settings_pg.select_avatar_file(tmp_jpeg_file)

        assert settings_pg.is_upload_button_enabled(), (
            "Upload button did not become enabled after selecting a valid JPEG file. "
            f"File path used: {tmp_jpeg_file!r}. "
            "Check that the file input's onChange handler is updating the uploadFile state."
        )

    def test_upload_shows_success_message(
        self, authenticated_settings_page: dict
    ) -> None:
        """Clicking Upload must display 'Avatar uploaded successfully.' status message."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        settings_pg.click_upload_button()

        success = settings_pg.wait_for_upload_success_message(timeout=_UPLOAD_TIMEOUT)
        assert success, (
            "The success message 'Avatar uploaded successfully.' was not displayed "
            f"within {_UPLOAD_TIMEOUT} ms after clicking Upload. "
            "Expected: p[role='status'] containing 'Avatar uploaded successfully.' "
            "Actual: message not found. "
            "Check that handleAvatarUpload sets uploadSuccess=true on a 200 response."
        )

    def test_avatar_url_field_populated_with_returned_url(
        self, authenticated_settings_page: dict
    ) -> None:
        """The Avatar URL text field must be populated with the URL returned by the API."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        actual_url = settings_pg.get_avatar_url_input_value()
        assert actual_url == _MOCK_AVATAR_URL, (
            f"Avatar URL field not populated with the returned URL after upload. "
            f"Expected: {_MOCK_AVATAR_URL!r}, "
            f"Got: {actual_url!r}. "
            "Check that handleAvatarUpload calls setForm to update avatarUrl with "
            "data.avatar_url from the API response."
        )

    def test_avatar_preview_visible_after_upload(
        self, authenticated_settings_page: dict
    ) -> None:
        """The avatar preview must be visible and show the newly uploaded image."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        assert settings_pg.is_avatar_preview_container_visible(timeout=8_000), (
            "Avatar preview container (role='img') not visible after successful upload. "
            "Expected the AvatarPreview component to render when avatarUrl is set."
        )

        actual_src = settings_pg.wait_for_avatar_img_src(_MOCK_AVATAR_URL, timeout=8_000)
        assert actual_src == _MOCK_AVATAR_URL, (
            f"Avatar preview img src does not match the uploaded URL. "
            f"Expected src: {_MOCK_AVATAR_URL!r}, "
            f"Got: {actual_src!r}. "
            "The AvatarPreview component should receive the new avatarUrl as its src prop."
        )
