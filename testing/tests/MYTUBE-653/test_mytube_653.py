"""
MYTUBE-653: SiteHeader avatar refresh — reverts to placeholder after deletion.

Objective
---------
Verify that the global SiteHeader avatar immediately reflects the removal of
the profile picture — the avatar reverts to the default placeholder icon/initials
without requiring a manual page refresh.

Preconditions
-------------
User is authenticated and viewing the Account Settings page; the SiteHeader
currently shows the user's custom avatar (an <img> element).

Steps
-----
1. Log in with a valid Firebase test account.
2. Navigate to /settings; mock GET /api/me to return a profile with a custom
   avatar URL so the SiteHeader renders the <img> avatar.
3. Confirm the SiteHeader shows the custom avatar image (not the placeholder span).
4. Click the 'Remove avatar' button.
5. Mock DELETE /api/me/avatar to return HTTP 200.
6. Wait for the removal to complete (avatar URL field clears).
7. Assert the SiteHeader avatar immediately reverts to the placeholder
   (gradient span, no <img>) without a page reload.

Expected Result
---------------
After clicking 'Remove avatar' and receiving a 200 response:
- The SiteHeader no longer contains ``<img class="...rounded-full">``
- The SiteHeader shows the gradient ``<span class="...rounded-full">`` placeholder
  with the user's initial letter.
- No manual page reload is required.

Architecture
------------
- LoginPage, SettingsPage, and SiteHeader Page Objects handle all DOM interactions.
- Playwright route interception mocks GET /api/me and DELETE /api/me/avatar.
- CDN avatar URL requests are also mocked to serve a valid 1×1 GIF (prevents
  AvatarPreview onError from switching to SVG fallback unexpectedly).
- WebConfig from testing/core/config/web_config.py provides all env vars.
- Credentials required: FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD.

Run from repo root:
    pytest testing/tests/MYTUBE-653/test_mytube_653.py -v
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Request, Route, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage
from testing.components.pages.site_header.site_header import SiteHeader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms — max time for initial page load
_LOGIN_TIMEOUT = 20_000        # ms — max time to wait for post-login redirect
_REMOVE_TIMEOUT = 10_000       # ms — max time to wait for removal completion

# A stable avatar URL that the user already has before removal.
_EXISTING_AVATAR_URL = (
    "https://storage.googleapis.com/mytube-hls-output/"
    "avatars/uid_653_test/existing_avatar.jpg"
)

# Minimal valid 1×1 transparent GIF — served for any avatar CDN image request.
_GIF_1X1 = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

# Route patterns
_API_ME_AVATAR_PATTERN = re.compile(r"/api/me/avatar")
_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")
_EXISTING_CDN_PATTERN = re.compile(r"existing_avatar\.jpg")

# Profile JSON with the existing avatar URL.
_INITIAL_PROFILE_JSON: bytes = json.dumps(
    {
        "username": "testuser653",
        "avatar_url": _EXISTING_AVATAR_URL,
    }
).encode()

# Successful delete response (empty 200).
_DELETE_SUCCESS_JSON: bytes = json.dumps({}).encode()


# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _api_me_avatar_delete_handler(route: Route, request: Request) -> None:
    """Mock DELETE /api/me/avatar — returns 200 to simulate successful removal."""
    if request.method == "DELETE":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_DELETE_SUCCESS_JSON,
        )
    else:
        route.continue_()


def _api_me_handler(route: Route, request: Request) -> None:
    """Mock GET /api/me — returns a stable profile with the existing avatar URL."""
    if request.method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_INITIAL_PROFILE_JSON,
        )
    else:
        route.continue_()


def _avatar_image_handler(route: Route, _request: Request) -> None:
    """Serve a valid 1×1 GIF for the existing avatar CDN URL.

    Prevents AvatarPreview's onError handler from firing so the preview
    stays in its normal (image-loaded) state before the removal.
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
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-653 SiteHeader avatar "
            "revert test. Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-653 test. "
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
def authenticated_settings_context(browser: Browser, web_config: WebConfig) -> dict:
    """Log in, navigate to /settings, install route interceptors, yield context dict.

    Route interceptors installed:
    * DELETE /api/me/avatar  → 200 OK (simulates successful removal).
    * GET    /api/me         → profile JSON with the existing avatar URL.
    * CDN URL for existing avatar → valid 1×1 GIF (prevents onError fallback).
    """
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Register DELETE /api/me/avatar interceptor BEFORE the broader /api/me pattern.
    page.route(_API_ME_AVATAR_PATTERN, _api_me_avatar_delete_handler)
    page.route(_API_ME_PATTERN, _api_me_handler)
    page.route(_EXISTING_CDN_PATTERN, _avatar_image_handler)

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


class TestSiteHeaderAvatarRevertsAfterDeletion:
    """MYTUBE-653: SiteHeader avatar reverts to placeholder after avatar removal."""

    def test_initial_avatar_url_field_shows_existing_url(
        self, authenticated_settings_context: dict
    ) -> None:
        """Before removal: the Avatar URL field must contain the existing avatar URL."""
        settings_pg: SettingsPage = authenticated_settings_context["settings_page"]

        initial_url = settings_pg.get_avatar_url_input_value()
        assert initial_url == _EXISTING_AVATAR_URL, (
            f"Expected Avatar URL field to contain the existing avatar URL before removal.\n"
            f"Expected: {_EXISTING_AVATAR_URL!r}\n"
            f"Got: {initial_url!r}\n"
            "Check that GET /api/me returns avatar_url and the settings form is "
            "populated correctly."
        )

    def test_site_header_shows_avatar_image_before_removal(
        self, authenticated_settings_context: dict
    ) -> None:
        """Before removal: the SiteHeader must show the custom avatar <img> element."""
        site_header: SiteHeader = authenticated_settings_context["site_header"]

        has_img = site_header.header_has_avatar_image()
        assert has_img, (
            "Expected the SiteHeader to render an <img class='...rounded-full'> "
            "avatar before the removal, because the user has a non-empty avatarUrl "
            "in AuthContext. Got: the <img> element is not visible in the header.\n"
            "Check that AuthContext.setAvatarUrl() is called with the existing URL "
            "when the settings page loads its profile."
        )

    def test_remove_avatar_button_is_visible(
        self, authenticated_settings_context: dict
    ) -> None:
        """The 'Remove avatar' button must be visible when an avatar URL is set."""
        settings_pg: SettingsPage = authenticated_settings_context["settings_page"]

        visible = settings_pg.is_remove_avatar_button_visible(timeout=5_000)
        assert visible, (
            "The 'Remove avatar' button is not visible on the settings page. "
            "Expected it to be rendered because form.avatarUrl is non-empty. "
            "Check that settings/page.tsx renders the button inside the "
            "{form.avatarUrl && ...} conditional block."
        )

    def test_click_remove_avatar_and_site_header_reverts_to_placeholder(
        self, authenticated_settings_context: dict
    ) -> None:
        """Core test: clicking 'Remove avatar' must revert the SiteHeader to placeholder.

        This is the primary assertion for MYTUBE-653:
        - Clicking 'Remove avatar' triggers DELETE /api/me/avatar (mocked → 200).
        - On success, settings/page.tsx calls setAvatarUrl("") on AuthContext.
        - SiteHeader reads avatarUrl from AuthContext and switches from <img> to <span>.
        - The <span class="...rounded-full..."> placeholder must be visible in the
          header immediately — no page reload required.
        """
        settings_pg: SettingsPage = authenticated_settings_context["settings_page"]
        site_header: SiteHeader = authenticated_settings_context["site_header"]

        # Click the Remove avatar button.
        settings_pg.click_remove_avatar()

        # Wait for removal to complete (avatar URL field cleared or "Removing…" gone).
        settings_pg.wait_for_avatar_removed(timeout=_REMOVE_TIMEOUT)

        # Assert the SiteHeader now shows the placeholder span (gradient circle).
        site_header.wait_for_avatar_placeholder(timeout=8_000)

        placeholder_visible = site_header.avatar_is_visible()
        assert placeholder_visible, (
            "After removing the avatar, the SiteHeader placeholder span "
            "(header button span.rounded-full with gradient background) is NOT visible.\n"
            "Expected: the gradient circle with user's initial letter replaces the "
            "custom avatar image immediately after deletion.\n"
            "Check that handleAvatarRemove() calls setAvatarUrl('') on AuthContext "
            "and that SiteHeader re-renders accordingly."
        )

    def test_site_header_no_avatar_image_after_removal(
        self, authenticated_settings_context: dict
    ) -> None:
        """After removal: the SiteHeader must NOT show the custom avatar <img>."""
        site_header: SiteHeader = authenticated_settings_context["site_header"]

        has_img = site_header.header_has_avatar_image()
        assert not has_img, (
            "After removing the avatar, the SiteHeader still shows the custom avatar "
            "<img class='...rounded-full'> element.\n"
            "Expected: the <img> is gone and only the gradient placeholder <span> is "
            "shown in the header.\n"
            "Check that setAvatarUrl('') is propagated correctly from the settings "
            "page to AuthContext and that SiteHeader re-renders without the <img>."
        )

    def test_avatar_url_field_cleared_after_removal(
        self, authenticated_settings_context: dict
    ) -> None:
        """After removal: the Avatar URL input field must be empty."""
        settings_pg: SettingsPage = authenticated_settings_context["settings_page"]

        url_value = settings_pg.get_avatar_url_input_value()
        assert url_value == "", (
            f"Expected Avatar URL field to be empty after removal.\n"
            f"Got: {url_value!r}\n"
            "Check that handleAvatarRemove() calls "
            "setForm((prev) => {{ ...prev, avatarUrl: '' }}) on success."
        )
