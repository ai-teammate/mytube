"""
MYTUBE-305: User profile loading failure — 'Could not load profile' message is displayed
and session is cleared.

Objective
---------
Verify that the application displays a graceful error message and clears session
metadata even when user profile data fails to load from Firestore (simulated via a
mocked 500 Internal Server Error response from the profile API endpoint).

Preconditions
-------------
Application is deployed to a static environment (GitHub Pages). A user document
exists in Firestore (or any username is navigable via the SPA fallback).

Steps
-----
1. Navigate to a valid user profile URL (e.g., /u/ci-test).
2. Intercept the Firestore/API request for the user document and mock a 500 Internal
   Server Error response, simulating a "Permission Denied" or storage failure.
3. Observe the rendered page content.
4. Check the value of sessionStorage.getItem("__spa_username").

Expected Result
---------------
The page displays the error message: "Could not load profile. Please try again later."
The username heading (h1), avatar, and video grid are NOT rendered.
The sessionStorage key __spa_username is cleared (returns null) after the component
mounts.

Architecture
------------
- Uses Playwright sync API (page.route) to intercept GET /api/users/<username> → 500.
- Uses UserProfilePage (Page Object) for all assertions.
- Uses WebConfig from testing/core/config/web_config.py for environment configuration.
- Module-scoped browser / function-scoped context to keep tests isolated.

Environment Variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Used to derive the CI test username (prefix before '@').
                         Default username: ci-test
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys
from typing import List, Tuple

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.user_profile_page.user_profile_page import UserProfilePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms — initial navigation + SPA redirect
_ERROR_STATE_TIMEOUT = 20_000  # ms — wait for error message to appear

# Playwright route pattern that matches GET /api/users/<username> but NOT
# /api/users/<username>/playlists (single * never matches /).
_PROFILE_API_PATTERN = "**/api/users/*"

# The sessionStorage key written by public/404.html and read by UserProfilePageClient.
_SPA_SESSION_KEY = "__spa_username"

# The exact error message expected when the profile API fails.
_EXPECTED_ERROR_MSG = "Could not load profile. Please try again later."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def test_username(web_config: WebConfig) -> str:
    """Derive the CI test username from FIREBASE_TEST_EMAIL (prefix before '@')."""
    email = web_config.test_email or "ci-test@mytube.test"
    return email.split("@")[0]


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def error_page(
    browser: Browser,
    web_config: WebConfig,
    test_username: str,
) -> Tuple[UserProfilePage, Page, List[str]]:
    """Load the user profile page with the profile API intercepted to return 500.

    Sets up Playwright route interception for GET /api/users/<username> before
    navigation.  This simulates a Firestore "Permission Denied" / server error,
    causing UserProfilePageClient.tsx to enter the error state.

    Yields
    ------
    (UserProfilePage, raw_Page, js_errors_list)
    """
    ctx: BrowserContext = browser.new_context()
    pg: Page = ctx.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    js_errors: List[str] = []
    pg.on("pageerror", lambda err: js_errors.append(str(err)))

    # Intercept the profile fetch: GET /api/users/<username> → 500.
    # The single-star wildcard (*) in Playwright does NOT match '/', so this
    # pattern matches /api/users/ci-test but NOT /api/users/ci-test/playlists.
    pg.route(
        _PROFILE_API_PATTERN,
        lambda route: route.fulfill(
            status=500,
            content_type="application/json",
            body='{"error": "Internal Server Error — simulated Firestore failure"}',
        ),
    )

    profile_page = UserProfilePage(pg)

    try:
        # Navigate via the SPA fallback flow (404.html → /u/_/ → React reads
        # __spa_username from sessionStorage and calls the profile API).
        profile_page.navigate(web_config.base_url, test_username)

        # Wait until the error state is rendered (role=alert appears).
        profile_page.is_error_visible(timeout=_ERROR_STATE_TIMEOUT)

        yield profile_page, pg, js_errors

    finally:
        ctx.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_session_storage_value(page: Page, key: str) -> str | None:
    """Return the value stored under *key* in sessionStorage, or None."""
    return page.evaluate(f"sessionStorage.getItem({key!r})")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProfileLoadingFailure:
    """MYTUBE-305: Profile displays error and clears session when API returns 500."""

    def test_error_message_is_displayed(
        self,
        error_page: Tuple[UserProfilePage, Page, List[str]],
    ) -> None:
        """Step 3: The exact error message must be visible after the API fails.

        Expected: a [role=alert] element containing exactly
        "Could not load profile. Please try again later." is rendered.
        """
        profile_page, pg, _ = error_page

        assert profile_page.is_error_visible(timeout=5_000), (
            f"Expected [role=alert] with the error message to be visible after "
            f"the profile API returned 500, but no alert element was found. "
            f"Current URL: {pg.url!r}. "
            f"Page body (first 400 chars): {(pg.locator('body').text_content() or '')[:400]!r}"
        )

        actual_msg = profile_page.get_error_message()
        assert actual_msg == _EXPECTED_ERROR_MSG, (
            f"Expected error message: {_EXPECTED_ERROR_MSG!r}. "
            f"Actual error message: {actual_msg!r}. "
            f"The component may have changed the error text or is not entering "
            f"the error state when the API returns 500."
        )

    def test_username_heading_not_rendered(
        self,
        error_page: Tuple[UserProfilePage, Page, List[str]],
    ) -> None:
        """Step 3: The username <h1> heading must NOT be rendered in the error state.

        Expected: no <h1> element containing the username is visible.
        When the profile API fails, UserProfilePageClient.tsx renders only the
        error message branch — no profile header.
        """
        profile_page, pg, _ = error_page

        heading = profile_page.get_username_heading()
        assert heading is None or heading == "", (
            f"Expected no <h1> username heading when the profile API returns 500, "
            f"but found: {heading!r}. "
            f"Current URL: {pg.url!r}. "
            f"The component may be rendering the profile content instead of the "
            f"error state."
        )

    def test_avatar_not_rendered(
        self,
        error_page: Tuple[UserProfilePage, Page, List[str]],
    ) -> None:
        """Step 3: The user avatar must NOT be rendered in the error state.

        Expected: neither an avatar image nor an avatar initials div is visible.
        """
        profile_page, pg, _ = error_page

        assert not profile_page.is_avatar_visible(), (
            f"Expected avatar to be hidden when the profile API returns 500, "
            f"but an avatar element is still visible. "
            f"Current URL: {pg.url!r}. "
            f"The component may be rendering the profile header alongside the error."
        )

    def test_video_grid_not_rendered(
        self,
        error_page: Tuple[UserProfilePage, Page, List[str]],
    ) -> None:
        """Step 3: The video grid must NOT be rendered in the error state.

        Expected: zero video card links (a[href*='/v/']) are present on the page.
        """
        profile_page, pg, _ = error_page

        video_count = profile_page.get_video_card_count()
        assert video_count == 0, (
            f"Expected 0 video cards when the profile API returns 500, "
            f"but found {video_count} video card(s). "
            f"Current URL: {pg.url!r}. "
            f"The component must not render the video grid in the error state."
        )

    def test_session_storage_cleared(
        self,
        error_page: Tuple[UserProfilePage, Page, List[str]],
    ) -> None:
        """Step 4: sessionStorage.__spa_username must be null after the component mounts.

        Expected: sessionStorage.getItem("__spa_username") returns null.

        The UserProfilePageClient.tsx state initialiser removes the key as soon as
        it reads it (sessionStorage.removeItem("__spa_username")).  This must happen
        even when the subsequent profile API call fails — the key is consumed before
        the fetch starts.
        """
        _, pg, _ = error_page

        stored = _get_session_storage_value(pg, _SPA_SESSION_KEY)
        assert stored is None, (
            f"Expected sessionStorage['{_SPA_SESSION_KEY}'] to be null after the "
            f"component mounted (even though the profile API returned 500), "
            f"but got: {stored!r}. "
            f"The component may not be calling "
            f"sessionStorage.removeItem('{_SPA_SESSION_KEY}') on mount."
        )

    def test_no_uncaught_js_errors(
        self,
        error_page: Tuple[UserProfilePage, Page, List[str]],
    ) -> None:
        """The page must not produce uncaught JS exceptions when the API fails.

        Expected: zero unhandled JS errors/promise rejections are captured.
        The fetch error must be caught inside UserProfilePageClient.tsx and must
        not propagate as an unhandled exception.
        """
        _, _, js_errors = error_page

        assert not js_errors, (
            "Uncaught JS errors were detected after the profile API returned 500:\n"
            + "\n".join(js_errors)
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
