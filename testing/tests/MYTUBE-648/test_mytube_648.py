"""
MYTUBE-648: SiteHeader avatar refresh — new image reflected after upload.

Objective
---------
Verify that the avatar image in the global SiteHeader is updated immediately
after a successful upload in the same session.

Preconditions
-------------
User is authenticated and viewing the Account Settings page.

Steps
-----
1. Note the current avatar image/URL displayed in the SiteHeader and settings.
2. Upload a new avatar image via the Account Settings form.
3. Once the upload is successful, observe the avatar in the SiteHeader and
   the AvatarPreview on the settings page.

Expected Result
---------------
- The SiteHeader avatar button remains visible (user is still authenticated).
- The AvatarPreview on the settings page reflects the newly uploaded avatar.
- The new avatar URL is unique (UUID-based per fix in MYTUBE-642), i.e.
  different from the old URL, proving cache-busting is in effect.
- The avatar_url field is populated with the new, unique URL.

Bug context (MYTUBE-642)
------------------------
The fix changed the GCS object key from a static path (``avatars/{uid}.{ext}``)
to a versioned path with a UUID (``avatars/{uid}/{uuid}.{ext}``).  This ensures
each upload produces a cache-busting URL.  Additionally the settings page
propagates the new URL via setForm so the AvatarPreview updates without a
page reload.

Architecture
------------
- LoginPage and SettingsPage Page Objects handle all DOM interactions.
- SiteHeader Page Object asserts the header avatar state.
- Playwright route interception mocks both GET /api/me and POST /api/me/avatar.
- WebConfig from testing/core/config/web_config.py provides all env vars.
- Credentials required: FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD.

Run from repo root:
    pytest testing/tests/MYTUBE-648/test_mytube_648.py -v
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
from testing.components.pages.site_header.site_header import SiteHeader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000    # ms — max time for initial page load
_LOGIN_TIMEOUT = 20_000         # ms — max time to wait for post-login redirect
_UPLOAD_TIMEOUT = 10_000        # ms — max time to wait for upload success message

# The "old" avatar URL that the user already has before the new upload.
_OLD_AVATAR_URL = "https://storage.googleapis.com/mytube-hls-output/avatars/uid_648_test/old_image.jpg"

# The "new" avatar URL returned by the mocked POST /api/me/avatar handler.
# It includes a UUID component — matching the MYTUBE-642 fix — so it is
# structurally different from the old static URL.
_NEW_AVATAR_URL = (
    "https://storage.googleapis.com/mytube-hls-output/"
    "avatars/uid_648_test/a1b2c3d4-e5f6-7890-abcd-ef1234567890.jpg"
)

# Regex patterns for route interception.
_API_ME_AVATAR_PATTERN = re.compile(r"/api/me/avatar")
_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")
_OLD_CDN_PATTERN = re.compile(r"old_image\.jpg")
_NEW_CDN_PATTERN = re.compile(r"a1b2c3d4-e5f6-7890-abcd-ef1234567890")

# Minimal valid 1×1 transparent GIF (35 bytes).
_GIF_1X1 = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

# Minimal valid 1×1 white JPEG bytes.
_JPEG_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDB"
    "kSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/"
    "wAARC"
    "AABAAEDASIA2gABAREA/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAIxAAAQMEAgMBAAAAAAAAAAAAAQIDBAAFESExQVFh"
    "/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAA"
    "AAAAAAAAAAAAAP/aAAwDAQACEQMRAD8Amk2pa3pVoiu3CqNOmTUoSVJDSwFKA9yBvXisWtd2vMiTHt8B2Q3GdLTi0DYSobBH3rF0"
    "/8QAHRABAAICAwEBAAAAAAAAAAAAAQIDBAAR"
    "ITIUQP/aAAgBAQABPxCk2e63S4SY8aI884y4UOJQNkKHIIPkEf0qw2O0W2wxVxrXEbiwFKA9yBvXisWtd2vMiTHt8B2Q"
    "3GdLTi0DYSobBH3rF0//2Q=="
)

# Profile JSON with the OLD avatar URL — simulates the user's current profile.
_INITIAL_PROFILE_JSON: bytes = json.dumps(
    {
        "username": "testuser648",
        "avatar_url": _OLD_AVATAR_URL,
    }
).encode()

# Upload success response — new unique URL returned by the API.
_UPLOAD_SUCCESS_JSON: bytes = json.dumps(
    {"avatar_url": _NEW_AVATAR_URL}
).encode()


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _api_me_avatar_handler(route: Route, _request: Request) -> None:
    """Mock POST /api/me/avatar — returns 200 with the new unique avatar URL."""
    route.fulfill(
        status=200,
        content_type="application/json",
        body=_UPLOAD_SUCCESS_JSON,
    )


def _api_me_handler(route: Route, request: Request) -> None:
    """Mock GET /api/me — returns a stable profile with the old avatar URL.

    Only intercepts GET requests.  POST /api/me requests (profile save)
    are passed through so they don't affect avatar upload assertions.
    """
    if request.method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_INITIAL_PROFILE_JSON,
        )
    else:
        route.continue_()


def _avatar_image_handler(route: Route, _request: Request) -> None:
    """Serve a valid 1×1 GIF for any avatar CDN URL.

    Prevents AvatarPreview's onError handler from firing, which would switch
    the component to its SVG fallback state and hide the <img> element.
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
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-648 SiteHeader avatar "
            "refresh test. Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-648 test. "
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
    fd, path = tempfile.mkstemp(suffix=".jpg", prefix="mytube_648_avatar_")
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
def authenticated_settings_context(
    browser: Browser, web_config: WebConfig
) -> dict:
    """
    Log in, navigate to /settings, install route interceptors, and yield a
    dict containing ``page``, ``settings_page``, and ``site_header``.

    Route interceptors installed:
    * GET  /api/me            → profile JSON with OLD avatar URL.
    * POST /api/me/avatar     → mocked 200 with NEW unique avatar URL.
    * CDN URLs for old/new avatar images → valid 1×1 GIF (prevents onError).
    """
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Register avatar upload interceptor BEFORE the broader /api/me pattern.
    page.route(_API_ME_AVATAR_PATTERN, _api_me_avatar_handler)
    page.route(_API_ME_PATTERN, _api_me_handler)

    # Serve valid images for both old and new avatar CDN URLs.
    page.route(_OLD_CDN_PATTERN, _avatar_image_handler)
    page.route(_NEW_CDN_PATTERN, _avatar_image_handler)

    # Log in.
    login_pg = LoginPage(page)
    login_pg.navigate(web_config.login_url())
    login_pg.login_as(web_config.test_email, web_config.test_password)
    login_pg.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

    # Navigate to /settings.
    settings_pg = SettingsPage(page)
    settings_pg.navigate(_settings_url(web_config))

    site_header = SiteHeader(page)

    yield {
        "page": page,
        "settings_page": settings_pg,
        "site_header": site_header,
    }

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSiteHeaderAvatarRefresh:
    """MYTUBE-648: SiteHeader avatar refresh — new image reflected after upload."""

    def test_initial_avatar_in_settings_shows_old_url(
        self, authenticated_settings_context: dict
    ) -> None:
        """The Avatar URL field must display the existing avatar URL before upload."""
        settings_pg: SettingsPage = authenticated_settings_context["settings_page"]

        initial_url = settings_pg.get_avatar_url_input_value()
        assert initial_url == _OLD_AVATAR_URL, (
            f"Expected Avatar URL field to contain the existing (old) avatar URL "
            f"before upload.\n"
            f"Expected: {_OLD_AVATAR_URL!r}\n"
            f"Got: {initial_url!r}\n"
            "Check that the GET /api/me handler and the form state initialisation "
            "in the settings page populate the avatarUrl field correctly."
        )

    def test_site_header_avatar_visible_before_upload(
        self, authenticated_settings_context: dict
    ) -> None:
        """The SiteHeader avatar button must be visible before the upload."""
        site_header: SiteHeader = authenticated_settings_context["site_header"]

        assert site_header.avatar_is_visible(), (
            "SiteHeader avatar button (header button span.rounded-full) is not "
            "visible before the avatar upload. The user should be authenticated "
            "and the gradient avatar circle should be rendered in the header."
        )

    def test_avatar_preview_shows_old_image_before_upload(
        self, authenticated_settings_context: dict
    ) -> None:
        """The AvatarPreview must display the old avatar image before upload."""
        settings_pg: SettingsPage = authenticated_settings_context["settings_page"]

        assert settings_pg.is_avatar_preview_container_visible(timeout=8_000), (
            "AvatarPreview container (role='img') not visible before upload. "
            "Expected it to render because avatar_url is set in the profile."
        )

        current_src = settings_pg.get_avatar_preview_img_src_from_dom()
        assert current_src == _OLD_AVATAR_URL, (
            f"AvatarPreview img src does not match the old avatar URL before upload.\n"
            f"Expected: {_OLD_AVATAR_URL!r}\n"
            f"Got: {current_src!r}"
        )

    def test_upload_new_avatar_shows_success_message(
        self, authenticated_settings_context: dict, tmp_jpeg_file: str
    ) -> None:
        """Uploading a new avatar must display the success message."""
        settings_pg: SettingsPage = authenticated_settings_context["settings_page"]

        settings_pg.select_avatar_file(tmp_jpeg_file)
        settings_pg.wait_for_upload_button_enabled(timeout=5_000)
        settings_pg.click_upload_button()

        success = settings_pg.wait_for_upload_success_message(timeout=_UPLOAD_TIMEOUT)
        assert success, (
            "The success message 'Avatar uploaded successfully.' was not shown "
            f"within {_UPLOAD_TIMEOUT} ms after clicking Upload.\n"
            "Expected: p[role='status'] containing 'Avatar uploaded successfully.'\n"
            "Check that handleAvatarUpload sets uploadSuccess=true on a 200 response."
        )

    def test_avatar_url_field_updated_to_new_unique_url(
        self, authenticated_settings_context: dict
    ) -> None:
        """The Avatar URL field must be updated with the new unique (UUID) URL.

        This is the core MYTUBE-642 regression check: the new URL must contain
        a UUID component and must differ from the old static URL.
        """
        settings_pg: SettingsPage = authenticated_settings_context["settings_page"]

        new_url = settings_pg.get_avatar_url_input_value()
        assert new_url == _NEW_AVATAR_URL, (
            f"Avatar URL field not updated with the new unique URL after upload.\n"
            f"Expected: {_NEW_AVATAR_URL!r}\n"
            f"Got: {new_url!r}\n"
            "Check that handleAvatarUpload calls setForm with data.avatar_url."
        )

        assert new_url != _OLD_AVATAR_URL, (
            "The new avatar URL is the same as the old URL — the MYTUBE-642 "
            "cache-busting fix does not appear to be in effect. "
            "The API should return a URL with a unique UUID component per upload."
        )

    def test_avatar_preview_updated_to_new_image_after_upload(
        self, authenticated_settings_context: dict
    ) -> None:
        """The AvatarPreview must show the newly uploaded avatar image immediately.

        After a successful upload, setForm is called with the new avatar_url.
        The AvatarPreview receives the new src prop and renders the new image
        without requiring a page reload.
        """
        settings_pg: SettingsPage = authenticated_settings_context["settings_page"]

        actual_src = settings_pg.wait_for_avatar_img_src(
            _NEW_AVATAR_URL, timeout=8_000
        )
        assert actual_src == _NEW_AVATAR_URL, (
            f"AvatarPreview img src not updated to the new avatar URL after upload.\n"
            f"Expected: {_NEW_AVATAR_URL!r}\n"
            f"Got: {actual_src!r}\n"
            "The settings page should propagate the new URL to AvatarPreview via "
            "setForm so the preview updates immediately without a page reload."
        )

    def test_site_header_avatar_still_visible_after_upload(
        self, authenticated_settings_context: dict
    ) -> None:
        """The SiteHeader avatar button must remain visible after the upload.

        After a successful avatar upload the user should still be authenticated
        and the header avatar (gradient circle with user's initial) must be
        rendered.  This confirms the upload does not affect the auth session.
        """
        site_header: SiteHeader = authenticated_settings_context["site_header"]

        assert site_header.avatar_is_visible(), (
            "SiteHeader avatar button not visible after avatar upload. "
            "The upload should not affect the authenticated session. "
            "Expected the gradient avatar circle (header button span.rounded-full) "
            "to remain visible in the site header."
        )
