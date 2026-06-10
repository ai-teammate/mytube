"""
MYTUBE-666: User without custom image on Home page — default avatar placeholder is rendered.

Objective
---------
Verify that the default avatar placeholder (gradient background with the user's
initial) is correctly displayed on the Home page for users who have not uploaded
a custom avatar image, confirming the MYTUBE-663 bug fix does not regress for
the default-avatar state.

Preconditions
-------------
User is authenticated and has no custom avatar image (avatarUrl is empty).

Steps
-----
1. Open the application and navigate to the Home page.
2. Inspect the user avatar area in the SiteHeader.

Expected Result
---------------
- The default avatar placeholder span (``header button span.rounded-full``) is
  visible in the site header.
- No ``<img>`` avatar element is present (confirming no custom image is shown).
- The avatar span has a non-trivial background that includes a gradient
  (the gradient placeholder is rendered, not a blank element).
- The avatar span displays the user's initial letter (first character of the
  email / display name).

Implementation notes
--------------------
- GET /api/me is mocked to return ``{"username": "testuser666", "avatar_url": ""}``
  so that the authenticated UI renders without a custom image.
- Firebase credentials (FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD) are
  required; the test is skipped when they are absent.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Email for the test Firebase account (required).
FIREBASE_TEST_PASSWORD   Password for the test Firebase account (required).
PLAYWRIGHT_HEADLESS      Run headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-666/test_mytube_666.py -v
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest
from playwright.sync_api import BrowserContext, Page, Route, Request, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.site_header.site_header import SiteHeader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_LOGIN_TIMEOUT = 20_000       # ms
_AVATAR_WAIT_TIMEOUT = 10_000  # ms

_TEST_USERNAME = "testuser666"
_API_ME_PATTERN = re.compile(r"/api/me(\?.*)?$")

# ---------------------------------------------------------------------------
# Route handler — GET /api/me mock with empty avatar_url
# ---------------------------------------------------------------------------

_PROFILE_NO_AVATAR: bytes = json.dumps(
    {"username": _TEST_USERNAME, "avatar_url": ""}
).encode()


def _api_me_no_avatar_handler(route: Route, request: Request) -> None:
    """Serve a user profile with no avatar for GET /api/me."""
    if request.method == "GET":
        route.fulfill(
            status=200,
            content_type="application/json",
            body=_PROFILE_NO_AVATAR,
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
    """Skip the entire module when Firebase test credentials are absent."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-666 test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-666. "
            "Set FIREBASE_TEST_PASSWORD to run."
        )


@pytest.fixture(scope="module")
def home_page_context(web_config: WebConfig) -> dict:
    """
    Authenticate, mock GET /api/me with empty avatar_url, navigate to the
    Home page, and collect avatar observations.

    Returns a dict with the captured state so that individual test functions
    can share a single browser session.
    """
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        context: BrowserContext = browser.new_context()
        page: Page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        # Intercept GET /api/me — serve empty avatar_url so the UI renders
        # the gradient placeholder instead of a custom image.
        page.route(_API_ME_PATTERN, _api_me_no_avatar_handler)

        try:
            # --- Login ---
            login_pg = LoginPage(page)
            login_pg.navigate(web_config.login_url())
            login_pg.login_as(web_config.test_email, web_config.test_password)
            login_pg.wait_for_navigation_to(
                web_config.home_url(), timeout=_LOGIN_TIMEOUT
            )

            # --- Ensure we are on the Home page ---
            if not page.url.rstrip("/").endswith(web_config.base_url.rstrip("/")):
                page.goto(web_config.home_url(), wait_until="domcontentloaded",
                          timeout=_PAGE_LOAD_TIMEOUT)

            header = SiteHeader(page)

            # Wait for the avatar placeholder to appear (confirms auth is resolved).
            header.avatar_wait(timeout=_AVATAR_WAIT_TIMEOUT)

            result = {
                "avatar_visible": header.avatar_is_visible(),
                "has_avatar_image": header.header_has_avatar_image(),
                "avatar_text": header.avatar_text(),
                "avatar_css": header.avatar_css(),
                "page_url": page.url,
            }
        finally:
            context.close()
            browser.close()

    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDefaultAvatarPlaceholderOnHomePage:
    """MYTUBE-666: Default avatar placeholder is rendered on the Home page."""

    def test_avatar_placeholder_span_is_visible(self, home_page_context: dict) -> None:
        """The gradient placeholder span must be visible in the site header."""
        assert home_page_context["avatar_visible"], (
            "The avatar placeholder span ('header button span.rounded-full') "
            "is NOT visible in the site header on the Home page for an "
            "authenticated user with no custom avatar.\n"
            f"Page URL: {home_page_context['page_url']}\n"
            "Expected: the gradient circle with the user's initial should render "
            "in place of a custom avatar image."
        )

    def test_no_custom_avatar_image_shown(self, home_page_context: dict) -> None:
        """No <img> avatar element should be present when avatarUrl is empty."""
        assert not home_page_context["has_avatar_image"], (
            "An <img> avatar element ('header button img.rounded-full') IS visible "
            "even though avatarUrl is empty. The default placeholder should be "
            "rendered instead of a custom image.\n"
            f"Page URL: {home_page_context['page_url']}"
        )

    def test_avatar_placeholder_displays_initial(self, home_page_context: dict) -> None:
        """The placeholder span must contain at least one non-whitespace character (the initial)."""
        initial = home_page_context["avatar_text"]
        assert initial.strip(), (
            "The avatar placeholder span is empty — it should display the user's "
            f"initial letter.\nGot text: {initial!r}\n"
            f"Page URL: {home_page_context['page_url']}"
        )
        assert len(initial.strip()) == 1, (
            f"Expected a single initial letter in the avatar placeholder, "
            f"got: {initial!r}.\n"
            f"Page URL: {home_page_context['page_url']}"
        )

    def test_avatar_placeholder_has_gradient_background(self, home_page_context: dict) -> None:
        """The avatar span's background must include a gradient (not plain colour)."""
        css = home_page_context["avatar_css"]
        background_image: str = css.get("backgroundImage", "")
        background: str = css.get("background", "")
        combined = (background_image + " " + background).lower()

        assert "gradient" in combined, (
            "The avatar placeholder span does not have a gradient background. "
            "Expected a gradient circle (the MyTube brand placeholder) to be "
            "applied when avatarUrl is empty.\n"
            f"backgroundImage: {background_image!r}\n"
            f"background: {background!r}\n"
            f"Page URL: {home_page_context['page_url']}"
        )
