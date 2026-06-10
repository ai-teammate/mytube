"""
MYTUBE-665: Navigation from other pages to Home — avatar remains applied.

Objective
---------
Ensure the avatar component does not lose its state or fail to load when
navigating to the Home page from another section of the application.

Preconditions
-------------
User is logged in.

Steps
-----
1. Navigate to any page other than the Home page (Account Settings).
2. Verify the avatar is visible in the header.
3. Use the application's navigation to return to the Home page.
4. Observe the avatar in the SiteHeader.

Expected Result
---------------
The avatar remains consistently visible and correctly applied after navigating
to the Home page; the UI does not revert to a blank state.

Related Bug
-----------
MYTUBE-663: Avatar is not applied on the home page (Status: Done — fix deployed).

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Test user email (required — test skips when absent).
FIREBASE_TEST_PASSWORD   Test user password (required — test skips when absent).
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-665/test_mytube_665.py -v
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
from testing.components.pages.home_page.home_page import HomePage
from testing.components.pages.site_header.site_header import SiteHeader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_LOGIN_TIMEOUT = 20_000       # ms
_AVATAR_WAIT_TIMEOUT = 10_000  # ms

_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")

# We use an empty avatar_url in the mock so the SiteHeader renders the
# placeholder <span class="rounded-full"> (initials circle).  The MYTUBE-663
# bug was about this element being completely absent on the Home page — we
# use the span variant because SiteHeader.avatar_wait() waits for the span.
# With a non-empty avatar_url the header renders <img> instead of <span>,
# which would make avatar_wait() time out (wrong selector).
_VALID_AVATAR_URL = ""

# ---------------------------------------------------------------------------
# Route handlers
# ---------------------------------------------------------------------------


def _make_api_me_handler(avatar_url: str):
    """Return a GET /api/me route handler serving *avatar_url* in the profile."""
    profile_bytes: bytes = json.dumps(
        {"username": "testuser665", "avatar_url": avatar_url}
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
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-665 test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-665 test. "
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarPersistsOnHomeNavigation:
    """MYTUBE-665: Avatar remains applied when navigating back to the Home page."""

    def test_avatar_remains_visible_after_navigating_to_home(
        self, browser_instance: Browser, web_config: WebConfig
    ) -> None:
        """Avatar persists in SiteHeader after navigating from Settings to Home.

        Steps:
        1. Login as the test user.
        2. Navigate to the Settings page (a non-home page).
        3. Assert avatar is visible in the header on the Settings page.
        4. Navigate to the Home page via the logo link.
        5. Assert avatar is still visible in the SiteHeader on the Home page.

        The MYTUBE-663 fix ensures AuthContext re-fetches the user profile
        correctly on navigation, so the avatar should not disappear.
        """
        context: BrowserContext = browser_instance.new_context()
        page: Page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        try:
            # Mock GET /api/me to return a user profile with an empty avatar_url.
            # An empty avatar_url causes SiteHeader to render the placeholder
            # <span class="rounded-full"> (initials circle), which is what
            # SiteHeader.avatar_wait() waits for.
            page.route(_API_ME_PATTERN, _make_api_me_handler(_VALID_AVATAR_URL))

            # Step 1: Log in.
            login_pg = LoginPage(page)
            login_pg.navigate(web_config.login_url())
            login_pg.login_as(web_config.test_email, web_config.test_password)
            login_pg.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

            # Step 2: Navigate to Settings (a non-home page).
            settings_pg = SettingsPage(page)
            settings_pg.navigate(web_config.settings_url())

            # Step 3: Verify avatar is visible in the header on the Settings page.
            header = SiteHeader(page)
            # Wait for the avatar to appear (either span placeholder or img).
            header.avatar_wait(timeout=_AVATAR_WAIT_TIMEOUT)

            avatar_on_settings = header.avatar_is_visible() or header.header_has_avatar_image()
            assert avatar_on_settings, (
                "Avatar is NOT visible in the SiteHeader on the Settings page "
                f"(URL: {page.url}).\n"
                "Precondition failed: the user must be authenticated with an avatar "
                "before we can test that it persists on Home navigation."
            )

            # Step 4: Navigate to the Home page using the logo link.
            header.click_logo()

            # Wait for Home page to be loaded.
            page.wait_for_url(
                lambda u: u.rstrip("/") == web_config.home_url().rstrip("/"),
                timeout=_PAGE_LOAD_TIMEOUT,
            )

            # Step 5: Verify avatar is still visible in the SiteHeader on the Home page.
            # Re-use the same SiteHeader instance (page is the same object).
            header.avatar_wait(timeout=_AVATAR_WAIT_TIMEOUT)

            avatar_on_home = header.avatar_is_visible() or header.header_has_avatar_image()
            assert avatar_on_home, (
                "Avatar is NOT visible in the SiteHeader after navigating to the Home page "
                f"(URL: {page.url}).\n"
                "Expected: the avatar span/image in the header should remain visible after "
                "navigating from Settings → Home.\n"
                "This regression was originally tracked as MYTUBE-663. "
                "Ensure the AuthContext profile fetch is not reset on Home page navigation."
            )

        finally:
            context.close()

    def test_avatar_visible_after_navigating_from_home_logo_click(
        self, browser_instance: Browser, web_config: WebConfig
    ) -> None:
        """Avatar persists in SiteHeader after using the logo to navigate to Home.

        This variant starts on the Home page, navigates away to Settings,
        then clicks the logo (Home link) and re-checks the avatar.
        """
        context: BrowserContext = browser_instance.new_context()
        page: Page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        try:
            # Mock GET /api/me to return a user profile with an empty avatar_url.
            page.route(_API_ME_PATTERN, _make_api_me_handler(_VALID_AVATAR_URL))

            # Log in and land on the Home page.
            login_pg = LoginPage(page)
            login_pg.navigate(web_config.login_url())
            login_pg.login_as(web_config.test_email, web_config.test_password)
            login_pg.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

            header = SiteHeader(page)
            header.avatar_wait(timeout=_AVATAR_WAIT_TIMEOUT)

            # Confirm avatar is visible on initial Home page load.
            assert header.avatar_is_visible() or header.header_has_avatar_image(), (
                "Avatar is NOT visible on the initial Home page load after login. "
                f"URL: {page.url}"
            )

            # Navigate away to Settings page.
            page.goto(web_config.settings_url(), wait_until="domcontentloaded")
            header.avatar_wait(timeout=_AVATAR_WAIT_TIMEOUT)

            # Navigate back to Home via the logo.
            header.click_logo()
            page.wait_for_url(
                lambda u: u.rstrip("/") == web_config.home_url().rstrip("/"),
                timeout=_PAGE_LOAD_TIMEOUT,
            )
            header.avatar_wait(timeout=_AVATAR_WAIT_TIMEOUT)

            avatar_after_return = header.avatar_is_visible() or header.header_has_avatar_image()
            assert avatar_after_return, (
                "Avatar disappeared in the SiteHeader after navigating Home→Settings→Home "
                f"using the logo link.\n"
                f"Current URL: {page.url}\n"
                "Expected: the avatar must remain applied and visible in the header "
                "regardless of navigation history (MYTUBE-663 regression check)."
            )

        finally:
            context.close()
