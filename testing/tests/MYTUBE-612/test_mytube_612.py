"""
MYTUBE-612: Modify avatar URL field — preview updates reactively.

Objective
---------
Verify that the avatar preview updates automatically as the user types,
without requiring a save or refresh.

Preconditions
-------------
User is on the Account Settings page (/settings).

Steps
-----
1. Enter a valid image URL (Image A) into the "Avatar URL" field.
2. Confirm Image A is visible in the preview.
3. Edit the text in the field to point to a different valid image URL (Image B).

Expected Result
---------------
The preview image updates to show Image B immediately as the URL string is
modified, with no requirement for clicking a save button.

Architecture
------------
- Playwright sync API with pytest module-scoped fixtures.
- LoginPage: authenticates the browser user before navigating to /settings.
- SettingsPage: page-object wrapper for all /settings interactions.
- WebConfig: centralises env var access (APP_URL, credentials).
- Route interception: serves deterministic 1×1 GIF responses for both test
  image URLs so the <img> elements mount without network errors.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Test user email (required — test skips when absent).
FIREBASE_TEST_PASSWORD   Test user password (required — test skips when absent).
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-612/test_mytube_612.py -v
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys

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
_LOGIN_TIMEOUT = 20_000       # ms — max time for post-login redirect

# Two distinct test image URLs. Playwright route interception serves a valid
# GIF for both, so image-load errors never fire and onError is never called.
_IMAGE_A_URL = "https://img-cdn.example.net/mytube-612-avatar-a.png"
_IMAGE_B_URL = "https://img-cdn.example.net/mytube-612-avatar-b.png"

# Regex used as the route URL matcher — matches any URL containing our
# test-specific token so interception is reliable regardless of exact URL form.
_TEST_IMAGE_PATTERN = re.compile(r"mytube-612-avatar")

# Minimal valid 1×1 transparent GIF (binary, 35 bytes).
_GIF_1X1 = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings_url(config: WebConfig) -> str:
    return f"{config.base_url}/settings/"


def _image_route_handler(route: Route, request: Request) -> None:
    """Return a valid 1×1 GIF instantly for any intercepted avatar image request."""
    route.fulfill(
        status=200,
        content_type="image/gif",
        body=_GIF_1X1,
    )


# Stable profile GET response — prevents the background /api/me fetch from
# overwriting form.avatarUrl mid-test and causing the preview to disappear.
_STABLE_PROFILE_JSON = json.dumps({
    "id": "00000000-0000-0000-0000-000000000612",
    "username": "testuser612",
    "avatar_url": None,
}).encode()

# Regex matching any /api/me URL (handles any origin prefix).
_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")


def _api_me_route_handler(route: Route, request: Request) -> None:
    """Intercept GET /api/me to return a predictable empty-avatar profile.

    PUT /api/me (save settings) is passed through to the real server so the
    test doesn't accidentally persist bad state.
    """
    if request.method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_STABLE_PROFILE_JSON,
        )
    else:
        route.continue_()


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
            "FIREBASE_TEST_EMAIL not set — skipping avatar preview reactivity test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping avatar preview reactivity test. "
            "Set FIREBASE_TEST_PASSWORD to run this test."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    """Launch a Chromium browser for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def authenticated_settings_page(
    browser: Browser, web_config: WebConfig
) -> dict:
    """
    Log in once, navigate to /settings, register image route interceptors,
    and yield {page, settings_page} for all tests in the module.
    """
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Intercept test avatar image URLs with a regex so ALL requests containing
    # our test token are served a valid GIF — prevents onError from firing.
    page.route(_TEST_IMAGE_PATTERN, _image_route_handler)

    # Intercept GET /api/me to return a stable profile with no avatar_url.
    # This prevents the background profile fetch from resetting form.avatarUrl
    # mid-test and causing the preview container to disappear unexpectedly.
    page.route(_API_ME_PATTERN, _api_me_route_handler)

    # Step 0: Log in.
    login_pg = LoginPage(page)
    login_pg.navigate(web_config.login_url())
    login_pg.login_as(web_config.test_email, web_config.test_password)
    login_pg.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

    # Step 1: Navigate to /settings.
    settings_pg = SettingsPage(page)
    settings_pg.navigate(_settings_url(web_config))

    yield {"page": page, "settings_page": settings_pg}

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarPreviewReactivity:
    """MYTUBE-612: Avatar preview reflects the URL field value reactively."""

    def test_preview_shows_image_a_when_typed(
        self, authenticated_settings_page: dict
    ) -> None:
        """
        After entering Image A URL into the Avatar URL field, the preview
        <img> element must appear with src equal to Image A URL — without
        clicking Save.
        """
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        # Enter Image A URL into the Avatar URL field (no save).
        settings_pg.fill_avatar_url(_IMAGE_A_URL)

        # The preview container (role="img") should become visible.
        assert settings_pg.is_avatar_preview_container_visible(timeout=5_000), (
            "Avatar preview container did not become visible after entering Image A URL "
            f"({_IMAGE_A_URL!r}). "
            "The AvatarPreview component may not be rendering."
        )

        # The <img> inside the preview must have src = Image A URL.
        actual_src = settings_pg.wait_for_avatar_img_src(_IMAGE_A_URL, timeout=8_000)
        assert actual_src == _IMAGE_A_URL, (
            f"Avatar preview img src mismatch after entering Image A URL. "
            f"Expected: {_IMAGE_A_URL!r}, Got: {actual_src!r}. "
            "The preview is not reactively reflecting the typed URL."
        )

    def test_preview_updates_to_image_b_without_save(
        self, authenticated_settings_page: dict
    ) -> None:
        """
        After editing the Avatar URL field from Image A to Image B, the
        preview <img> src must update to Image B URL immediately — without
        clicking the Save Settings button.
        """
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]
        page: Page = authenticated_settings_page["page"]

        # Change the avatar URL field to Image B (simulates 'editing the text').
        settings_pg.fill_avatar_url(_IMAGE_B_URL)

        # The input must reflect the new URL.
        input_val = settings_pg.get_avatar_url_input_value()
        assert input_val == _IMAGE_B_URL, (
            f"Avatar URL input value not updated to Image B. "
            f"Expected: {_IMAGE_B_URL!r}, Got: {input_val!r}."
        )

        # The preview container must be visible (form.avatarUrl is truthy → component renders).
        assert settings_pg.is_avatar_preview_container_visible(timeout=5_000), (
            "Avatar preview container disappeared after changing from Image A to Image B URL. "
            "Expected the preview to remain visible with the new URL."
        )

        # The <img> src must update to Image B URL without a save or page reload.
        actual_src = settings_pg.wait_for_avatar_img_src(_IMAGE_B_URL, timeout=8_000)
        assert actual_src == _IMAGE_B_URL, (
            f"Avatar preview img src did NOT update when the URL field changed to Image B. "
            f"Expected: {_IMAGE_B_URL!r}, Got: {actual_src!r}. "
            "The preview is not updating reactively — a save or refresh may be required, "
            "which contradicts the expected behaviour."
        )
