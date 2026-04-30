"""
MYTUBE-611: Enter broken avatar URL — fallback placeholder is displayed.

Objective
---------
Verify that a fallback placeholder is shown when the provided avatar URL fails
to load due to a broken link or CORS block.

Preconditions
-------------
User is on the Account Settings page (/settings).

Steps
-----
1. Log in with a valid Firebase test account.
2. Navigate to /settings.
3. Enter an invalid or broken image URL (e.g., https://invalid-domain.com/missing.jpg)
   into the "Avatar URL" field.
4. Observe the preview area while the browser attempts to load the image.

Expected Result
---------------
The <img> element is hidden upon load error. A grey circular placeholder
containing a generic person icon (SVG) is displayed instead, ensuring the
layout does not break.

Architecture
------------
- LoginPage and SettingsPage Page Objects handle all DOM interactions.
- WebConfig from testing/core/config/web_config.py provides all env vars.
- Playwright sync API via pytest fixtures.
- Credentials required: FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD.

Run from repo root:
    pytest testing/tests/MYTUBE-611/test_mytube_611.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000       # ms — max time for initial page load
_NAVIGATION_TIMEOUT = 25_000      # ms — max time to wait for post-login redirect
_IMAGE_ERROR_TIMEOUT = 15_000     # ms — max time to wait for onError fallback

# A syntactically-valid URL that will definitively fail to load (no such domain).
_BROKEN_AVATAR_URL = "https://invalid-domain-that-does-not-exist.example.com/missing.jpg"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are not provided."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping settings avatar fallback test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping settings avatar fallback test. "
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
def authenticated_page(web_config: WebConfig, browser: Browser) -> Page:
    """Login once and return the page ready for further navigation.

    1. Open a fresh browser context.
    2. Navigate to /login and sign in with the test Firebase account.
    3. Wait for redirect to home page confirming successful auth.
    4. Yield the page for subsequent fixture/test use.
    """
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)

    # Wait for post-login redirect to confirm successful authentication.
    login_page.wait_for_navigation_to(
        web_config.home_url(), timeout=_NAVIGATION_TIMEOUT
    )

    yield page
    context.close()


@pytest.fixture(scope="module")
def settings_page_obj(authenticated_page: Page, web_config: WebConfig) -> SettingsPage:
    """Navigate to /settings and return the SettingsPage object."""
    settings_url = f"{web_config.base_url}/settings/"
    page_obj = SettingsPage(authenticated_page)
    page_obj.navigate(settings_url)
    assert page_obj.is_settings_page_loaded(), (
        f"Settings page did not load within timeout. "
        f"URL navigated to: {settings_url}"
    )
    return page_obj


@pytest.fixture(scope="module")
def broken_url_entered(settings_page_obj: SettingsPage) -> SettingsPage:
    """Enter the broken avatar URL into the Avatar URL field.

    The AvatarPreview component renders as soon as the field is non-empty.
    The browser will attempt to load the image and fire onError, which
    triggers the React fallback (SVG placeholder).
    """
    settings_page_obj.fill_avatar_url(_BROKEN_AVATAR_URL)
    # Wait for the React onError handler to fire and render the SVG fallback.
    settings_page_obj.wait_for_avatar_error_fallback(timeout=_IMAGE_ERROR_TIMEOUT)
    return settings_page_obj


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarFallbackOnBrokenUrl:
    """MYTUBE-611 — AvatarPreview shows grey placeholder when URL fails to load."""

    def test_avatar_preview_container_is_visible(
        self, broken_url_entered: SettingsPage
    ) -> None:
        """The AvatarPreview container (div[role='img']) must be visible.

        When the avatar URL field is non-empty, the settings page renders the
        AvatarPreview component.  The outer container div is always present
        regardless of whether the image loaded or errored.
        """
        assert broken_url_entered.is_avatar_preview_container_visible(timeout=5_000), (
            "The AvatarPreview container (div[role='img'][aria-label='Avatar preview']) "
            "was not visible after entering a broken avatar URL. "
            f"Broken URL used: {_BROKEN_AVATAR_URL}. "
            "Expected: the container is rendered whenever avatar_url is non-empty."
        )

    def test_img_element_is_absent_after_error(
        self, broken_url_entered: SettingsPage
    ) -> None:
        """The <img> element inside AvatarPreview must NOT be in the DOM after error.

        When the image URL fails to load, AvatarPreview's onError handler sets
        React state error=true.  The component's render branch switches from
        '<img>' to '<svg>', so the <img> element is removed from the DOM entirely.
        """
        assert not broken_url_entered.is_avatar_img_present(), (
            "The <img> element is still present in the AvatarPreview container "
            "after the image URL failed to load. "
            f"Broken URL used: {_BROKEN_AVATAR_URL}. "
            "Expected: after onError fires, the <img> is removed and the SVG "
            "placeholder is rendered in its place (React state: error=true)."
        )

    def test_svg_placeholder_is_visible(
        self, broken_url_entered: SettingsPage
    ) -> None:
        """The SVG person-icon placeholder must be visible after the load error.

        AvatarPreview renders an SVG (person icon) when showImage is false
        (i.e. when src is empty or error=true).  This test verifies the SVG
        is present and visible so that the layout does not break on a bad URL.
        """
        assert broken_url_entered.is_avatar_svg_placeholder_visible(timeout=5_000), (
            "The SVG placeholder was NOT visible inside the AvatarPreview container "
            "after the broken image URL failed to load. "
            f"Broken URL used: {_BROKEN_AVATAR_URL}. "
            "Expected: a grey circular container with an SVG person icon is displayed "
            "instead of the failed <img> element."
        )

    def test_avatar_preview_has_grey_background(
        self, broken_url_entered: SettingsPage
    ) -> None:
        """The AvatarPreview container must have the grey background class (bg-gray-200).

        The outer container always carries the grey background styling so that
        the placeholder is visually distinct — the layout must not break on
        a broken image URL.
        """
        assert broken_url_entered.is_avatar_preview_container_has_bg_gray(), (
            "The AvatarPreview container does not have the expected 'bg-gray-200' "
            "Tailwind class after a broken URL was entered. "
            f"Broken URL used: {_BROKEN_AVATAR_URL}. "
            "Expected: the container always carries bg-gray-200 to provide the grey "
            "circular placeholder background."
        )
