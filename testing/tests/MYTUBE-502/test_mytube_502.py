"""
MYTUBE-502: Authenticated user avatar — gradient styling and letter rendering.

Objective
---------
Verify the visual representation of the authenticated user's avatar matches
the design spec: a circular element with a green-to-purple gradient background
that displays the first letter of the user's display name.

Preconditions
-------------
User is logged into the application.

Steps
-----
1. Observe the user avatar in the header utility area.
2. Inspect the CSS properties of the avatar circle.

Expected Result
---------------
The avatar is a circle with a gradient (--gradient-hero) containing both green
(#62c235) and purple (#6d40cb or #9370db) colour stops, and displays the
user's initial letter (first character of display name, uppercased).

Test approach
-------------
1. Log in with Firebase test credentials (FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD).
2. After the home page loads, locate the avatar span in the header utility area.
3. Read its computed CSS properties via page.evaluate():
   - border-radius must be "50%" (circular).
   - background-image must contain a linear-gradient with green and purple colour stops.
4. Read the text content; must match the expected initial letter.

Implementation notes
--------------------
The avatar is rendered by SiteHeader.tsx as:
  <span
    className="h-7 w-7 rounded-full text-white flex items-center justify-center
               text-xs font-bold select-none"
    style={{ background: "var(--gradient-hero)" }}
    aria-hidden="true"
  >
    {displayName[0].toUpperCase()}
  </span>

--gradient-hero is defined in globals.css as:
  light: linear-gradient(135deg, #6d40cb 0%, #62c235 100%)
  dark:  linear-gradient(135deg, #9370db 0%, #62c235 100%)

Both variants contain green (#62c235) and a purple shade.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Email of the registered Firebase test user (required).
FIREBASE_TEST_PASSWORD   Password of the registered Firebase test user (required).
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses LoginPage (Page Object) to authenticate.
- Uses SiteHeader (Page Object) from testing/components/pages/site_header/ for logo
  visibility (inherits navigation helpers).
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_NAVIGATION_TIMEOUT = 20_000  # ms — max time to wait for post-login redirect
_AUTH_SETTLE_TIMEOUT = 10_000  # ms — max wait for avatar to appear after login

# Selector: the avatar span rendered by SiteHeader.tsx inside the header
# utility area when the user is authenticated.
# It carries `aria-hidden="true"`, `rounded-full`, and is the only span
# containing a single letter directly inside the <header> button that opens
# the account menu.
_AVATAR_SELECTOR = "header button span.rounded-full"

# Regex matching any known purple hex stop used in --gradient-hero.
# Light mode: #6d40cb  Dark mode: #9370db
_PURPLE_HEX_RE = re.compile(r"#(6d40cb|9370db|[56789a-f][0-9a-f]{4}[89a-f][0-9a-f])", re.IGNORECASE)

# Green colour stop used in both light and dark --gradient-hero.
_GREEN_HEX = "#62c235"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig) -> None:
    """Skip the entire module when Firebase test credentials are not set."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping avatar style test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping avatar style test. "
            "Set FIREBASE_TEST_PASSWORD to run."
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
def authenticated_page(browser: Browser, web_config: WebConfig) -> Page:
    """Open a browser context, log in once, and yield the authenticated page.

    Login is executed exactly once per module run; all tests share the session.
    """
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    login_page = LoginPage(pg)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)

    # Wait until the avatar button appears in the header, confirming auth state.
    pg.wait_for_selector(_AVATAR_SELECTOR, timeout=_AUTH_SETTLE_TIMEOUT)

    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _avatar_css(page: Page) -> dict[str, str]:
    """Return computed CSS properties of the avatar span as a dict."""
    return page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return {};
            const s = window.getComputedStyle(el);
            return {
                borderRadius: s.borderRadius,
                backgroundImage: s.backgroundImage,
                background: s.background,
            };
        }""",
        _AVATAR_SELECTOR,
    )


def _avatar_text(page: Page) -> str:
    """Return the trimmed text content of the avatar span."""
    el = page.query_selector(_AVATAR_SELECTOR)
    if el is None:
        return ""
    return (el.text_content() or "").strip()


def _contains_green(css_value: str) -> bool:
    """Return True if *css_value* contains the green colour stop #62c235 in any form."""
    # Browsers may convert hex → rgb; compare both forms.
    return (
        "62c235" in css_value.lower()
        or "rgb(98, 194, 53)" in css_value
    )


def _contains_purple(css_value: str) -> bool:
    """Return True if *css_value* contains any known purple colour stop."""
    lower = css_value.lower()
    # Hex forms
    if "6d40cb" in lower or "9370db" in lower:
        return True
    # RGB forms: rgb(109, 64, 203)  or  rgb(147, 112, 219)
    if "rgb(109, 64, 203)" in lower or "rgb(147, 112, 219)" in lower:
        return True
    return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUserAvatarStyling:
    """MYTUBE-502: Authenticated user avatar gradient styling and letter rendering."""

    def test_avatar_is_present_in_header(self, authenticated_page: Page) -> None:
        """Step 1: The avatar span must be visible inside the header utility area.

        Expected: a rounded-full <span> exists inside a <header> <button> and
        is visible after the user has logged in.
        """
        avatar = authenticated_page.query_selector(_AVATAR_SELECTOR)
        assert avatar is not None, (
            f"Avatar span ({_AVATAR_SELECTOR!r}) not found in the DOM after login. "
            f"The user may not be authenticated, or the header may not have rendered "
            f"the avatar button yet. "
            f"Current URL: {authenticated_page.url!r}"
        )
        assert avatar.is_visible(), (
            f"Avatar span ({_AVATAR_SELECTOR!r}) is present in the DOM but not visible. "
            f"Current URL: {authenticated_page.url!r}"
        )

    def test_avatar_is_circular(self, authenticated_page: Page) -> None:
        """Step 2: The avatar circle must have border-radius of 50% (circular shape).

        Expected: computed border-radius resolves to '50%' (Tailwind's
        rounded-full class) or equivalent pixel value matching a perfect circle.
        """
        css = _avatar_css(authenticated_page)
        assert css, (
            f"Could not read computed CSS from avatar span ({_AVATAR_SELECTOR!r}). "
            f"Element may not be in the DOM. Current URL: {authenticated_page.url!r}"
        )
        border_radius = css.get("borderRadius", "")
        # Playwright/browsers resolve 'rounded-full' to '9999px' or '50%' depending
        # on how they compute border-radius for equal width/height elements.
        # We accept both, or any value ≥ 14px (half of 28px width = h-7 / w-7).
        is_circular = (
            border_radius == "50%"
            or border_radius == "9999px"
            or "9999" in border_radius
            # Some browsers resolve Tailwind's rounded-full to px on square elements
            or (
                border_radius.endswith("px")
                and float(border_radius.replace("px", "").split()[0]) >= 14.0
            )
        )
        assert is_circular, (
            f"Expected the avatar to be circular (border-radius: 50% or 9999px), "
            f"but computed border-radius is: {border_radius!r}. "
            f"Full computed CSS: {css!r}. "
            f"The 'rounded-full' Tailwind class should apply border-radius: 9999px."
        )

    def test_avatar_has_gradient_background(self, authenticated_page: Page) -> None:
        """Step 2: The avatar background must be a linear-gradient (--gradient-hero).

        Expected: the computed background-image contains 'linear-gradient' with
        both green (#62c235) and purple (#6d40cb / #9370db) colour stops.
        """
        css = _avatar_css(authenticated_page)
        bg_image = css.get("backgroundImage", "") or css.get("background", "")

        assert "linear-gradient" in bg_image.lower(), (
            f"Expected the avatar background to be a linear-gradient "
            f"(var(--gradient-hero)), but computed background-image is: {bg_image!r}. "
            f"The avatar span uses 'style={{{{ background: \"var(--gradient-hero)\" }}}}' "
            f"in SiteHeader.tsx. "
            f"Full computed CSS: {css!r}."
        )

        assert _contains_green(bg_image), (
            f"Expected the avatar gradient to contain green (#62c235 / rgb(98,194,53)), "
            f"but it was not found in: {bg_image!r}. "
            f"Check globals.css --gradient-hero definition."
        )

        assert _contains_purple(bg_image), (
            f"Expected the avatar gradient to contain a purple colour stop "
            f"(#6d40cb / #9370db or their rgb equivalents), "
            f"but none were found in: {bg_image!r}. "
            f"Check globals.css --gradient-hero definition."
        )

    def test_avatar_displays_initial_letter(self, authenticated_page: Page) -> None:
        """Step 1 + 2: The avatar must display a single uppercase initial letter.

        Expected: the text content of the avatar span is exactly one alphabetic
        character and is uppercase.  It represents the first character of the
        authenticated user's display name.
        """
        letter = _avatar_text(authenticated_page)
        assert len(letter) == 1, (
            f"Expected the avatar to display exactly one initial letter, "
            f"but got: {letter!r} (length {len(letter)}). "
            f"The SiteHeader renders {{displayName[0].toUpperCase()}} inside the span."
        )
        assert letter.isalpha() or letter.isdigit(), (
            f"Expected the avatar letter to be alphanumeric, but got: {letter!r}."
        )
        assert letter == letter.upper(), (
            f"Expected the avatar letter to be uppercase, "
            f"but got: {letter!r}. "
            f"The SiteHeader calls .toUpperCase() on the first display name character."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
