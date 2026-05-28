"""
MYTUBE-656: Delete avatar API failure — error message displayed and avatar remains.

Objective
---------
Verify that the UI handles backend errors gracefully during avatar removal.
When the DELETE /api/me/avatar request returns a 500 Internal Server Error,
an inline error message must appear and the avatar preview/state must remain
unchanged.

Preconditions
-------------
- User is on the Account Settings page with an avatar set.

Steps
-----
1. Login and navigate to /settings.
2. Set up route interception: GET /api/me returns a profile with an
   avatar URL so the "Remove avatar" button is visible.
3. Set up route interception: DELETE /api/me/avatar returns HTTP 500 with
   ``{"error": "Internal Server Error"}``.
4. Click the "Remove avatar" button.
5. Assert that a ``<p role="alert">`` element appears with the error text.
6. Assert that the avatar URL input field still contains the original URL
   (avatar state was NOT cleared).

Expected Result
---------------
- An inline error message is displayed near the avatar.
- The avatar preview and the avatar URL in the form remain unchanged.

Architecture
------------
- WebConfig: base URL and credentials from environment variables.
- LoginPage: authentication flow.
- SettingsPage: page object with ``click_remove_avatar()``,
  ``get_remove_error_text()``, and ``is_remove_avatar_button_visible()``.
- Playwright route interception simulates a backend 500 failure without
  requiring a running API server.

Environment variables
---------------------
APP_URL / WEB_BASE_URL      Base URL of the deployed web app.
                            Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL         Email for the test Firebase account (required).
FIREBASE_TEST_PASSWORD      Password for the test Firebase account (required).
PLAYWRIGHT_HEADLESS         Run headless (default: true).
PLAYWRIGHT_SLOW_MO          Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-656/test_mytube_656.py -v
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Route

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NAVIGATION_TIMEOUT = 25_000   # ms
_PAGE_LOAD_TIMEOUT = 30_000    # ms
_ERROR_APPEAR_TIMEOUT = 8_000  # ms — error must appear within this window

# A stable test avatar URL injected via profile interception.
_TEST_AVATAR_URL = "https://cdn.example.com/test-avatar-656.png"

# The error body returned by the fake 500 response.
_BACKEND_ERROR_MSG = "Internal Server Error"

# Expected fallback message (settings page uses body.error or a hardcoded fallback).
_EXPECTED_ERROR_CONTAINS = "Internal Server Error"

# Selectors used for assertions beyond SettingsPage methods.
_AVATAR_ENDPOINT_SUFFIX = "/api/me/avatar"
# Regex to match the profile endpoint exactly (GET /api/me) without matching /api/me/avatar.
_PROFILE_ENDPOINT_RE = re.compile(r".*/api/me$")


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
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-656 avatar removal "
            "error test. Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-656. "
            "Set FIREBASE_TEST_PASSWORD to run."
        )


@pytest.fixture(scope="module")
def browser():
    """Launch a single Chromium browser instance for the module."""
    with sync_playwright() as pw:
        cfg = WebConfig()
        br = pw.chromium.launch(
            headless=cfg.headless,
            slow_mo=cfg.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="function")
def page(browser: Browser) -> Page:
    """Open a fresh browser context and page for each test."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="function")
def settings_page(page: Page) -> SettingsPage:
    return SettingsPage(page)


@pytest.fixture(scope="function")
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)


@pytest.fixture(scope="function")
def authenticated_page_with_avatar(
    web_config: WebConfig,
    login_page: LoginPage,
    settings_page: SettingsPage,
    page: Page,
) -> Page:
    """Authenticate, inject a fake avatar via profile interception, navigate to /settings."""
    # ---- Login first (before route interception so the real login call goes through) ----
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)

    # ---- Intercept profile GET to inject avatar URL ----
    def _handle_profile(route: Route) -> None:
        route.fulfill(
            status=200,
            content_type="application/json",
            body=json.dumps({"username": "testuser", "avatar_url": _TEST_AVATAR_URL}),
        )

    page.route(_PROFILE_ENDPOINT_RE, _handle_profile)

    # ---- Navigate to /settings (triggers profile fetch → intercepted) ----
    settings_page.navigate(web_config.settings_url())

    yield page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeleteAvatarApiFailure:
    """MYTUBE-656: Backend 500 on DELETE /api/me/avatar shows error and keeps avatar."""

    def test_error_message_displayed_on_500(
        self,
        authenticated_page_with_avatar: Page,
        settings_page: SettingsPage,
        page: Page,
    ) -> None:
        """Clicking 'Remove avatar' when DELETE returns 500 must show an inline error.

        Route interception stubs DELETE /api/me/avatar with HTTP 500 and a JSON
        body ``{"error": "Internal Server Error"}``.  The SettingsPage handler
        propagates this message to ``setRemoveError``, which renders
        ``<p role="alert">{message}</p>`` near the avatar section.
        """
        # ---- Pre-condition: "Remove avatar" button must be visible ----
        assert settings_page.is_remove_avatar_button_visible(timeout=10_000), (
            "Precondition failed: 'Remove avatar' button is not visible. "
            f"The profile should have been mocked to return avatar_url={_TEST_AVATAR_URL!r}."
        )

        # ---- Intercept DELETE to simulate 500 failure ----
        def _handle_delete(route: Route) -> None:
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"error": _BACKEND_ERROR_MSG}),
            )

        authenticated_page_with_avatar.route(
            f"**{_AVATAR_ENDPOINT_SUFFIX}",
            _handle_delete,
        )

        # ---- Trigger removal ----
        settings_page.click_remove_avatar()

        # ---- Assert error message is shown ----
        error_text = settings_page.get_remove_error_text(timeout=_ERROR_APPEAR_TIMEOUT)
        assert error_text is not None, (
            "Expected an inline error message (p[role='alert']) to appear after "
            "clicking 'Remove avatar' when the backend returns 500, but no alert "
            "element was found within the timeout."
        )
        assert _EXPECTED_ERROR_CONTAINS.lower() in error_text.lower(), (
            f"Expected the error message to contain {_EXPECTED_ERROR_CONTAINS!r}, "
            f"but got: {error_text!r}"
        )

    def test_avatar_state_unchanged_on_500(
        self,
        web_config: WebConfig,
        login_page: LoginPage,
        settings_page: SettingsPage,
        page: Page,
    ) -> None:
        """After a 500 failure, the avatar URL input field must retain its original value.

        A fresh page/context is used (via `page` fixture) to isolate state.
        """
        # ---- Login ----
        login_page.navigate(web_config.login_url())
        login_page.login_as(web_config.test_email, web_config.test_password)
        login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)

        # ---- Intercept profile GET to inject avatar URL ----
        def _handle_profile(route: Route) -> None:
            route.fulfill(
                status=200,
                content_type="application/json",
                body=json.dumps({"username": "testuser", "avatar_url": _TEST_AVATAR_URL}),
            )

        page.route(_PROFILE_ENDPOINT_RE, _handle_profile)

        # ---- Intercept DELETE to simulate 500 failure ----
        def _handle_delete(route: Route) -> None:
            route.fulfill(
                status=500,
                content_type="application/json",
                body=json.dumps({"error": _BACKEND_ERROR_MSG}),
            )

        page.route(f"**{_AVATAR_ENDPOINT_SUFFIX}", _handle_delete)

        # ---- Navigate to /settings ----
        settings_page.navigate(web_config.settings_url())

        # ---- Pre-condition: "Remove avatar" button must be visible ----
        assert settings_page.is_remove_avatar_button_visible(timeout=10_000), (
            "Precondition failed: 'Remove avatar' button not visible after profile mock."
        )

        # Capture the avatar URL before removal attempt.
        avatar_url_before = settings_page.get_avatar_url_field_value()

        # ---- Trigger removal ----
        settings_page.click_remove_avatar()

        # ---- Wait for error to appear (confirms the response was processed) ----
        settings_page.wait_for_remove_error(timeout=_ERROR_APPEAR_TIMEOUT)

        # ---- Assert avatar URL field unchanged ----
        avatar_url_after = settings_page.get_avatar_url_field_value()
        assert avatar_url_after == avatar_url_before, (
            f"Avatar URL field should remain {avatar_url_before!r} after a failed "
            f"removal, but it changed to {avatar_url_after!r}. "
            "The frontend must NOT clear the avatar state when the backend returns an error."
        )

        # ---- Assert "Remove avatar" button still visible ----
        assert settings_page.is_remove_avatar_button_visible(timeout=3_000), (
            "The 'Remove avatar' button should still be visible after a failed removal "
            "(avatar URL was not cleared), but it disappeared."
        )
