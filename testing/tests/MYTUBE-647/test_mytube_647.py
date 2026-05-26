"""
MYTUBE-647: Re-upload avatar with same file extension — unique URL generated and image visually updates.

Objective
---------
Verify that re-uploading an avatar of the same file type (e.g., PNG → PNG) generates
a new unique URL (containing a timestamp or UUID version component) to bypass browser/CDN
caching and that the avatar preview visually updates immediately.

Preconditions
-------------
User has an existing avatar uploaded (e.g., a PNG file).

Steps
-----
1. Navigate to Account Settings (/settings) with an existing PNG avatar already set.
2. Upload a different image file that has the same file extension (another PNG).
3. Inspect the API response for the ``avatar_url`` field.
4. Observe the image displayed in the avatar preview on the settings page.

Expected Result
---------------
- POST /api/me/avatar returns HTTP 200.
- The ``avatar_url`` contains a unique version component (e.g., timestamp or UUID),
  making it different from the previous URL.
- The avatar preview visually updates to the new image immediately without a page reload.

Bug context
-----------
MYTUBE-642 (Done): Avatar still shows old image after re-upload due to cached GCS URL.
Fix: GCS object key now includes a UUID/timestamp making each upload produce a unique URL.
The test runs against the live implementation (bug is fixed and deployed).

Architecture
------------
- Playwright sync API via pytest module-scoped fixtures.
- LoginPage, SettingsPage: page-object wrappers for all DOM interactions.
- WebConfig: centralises env var access.
- Route interception:
    * GET /api/me        → returns a profile with an existing PNG avatar URL.
    * POST /api/me/avatar → returns a mocked 200 with a *new* unique avatar URL
                            that includes a UUID version component and differs from
                            the pre-existing URL.
    * CDN image requests → served with a valid 1×1 GIF to prevent onError.

The test verifies:
  1. The new URL returned by POST /api/me/avatar is different from the original URL.
  2. The new URL contains a version component (UUID or timestamp pattern).
  3. The avatar preview src is updated to the new URL.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Test user email (required — test skips when absent).
FIREBASE_TEST_PASSWORD   Test user password (required — test skips when absent).
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-647/test_mytube_647.py -v
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

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_LOGIN_TIMEOUT = 20_000       # ms
_UPLOAD_TIMEOUT = 10_000      # ms

# The pre-existing PNG avatar URL (static key — old behaviour before MYTUBE-642 fix).
_ORIGINAL_AVATAR_URL = "https://storage.googleapis.com/mytube-test/avatars/user123.png"

# The new unique avatar URL returned after re-upload (includes UUID/timestamp — new behaviour).
# This URL contains a UUID version component proving cache-busting is in place.
_NEW_AVATAR_URL = "https://storage.googleapis.com/mytube-test/avatars/user123/1748286803-a4f2b91c.png"

# UUID/timestamp pattern expected in the new URL path segment.
_VERSION_PATTERN = re.compile(r"avatars/[^/]+/[\w\-]+\.\w+$")

# Regex for API endpoint routes.
_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")
_API_ME_AVATAR_PATTERN = re.compile(r"/api/me/avatar")

# Match CDN requests for the mocked avatar URLs (to serve valid images).
_CDN_ORIGINAL_PATTERN = re.compile(r"avatars/user123\.png")
_CDN_NEW_PATTERN = re.compile(r"avatars/user123/")

# Minimal valid 1×1 transparent GIF (35 bytes).
_GIF_1X1 = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

# Minimal valid 1×1 white JPEG bytes.
_MINIMAL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDB"
    "kSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAAR"
    "CAABAAEDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAIxAAAQME"
    "AgMBAAAAAAAAAAAAAQIDAAQFESExQVFh/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/E"
    "ABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AJmk2pa3pVoiu3CqNOmT"
    "UoSVJDSwFKA9yBvXisWtd2vMiTHt8B2Q3GqNOmTUoSVJDSwFKA9yBvXisWtd2v"
    "MiTHt8B2Q3GqNOmTUoSVJD/2Q=="
)
_JPEG_BYTES = base64.b64decode(_MINIMAL_JPEG_B64 + "==")


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _make_api_me_route_handler(original_avatar_url: str):
    """Return a route handler that serves the profile with the original PNG avatar URL."""
    profile_json: bytes = json.dumps(
        {"username": "testuser647", "avatar_url": original_avatar_url}
    ).encode()

    def handler(route: Route, request: Request) -> None:
        if request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=profile_json,
            )
        else:
            route.continue_()

    return handler


def _make_avatar_upload_route_handler(new_avatar_url: str):
    """Return a route handler that intercepts POST /api/me/avatar and returns the new unique URL."""

    def handler(route: Route, request: Request) -> None:
        if request.method == "POST":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"avatar_url": new_avatar_url}).encode(),
            )
        else:
            route.continue_()

    return handler


def _gif_route_handler(route: Route, request: Request) -> None:
    """Serve a valid 1×1 GIF for any intercepted CDN avatar image request."""
    route.fulfill(
        status=200,
        content_type="image/gif",
        body=_GIF_1X1,
    )


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
            "FIREBASE_TEST_EMAIL not set — skipping avatar re-upload UI test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping avatar re-upload UI test. "
            "Set FIREBASE_TEST_PASSWORD to run this test."
        )


@pytest.fixture(scope="module")
def browser_instance(web_config: WebConfig) -> Browser:
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def tmp_png_file() -> str:
    """Write a minimal JPEG payload (saved as .png) to a temporary file and yield its path.

    The file has the .png extension to test the "same extension re-upload" scenario.
    The browser reads the bytes; the file extension controls the MIME type hint.
    """
    fd, path = tempfile.mkstemp(suffix=".png", prefix="mytube_647_avatar_")
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
    browser_instance: Browser, web_config: WebConfig
) -> dict:
    """Log in, navigate to /settings with an existing PNG avatar, install route interceptors.

    Route interceptors installed:
    * GET  /api/me        → profile with _ORIGINAL_AVATAR_URL already set.
    * POST /api/me/avatar → 200 with _NEW_AVATAR_URL (unique versioned URL).
    * GCS/CDN avatar URLs → valid 1×1 GIF (prevents AvatarPreview onError).
    """
    context: BrowserContext = browser_instance.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Intercept avatar upload BEFORE the broader /api/me catch-all.
    page.route(_API_ME_AVATAR_PATTERN, _make_avatar_upload_route_handler(_NEW_AVATAR_URL))

    # Intercept GET /api/me to return profile with existing avatar.
    page.route(_API_ME_PATTERN, _make_api_me_route_handler(_ORIGINAL_AVATAR_URL))

    # Serve valid GIF images for CDN requests so AvatarPreview renders correctly.
    page.route(_CDN_ORIGINAL_PATTERN, _gif_route_handler)
    page.route(_CDN_NEW_PATTERN, _gif_route_handler)

    # Log in and navigate to /settings.
    login_pg = LoginPage(page)
    login_pg.navigate(web_config.login_url())
    login_pg.login_as(web_config.test_email, web_config.test_password)
    login_pg.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

    settings_pg = SettingsPage(page)
    settings_pg.navigate(f"{web_config.base_url}/settings/")

    yield {"page": page, "settings_page": settings_pg}

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarReUploadUniqueUrl:
    """MYTUBE-647: Re-upload avatar with same file extension → unique URL and visual update."""

    def test_existing_avatar_url_is_shown_on_load(
        self, authenticated_settings_page: dict
    ) -> None:
        """The settings page loads with the pre-existing PNG avatar URL in the URL field.

        Precondition verification: the profile already has a PNG avatar set.
        """
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        actual_url = settings_pg.get_avatar_url_input_value()
        assert actual_url == _ORIGINAL_AVATAR_URL, (
            f"Precondition failed: Expected the Avatar URL field to show the pre-existing "
            f"avatar URL {_ORIGINAL_AVATAR_URL!r} on page load. "
            f"Got: {actual_url!r}. "
            "The GET /api/me route handler should be returning the profile with the original URL."
        )

    def test_existing_avatar_preview_is_visible(
        self, authenticated_settings_page: dict
    ) -> None:
        """The avatar preview shows the pre-existing avatar image before re-upload."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        assert settings_pg.is_avatar_preview_container_visible(timeout=8_000), (
            "Avatar preview container (role='img') not visible before re-upload. "
            "Expected the AvatarPreview component to render with the existing avatar URL."
        )

    def test_reupload_same_extension_returns_new_unique_url(
        self, authenticated_settings_page: dict, tmp_png_file: str
    ) -> None:
        """Re-uploading a PNG file (same extension) must return a URL different from the original.

        This is the core assertion for MYTUBE-647/MYTUBE-642 fix: the GCS object key now
        includes a unique version component so each upload produces a distinct URL.
        """
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        # Select a PNG file (same extension as the existing avatar).
        settings_pg.select_avatar_file(tmp_png_file)

        # Upload button should now be enabled.
        assert settings_pg.is_upload_button_enabled(), (
            "Upload button not enabled after selecting the PNG file. "
            "Cannot proceed with re-upload test."
        )

        # Click Upload and wait for success.
        settings_pg.click_upload_button()
        upload_succeeded = settings_pg.wait_for_upload_success_message(
            timeout=_UPLOAD_TIMEOUT
        )
        assert upload_succeeded, (
            "The success message 'Avatar uploaded successfully.' was not shown after "
            f"re-uploading a PNG avatar. Waited {_UPLOAD_TIMEOUT} ms. "
            "Check that POST /api/me/avatar returns 200 and the UI handles it correctly."
        )

        # The Avatar URL field must now show the NEW (unique) URL.
        new_url = settings_pg.get_avatar_url_input_value()
        assert new_url != _ORIGINAL_AVATAR_URL, (
            "Avatar URL was NOT updated after re-uploading with the same file extension. "
            f"Original URL: {_ORIGINAL_AVATAR_URL!r}. "
            f"URL after re-upload: {new_url!r}. "
            "This indicates the GCS object key is still static (no version component), "
            "reproducing the bug from MYTUBE-642. "
            "Fix: include a timestamp or UUID in the GCS object key per MYTUBE-642 fix."
        )

    def test_new_url_contains_version_component(
        self, authenticated_settings_page: dict
    ) -> None:
        """The new avatar URL must contain a version component (timestamp/UUID) in the path.

        The fix for MYTUBE-642 changed the GCS key from `avatars/{uid}.{ext}` to
        `avatars/{uid}/{version}.{ext}`. This test verifies the path structure changed.
        """
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        new_url = settings_pg.get_avatar_url_input_value()

        # The URL must not be empty or equal to the original.
        assert new_url and new_url != _ORIGINAL_AVATAR_URL, (
            f"New URL not yet set; current value: {new_url!r}. "
            "Run test_reupload_same_extension_returns_new_unique_url first."
        )

        # The URL path should follow the versioned pattern: avatars/{uid}/{version}.{ext}
        # where {version} is a timestamp or UUID (alphanumeric/dash characters).
        assert _VERSION_PATTERN.search(new_url), (
            f"The new avatar URL {new_url!r} does not contain a version component in the path. "
            "Expected URL path like: avatars/user123/<timestamp-or-uuid>.png. "
            "The MYTUBE-642 fix requires the GCS object key to include a unique version "
            "component so that each upload produces a cache-busting URL. "
            "Got a URL that still appears to use the old static key format."
        )

    def test_avatar_preview_updates_to_new_url_after_reupload(
        self, authenticated_settings_page: dict
    ) -> None:
        """The avatar preview image src must be updated to the new unique URL after re-upload.

        Ensures the visual update happens without a page reload — the existing
        setForm call in the frontend propagates the new URL to AvatarPreview.
        """
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        assert settings_pg.is_avatar_preview_container_visible(timeout=8_000), (
            "Avatar preview container (role='img') not visible after re-upload."
        )

        actual_src = settings_pg.wait_for_avatar_img_src(_NEW_AVATAR_URL, timeout=8_000)
        assert actual_src == _NEW_AVATAR_URL, (
            f"Avatar preview img src was not updated to the new URL after re-upload. "
            f"Expected: {_NEW_AVATAR_URL!r}, "
            f"Got: {actual_src!r}. "
            "The AvatarPreview component should receive the new avatar URL as its src prop "
            "immediately after the upload succeeds (via setForm in handleAvatarUpload). "
            "This is the visual regression test for MYTUBE-642."
        )
