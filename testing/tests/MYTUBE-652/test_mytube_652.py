"""
MYTUBE-652: Click Remove avatar button — avatar removed and UI updated.

Objective
---------
Verify that clicking the 'Remove avatar' button triggers a DELETE request to the backend
and upon success sets form.avatarUrl to an empty string so the image preview disappears.

Preconditions
-------------
User is on the Account Settings page and an avatar is currently set.

Steps
-----
1. Click the 'Remove avatar' button.
2. Wait for the request to complete.

Expected Result
---------------
- A DELETE request is sent to DELETE /api/me/avatar.
- Upon success, form.avatarUrl is set to an empty string.
- The image preview disappears (AvatarPreview component is no longer rendered).

Architecture
------------
- Playwright sync API via pytest module-scoped fixtures.
- LoginPage, SettingsPage: page-object wrappers for all DOM interactions.
- WebConfig: centralises env var access.
- Route interception:
    * GET /api/me         → returns a profile with an existing avatar URL.
    * DELETE /api/me/avatar → returns mocked HTTP 204 No Content.
    * CDN image requests  → served with a valid 1×1 GIF to prevent onError.
- A MutationObserver is armed in the browser before the click to record the DELETE
  request being dispatched (captured via page.route handler flag).

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Test user email (required — test skips when absent).
FIREBASE_TEST_PASSWORD   Test user password (required — test skips when absent).
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-652/test_mytube_652.py -v
"""
from __future__ import annotations

import base64
import json
import os
import re
import sys

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Route, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_LOGIN_TIMEOUT = 20_000       # ms
_ACTION_TIMEOUT = 10_000      # ms

# Pre-existing avatar URL that GET /api/me will return.
_EXISTING_AVATAR_URL = "https://storage.googleapis.com/mytube-test/avatars/user123.png"

# 1×1 transparent GIF — served for CDN avatar image requests so AvatarPreview renders.
_GIF_1X1 = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

# Route patterns
_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")
_API_ME_AVATAR_PATTERN = re.compile(r"/api/me/avatar(\?.*)?$")
_CDN_AVATAR_PATTERN = re.compile(r"storage\.googleapis\.com/mytube-test/avatars/")

# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _make_api_me_route_handler(avatar_url: str):
    """Return a route handler for GET /api/me that includes *avatar_url* in the profile."""

    def handler(route: Route) -> None:
        if route.request.method != "GET":
            route.fallback()
            return
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({
                "username": "testuser",
                "avatar_url": avatar_url,
                "email": "test@example.com",
            }),
        )

    return handler


def _make_avatar_delete_route_handler(delete_called_flag: dict):
    """Return a route handler for DELETE /api/me/avatar that records the call and returns 204."""

    def handler(route: Route) -> None:
        if route.request.method == "DELETE":
            delete_called_flag["called"] = True
            route.fulfill(status=204, body="")
        else:
            route.fallback()

    return handler


def _gif_route_handler(route: Route) -> None:
    """Serve a valid 1×1 GIF for avatar CDN requests to prevent AvatarPreview onError."""
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
    """Return the shared WebConfig instance."""
    return WebConfig()


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
def authenticated_settings_page(
    browser_instance: Browser, web_config: WebConfig
) -> dict:
    """Log in, navigate to /settings with an existing avatar set, install route interceptors.

    Route interceptors:
    * DELETE /api/me/avatar → 204 No Content; sets delete_called flag.
    * GET    /api/me        → profile with _EXISTING_AVATAR_URL.
    * CDN avatar URLs      → valid 1×1 GIF.
    """
    if not web_config.test_email or not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD not set — "
            "cannot authenticate for MYTUBE-652 test."
        )

    delete_called_flag: dict = {"called": False}

    context: BrowserContext = browser_instance.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Register DELETE route BEFORE the broader GET /api/me handler.
    page.route(
        _API_ME_AVATAR_PATTERN,
        _make_avatar_delete_route_handler(delete_called_flag),
    )

    # GET /api/me → profile with avatar already set.
    page.route(_API_ME_PATTERN, _make_api_me_route_handler(_EXISTING_AVATAR_URL))

    # Serve 1×1 GIF for CDN avatar images.
    page.route(_CDN_AVATAR_PATTERN, _gif_route_handler)

    # Log in and navigate to /settings.
    login_pg = LoginPage(page)
    login_pg.navigate(web_config.login_url())
    login_pg.login_as(web_config.test_email, web_config.test_password)
    login_pg.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

    settings_pg = SettingsPage(page)
    settings_pg.navigate(f"{web_config.base_url}/settings/")

    yield {
        "page": page,
        "settings_page": settings_pg,
        "delete_called_flag": delete_called_flag,
    }

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRemoveAvatarButton:
    """MYTUBE-652: Clicking Remove avatar sends DELETE and clears the image preview."""

    def test_precondition_existing_avatar_visible(
        self, authenticated_settings_page: dict
    ) -> None:
        """Precondition: settings page loaded with an existing avatar URL and preview visible."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        assert settings_pg.is_settings_page_loaded(timeout=20_000), (
            "Account Settings page did not load (h1 'Account settings' not found). "
            "Cannot verify precondition for remove avatar test."
        )

        current_url = settings_pg.get_avatar_url_input_value()
        assert current_url == _EXISTING_AVATAR_URL, (
            f"Precondition failed: expected Avatar URL field to contain {_EXISTING_AVATAR_URL!r} "
            f"but got {current_url!r}. The GET /api/me interceptor should return the avatar URL."
        )

        assert settings_pg.is_avatar_preview_container_visible(timeout=8_000), (
            "Precondition failed: AvatarPreview container not visible even though "
            f"avatar URL is set to {_EXISTING_AVATAR_URL!r}."
        )

    def test_remove_avatar_button_is_visible(
        self, authenticated_settings_page: dict
    ) -> None:
        """The 'Remove avatar' button must be visible when an avatar URL is set."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        assert settings_pg.is_remove_avatar_button_visible(), (
            "The 'Remove avatar' button was not found/visible on the settings page "
            "even though an avatar URL is set. The button should render inside the "
            "conditional block that shows when form.avatarUrl is non-empty."
        )

    def test_click_remove_avatar_sends_delete_request(
        self, authenticated_settings_page: dict
    ) -> None:
        """Clicking 'Remove avatar' must dispatch a DELETE /api/me/avatar request."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]
        delete_flag: dict = authenticated_settings_page["delete_called_flag"]

        # Reset flag in case other tests ran first.
        delete_flag["called"] = False

        settings_pg.click_remove_avatar()

        # Wait for the preview to disappear (signals async handler completed).
        settings_pg.wait_for_avatar_preview_gone(timeout=_ACTION_TIMEOUT)

        assert delete_flag["called"], (
            "No DELETE request was sent to /api/me/avatar after clicking 'Remove avatar'. "
            "Expected handleAvatarRemove() to call fetch() with method: 'DELETE' against "
            "the /api/me/avatar endpoint. The route interceptor did not record the call."
        )

    def test_avatar_url_input_cleared_after_remove(
        self, authenticated_settings_page: dict
    ) -> None:
        """After successful removal, the Avatar URL input field must be empty."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        avatar_url_value = settings_pg.get_avatar_url_input_value()
        assert avatar_url_value == "", (
            f"Avatar URL input field was not cleared after remove. "
            f"Expected empty string, got {avatar_url_value!r}. "
            "setForm((prev) => ({ ...prev, avatarUrl: '' })) should have been called "
            "on a successful DELETE response."
        )

    def test_avatar_preview_disappears_after_remove(
        self, authenticated_settings_page: dict
    ) -> None:
        """After removal the AvatarPreview container must not be visible in the DOM."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        # The AvatarPreview is conditionally rendered only when form.avatarUrl is non-empty.
        assert not settings_pg.is_avatar_img_present(), (
            "Avatar preview <img> element is still present after clicking Remove avatar. "
            "Expected the <img> to be removed from the DOM because form.avatarUrl "
            "was set to '' and AvatarPreview is only rendered when form.avatarUrl is truthy."
        )

    def test_remove_avatar_button_disappears_after_remove(
        self, authenticated_settings_page: dict
    ) -> None:
        """The 'Remove avatar' button must disappear once the avatar URL is cleared."""
        settings_pg: SettingsPage = authenticated_settings_page["settings_page"]

        # After clearing avatarUrl the conditional block is removed — button gone.
        button_visible = settings_pg.is_remove_avatar_button_visible()
        assert not button_visible, (
            "The 'Remove avatar' button is still visible after the avatar was removed. "
            "The button is rendered conditionally on form.avatarUrl being non-empty; "
            "after removal it should disappear."
        )
