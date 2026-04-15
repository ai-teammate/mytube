"""
MYTUBE-610: Enter valid avatar URL — live image preview is displayed.

Objective
---------
Verify that a live preview of the avatar image is displayed when a valid URL is
entered in the Avatar URL field on the Account Settings page.

Preconditions
-------------
User is on the Account Settings page (/settings).

Steps
-----
1. Log in as the CI test user.
2. Navigate to /settings.
3. Locate the "Avatar URL" input field.
4. Enter a valid image URL
   (https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png).
5. Verify an <img> element appears inside the avatar preview container.

Expected Result
---------------
An <img> element appears below the Avatar URL input. The image:
- Has src matching the provided URL.
- Has class ``rounded-full`` (circular shape).
- Has class ``w-16 h-16`` (64×64 px).
- Has class ``object-cover`` (fill fitting).

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Email for the CI test Firebase user.
FIREBASE_TEST_PASSWORD   Password for the CI test Firebase user.
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root
------------------
    pytest testing/tests/MYTUBE-610/test_mytube_610.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage
from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_AVATAR_URL = (
    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/25.png"
)

_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Credentials guard
# ---------------------------------------------------------------------------

_config = WebConfig()
_FIREBASE_EMAIL = _config.test_email
_FIREBASE_PASSWORD = _config.test_password


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_avatar_url_shows_live_preview() -> None:
    """Entering a valid avatar URL in Account Settings displays a live <img> preview."""

    if not _FIREBASE_EMAIL or not _FIREBASE_PASSWORD:
        pytest.skip(
            "FIREBASE_TEST_EMAIL and/or FIREBASE_TEST_PASSWORD not set — "
            "skipping MYTUBE-610 avatar preview test."
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=_config.headless,
            slow_mo=_config.slow_mo,
        )
        context = browser.new_context()
        page = context.new_page()

        try:
            login_page = LoginPage(page)
            settings_page = SettingsPage(page)

            # Step 1 — Log in.
            login_page.navigate(_config.login_url())
            login_page.wait_for_form(timeout=_PAGE_LOAD_TIMEOUT)
            login_page.login_as(_FIREBASE_EMAIL, _FIREBASE_PASSWORD)

            # Wait for redirect away from /login (auth completes).
            page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=_PAGE_LOAD_TIMEOUT,
            )

            # Step 2 — Navigate to /settings.
            settings_page.navigate(_config.base_url)

            # Step 3 — Wait for the initial profile fetch to complete so that
            # it does not overwrite the avatar URL we are about to type.
            # The profile fetch populates the username field; we wait until
            # the field has any value (or the request finishes with empty data,
            # in which case waitForFunction times out gracefully and we proceed).
            try:
                page.wait_for_function(
                    "() => document.querySelector('#username')?.value.length > 0",
                    timeout=8_000,
                )
            except Exception:
                # Profile may have loaded with an empty username, or may have
                # failed. Either way we continue — the avatar URL field is what
                # we care about.
                pass

            # Step 4 — Enter a valid image URL.
            settings_page.fill_avatar_url(_VALID_AVATAR_URL)

            # Step 5 — Verify the preview <img> appears.
            settings_page.wait_for_avatar_preview(timeout=10_000)

            assert settings_page.is_avatar_preview_visible(), (
                "Avatar preview <img> is not visible after entering a valid URL."
            )

            # Verify src matches the URL we entered.
            actual_src = settings_page.get_avatar_preview_src()
            assert actual_src == _VALID_AVATAR_URL, (
                f"Avatar preview src mismatch.\n"
                f"  Expected: {_VALID_AVATAR_URL!r}\n"
                f"  Actual:   {actual_src!r}"
            )

            # Verify CSS classes: rounded-full, w-16, h-16, object-cover.
            img_classes = settings_page.get_avatar_preview_classes()
            for expected_class in ("rounded-full", "w-16", "h-16", "object-cover"):
                assert expected_class in img_classes, (
                    f"Avatar preview <img> is missing class '{expected_class}'. "
                    f"Actual classes: {img_classes!r}"
                )

            # Verify the computed rendered size is approximately 64×64 px.
            width, height = settings_page.get_avatar_preview_computed_size()
            assert 60 <= width <= 70, (
                f"Avatar preview width is {width}px; expected ~64px (w-16)."
            )
            assert 60 <= height <= 70, (
                f"Avatar preview height is {height}px; expected ~64px (h-16)."
            )

            # Verify object-fit is 'cover'.
            object_fit = settings_page.get_avatar_img_object_fit()
            assert object_fit == "cover", (
                f"Avatar preview object-fit is {object_fit!r}; expected 'cover'."
            )

        finally:
            context.close()
            browser.close()
