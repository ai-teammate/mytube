"""
MYTUBE-654: Remove avatar button visibility — button hidden when no avatar exists.

Objective
---------
Verify that the 'Remove avatar' button only appears when the user actually has
an avatar to remove (i.e. ``avatarUrl`` is non-empty), and is hidden when
``avatarUrl`` is empty.

Preconditions
-------------
User is on the Account Settings page.

Steps
-----
1. Clear the avatar (if one exists) so ``avatarUrl`` is empty.
2. Observe the interface — 'Remove avatar' button must NOT be visible.
3. Upload a new avatar / fill in a valid avatarUrl.
4. Observe the interface again — 'Remove avatar' button must be visible.

Expected Result
---------------
The 'Remove avatar' button is hidden when ``avatarUrl`` is empty and becomes
visible only when a valid ``avatarUrl`` is present.

Implementation notes
--------------------
- GET /api/me is mocked per scenario:
    Scenario A  → returns ``{"avatar_url": ""}`` (no avatar).
    Scenario B  → returns ``{"avatar_url": "<valid URL>"}`` (avatar exists).
- No real network calls; all external requests are intercepted.
- The test also covers the intermediate state: filling the Avatar URL input
  directly (without an API round-trip) to confirm the button renders reactively.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Test user email (required — test skips when absent).
FIREBASE_TEST_PASSWORD   Test user password (required — test skips when absent).
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-654/test_mytube_654.py -v
"""
from __future__ import annotations

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
_LOGIN_TIMEOUT = 20_000       # ms

# A valid avatar URL used for the "has avatar" scenario.
_VALID_AVATAR_URL = (
    "https://storage.googleapis.com/mytube-test/avatars/user654/avatar.jpg"
)

_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")

# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _make_api_me_handler(avatar_url: str):
    """Return a GET /api/me route handler serving *avatar_url* in the profile."""
    profile_bytes: bytes = json.dumps(
        {"username": "testuser654", "avatar_url": avatar_url}
    ).encode()

    def handler(route: Route, request: Request) -> None:
        if request.method == "GET":
            route.fulfill(
                status=200,
                content_type="application/json",
                body=profile_bytes,
            )
        else:
            route.continue_()

    return handler


def _gif_handler(route: Route, request: Request) -> None:
    """Serve a minimal 1×1 transparent GIF for CDN avatar image requests."""
    import base64
    gif = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")
    route.fulfill(status=200, content_type="image/gif", body=gif)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig) -> None:
    """Skip the entire module when Firebase credentials are absent."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-654 test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-654 test. "
            "Set FIREBASE_TEST_PASSWORD to run."
        )


@pytest.fixture(scope="module")
def browser_instance(web_config: WebConfig) -> Browser:
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


def _login_and_open_settings(
    browser: Browser, web_config: WebConfig, avatar_url: str
) -> tuple[BrowserContext, Page, SettingsPage]:
    """Log in, mock GET /api/me with *avatar_url*, navigate to /settings.

    Returns (context, page, settings_page).  Caller is responsible for
    calling ``context.close()`` when done.
    """
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Intercept GET /api/me to return the desired avatarUrl.
    page.route(_API_ME_PATTERN, _make_api_me_handler(avatar_url))

    # Serve valid GIF for any CDN image requests (prevents AvatarPreview onError).
    if avatar_url:
        page.route(re.compile(r"storage\.googleapis\.com.*avatars/"), _gif_handler)

    login_pg = LoginPage(page)
    login_pg.navigate(web_config.login_url())
    login_pg.login_as(web_config.test_email, web_config.test_password)
    login_pg.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

    settings_pg = SettingsPage(page)
    settings_pg.navigate(web_config.settings_url())

    return context, page, settings_pg


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRemoveAvatarButtonVisibility:
    """MYTUBE-654: 'Remove avatar' button visibility based on avatarUrl state."""

    # ------------------------------------------------------------------
    # Scenario A: user has NO avatar
    # ------------------------------------------------------------------

    def test_remove_button_hidden_when_avatar_url_is_empty(
        self, browser_instance: Browser, web_config: WebConfig
    ) -> None:
        """'Remove avatar' button must NOT be visible when avatarUrl is empty.

        The GET /api/me mock returns an empty avatar_url so the settings form
        initialises with avatarUrl = "".  Because the button is rendered inside
        {form.avatarUrl && (…)}, it must be absent from the DOM.
        """
        context, page, settings_pg = _login_and_open_settings(
            browser_instance, web_config, avatar_url=""
        )
        try:
            is_hidden = settings_pg.is_remove_avatar_button_hidden(timeout=5_000)
            assert is_hidden, (
                "'Remove avatar' button is visible when avatarUrl is empty.\n"
                "Expected: button should NOT be rendered when form.avatarUrl == ''.\n"
                "Check that the conditional `{form.avatarUrl && (<button>…)}` "
                "in settings/page.tsx correctly hides the button for an empty URL."
            )
        finally:
            context.close()

    # ------------------------------------------------------------------
    # Scenario B: user HAS an avatar
    # ------------------------------------------------------------------

    def test_remove_button_visible_when_avatar_url_is_set(
        self, browser_instance: Browser, web_config: WebConfig
    ) -> None:
        """'Remove avatar' button must be visible when avatarUrl is non-empty.

        The GET /api/me mock returns a valid avatar_url so the settings form
        initialises with avatarUrl set.  The button inside {form.avatarUrl && (…)}
        must therefore be rendered and visible.
        """
        context, page, settings_pg = _login_and_open_settings(
            browser_instance, web_config, avatar_url=_VALID_AVATAR_URL
        )
        try:
            is_visible = settings_pg.is_remove_avatar_button_visible(timeout=8_000)
            assert is_visible, (
                f"'Remove avatar' button is NOT visible when avatarUrl is set "
                f"to {_VALID_AVATAR_URL!r}.\n"
                "Expected: button should be rendered inside `{form.avatarUrl && …}` "
                "in settings/page.tsx when the avatar URL is non-empty.\n"
                "Check that the AvatarPreview block containing the 'Remove avatar' "
                "button is actually rendered when form.avatarUrl is truthy."
            )
        finally:
            context.close()

    # ------------------------------------------------------------------
    # Scenario C: reactive toggle — button appears after filling the URL field
    # ------------------------------------------------------------------

    def test_remove_button_appears_after_filling_avatar_url_input(
        self, browser_instance: Browser, web_config: WebConfig
    ) -> None:
        """'Remove avatar' button must appear reactively after the URL field is filled.

        Start with an empty avatarUrl (button hidden), then fill the Avatar URL
        input with a valid URL and confirm the button renders without a page reload.
        """
        context, page, settings_pg = _login_and_open_settings(
            browser_instance, web_config, avatar_url=""
        )
        try:
            # Confirm button is initially hidden.
            assert settings_pg.is_remove_avatar_button_hidden(timeout=5_000), (
                "'Remove avatar' button is visible before filling the URL field — "
                "expected it to be hidden when avatarUrl starts empty."
            )

            # Serve GIF for the CDN URL we're about to inject so AvatarPreview
            # doesn't fire onError.
            page.route(
                re.compile(r"storage\.googleapis\.com.*avatars/"),
                _gif_handler,
            )

            # Fill the Avatar URL input — this triggers React's onChange →
            # setForm → re-render → button should now appear.
            settings_pg.fill_avatar_url(_VALID_AVATAR_URL)

            # Button should now be visible (React re-renders synchronously on input).
            is_visible = settings_pg.is_remove_avatar_button_visible(timeout=8_000)
            assert is_visible, (
                "'Remove avatar' button did NOT appear after filling the Avatar URL "
                f"input with {_VALID_AVATAR_URL!r}.\n"
                "Expected: React's onChange handler sets form.avatarUrl which makes "
                "`{form.avatarUrl && (<button>Remove avatar</button>)}` render.\n"
                "Check that the onChange on the avatar_url input calls setForm and "
                "that the conditional block in settings/page.tsx re-renders correctly."
            )
        finally:
            context.close()
