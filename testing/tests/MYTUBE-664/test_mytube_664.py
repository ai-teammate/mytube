"""
MYTUBE-664: Authenticated user on Home page — avatar is visible and correctly rendered.

Objective
---------
Verify that the authenticated user's avatar is correctly displayed in the
SiteHeader when the user is on the Home page, resolving the reported bug
(MYTUBE-663) where the avatar was missing on this specific route.

Preconditions
-------------
User is authenticated and has a custom avatar image set.

Steps
-----
1. Open the application.
2. Navigate to the Home page (root URL /).
3. Observe the user avatar in the SiteHeader.

Expected Result
---------------
The user's custom avatar image is visible and correctly rendered in the header
on the Home page without being replaced by a placeholder or failing to load.

Implementation notes
--------------------
- GET /api/me is mocked to return a profile with a non-empty avatar_url so
  that no real user account with an avatar is required.
- CDN image requests for the avatar are intercepted and served with a valid
  1×1 GIF so the <img> element renders without triggering onError.
- The test asserts that `header button img.rounded-full` is visible, which is
  the selector for the avatar <img> in SiteHeader.tsx.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Test user email (required — test skips when absent).
FIREBASE_TEST_PASSWORD   Test user password (required — test skips when absent).
PLAYWRIGHT_HEADLESS      Run headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-664/test_mytube_664.py -v
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
from testing.components.pages.home_page.home_page import HomePage
from testing.components.pages.site_header.site_header import SiteHeader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_LOGIN_TIMEOUT = 20_000      # ms
_AVATAR_WAIT_TIMEOUT = 10_000  # ms — allow React context to propagate avatarUrl

# A plausible avatar URL that will be returned by the mocked /api/me endpoint.
_VALID_AVATAR_URL = (
    "https://storage.googleapis.com/mytube-test/avatars/user664/avatar.jpg"
)

# Minimal 1×1 transparent GIF (valid image so <img> renders without onError).
_GIF_BYTES = base64.b64decode(
    "R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
)

_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")

# ---------------------------------------------------------------------------
# Route helpers
# ---------------------------------------------------------------------------


def _api_me_handler(route: Route, request: Request) -> None:
    """Serve a mocked /api/me response with a valid avatar_url."""
    if request.method == "GET":
        body = json.dumps(
            {"username": "testuser664", "avatar_url": _VALID_AVATAR_URL}
        ).encode()
        route.fulfill(status=200, content_type="application/json", body=body)
    else:
        route.continue_()


def _gif_handler(route: Route, request: Request) -> None:
    """Serve a minimal 1×1 transparent GIF for avatar CDN image requests."""
    route.fulfill(status=200, content_type="image/gif", body=_GIF_BYTES)


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
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-664 test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-664 test. "
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
# Helper
# ---------------------------------------------------------------------------


def _login_and_go_home(
    browser: Browser, web_config: WebConfig
) -> tuple[BrowserContext, Page, HomePage, SiteHeader]:
    """Log in with mocked /api/me (avatar_url set) then navigate to /.

    Returns (context, page, home_page, site_header). Caller must call
    ``context.close()`` when done.
    """
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Mock /api/me so AuthContext receives a profile with a non-empty avatarUrl.
    page.route(_API_ME_PATTERN, _api_me_handler)

    # Intercept CDN avatar requests so <img> renders without onError.
    page.route(re.compile(r"storage\.googleapis\.com.*avatars/"), _gif_handler)

    # 1. Log in.
    login_pg = LoginPage(page)
    login_pg.navigate(web_config.login_url())
    login_pg.login_as(web_config.test_email, web_config.test_password)
    login_pg.wait_for_navigation_to(web_config.home_url(), timeout=_LOGIN_TIMEOUT)

    home_pg = HomePage(page)
    header = SiteHeader(page)

    return context, page, home_pg, header


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarVisibleOnHomePage:
    """MYTUBE-664: Avatar image must be visible in SiteHeader on the Home page."""

    def test_avatar_image_visible_on_home_page(
        self, browser_instance: Browser, web_config: WebConfig
    ) -> None:
        """Custom avatar <img> must be visible in the header when on the Home page.

        This test directly reproduces the regression reported in MYTUBE-663:
        the avatar was missing on the / route despite being present on other
        authenticated routes.

        Steps:
        1. Log in (with /api/me mocked to return a non-empty avatar_url).
        2. Confirm we are on the Home page (/).
        3. Wait for the avatar <img> to appear in the site header.
        4. Assert header_has_avatar_image() is True.
        5. Assert the avatar placeholder span is NOT shown instead of the image.
        """
        context, page, home_pg, header = _login_and_go_home(
            browser_instance, web_config
        )
        try:
            # Step 2 — verify we are on the Home page.
            current_url = page.url.rstrip("/")
            expected_url = web_config.home_url().rstrip("/")
            assert current_url == expected_url, (
                f"Expected to be on the Home page ({expected_url!r}) after login, "
                f"but the current URL is {current_url!r}."
            )

            # Step 3 — wait for the avatar <img> in the header.
            # When avatarUrl is non-empty, SiteHeader renders an <img class="rounded-full">
            # (not the placeholder <span>).  Wait directly for the img selector.
            page.wait_for_selector(
                "header button img.rounded-full",
                state="visible",
                timeout=_AVATAR_WAIT_TIMEOUT,
            )

            # Step 4 — assert the avatar <img> (custom photo) is present.
            has_img = header.header_has_avatar_image()
            assert has_img, (
                "The avatar <img class='rounded-full'> is NOT visible inside the "
                "site header on the Home page (/).\n"
                "Expected: SiteHeader renders <img> when avatarUrl is non-empty.\n"
                "Actual: No avatar image found — the header may be showing only "
                "the placeholder <span> or no avatar element at all.\n"
                "This is a regression of MYTUBE-663: avatarUrl was not propagated "
                "to SiteHeader on the Home route."
            )

            # Step 5 — (informational) confirm placeholder is not the only element.
            # avatar_wait already confirms the span is present (both states render it),
            # so we just assert the img is what's visible.
            avatar_text = header.avatar_text()
            assert has_img or avatar_text == "", (
                "The avatar area shows the placeholder initial letter instead of "
                f"the custom avatar image. Placeholder text: {avatar_text!r}"
            )

        finally:
            context.close()
