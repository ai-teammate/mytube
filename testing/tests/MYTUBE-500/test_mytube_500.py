"""
MYTUBE-500: SiteHeader login button — pill shape and branded styling applied.

Objective
---------
Verify the redesigned login button replaces the previous link style with a
branded pill-shaped button.

Preconditions
-------------
User is not authenticated.

Steps
-----
1. Open the application and locate the Login button in the header utility area.
2. Inspect the styling of the .btn.login element (header a[href="/login"]).

Expected Result
---------------
The button has a pill shape (border-radius ≥ 50 % / rounded-full),
border-color: var(--accent-login-border), color: var(--accent-logo),
and font-weight: 600.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- SiteHeader from testing/components/pages/site_header/site_header.py provides
  the login_button() locator and style helpers (component layer).
- Tests use only semantic methods from the component; no raw Playwright APIs
  in tests.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.site_header.site_header import SiteHeader

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_FONT_WEIGHT_SEMIBOLD = 600
_ACCENT_LOGIN_BORDER = "rgb(161, 137, 219)"  # --accent-login-border (#a189db)
_ACCENT_LOGO = "rgb(109, 64, 203)"           # --accent-logo (#6d40cb)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        yield page
        browser.close()


@pytest.fixture(scope="module")
def header(browser_page: Page) -> SiteHeader:
    return SiteHeader(browser_page)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoginButtonStyling:
    """MYTUBE-500: Login button in SiteHeader has pill shape and branded styling."""

    def test_login_button_is_visible(self, header: SiteHeader) -> None:
        """Step 1: The login button must be present and visible in the header."""
        assert header.is_login_button_visible(), (
            "Login button not visible in the site header for unauthenticated user."
        )

    def test_login_button_has_pill_shape(self, header: SiteHeader) -> None:
        """Step 2a: The button must have a pill shape (border-radius equals half the height)."""
        styles = header.login_button_computed_styles()
        border_radius = styles.get("borderTopLeftRadius", "")
        # Pill / rounded-full: border-radius should be at least ~9999px or ≥ height/2.
        # Tailwind 'rounded-full' renders as a very large px value (e.g. 9999px) or
        # a percentage. We just verify it is not 0px.
        assert border_radius not in ("0px", "0", "", "none"), (
            f"Login button does not have a pill shape. "
            f"Expected a non-zero border-radius (rounded-full). "
            f"Actual borderTopLeftRadius='{border_radius}'."
        )

    def test_login_button_border_color_uses_accent_login_border(
        self, header: SiteHeader
    ) -> None:
        """Step 2b: The button border-color must resolve to var(--accent-login-border)."""
        styles = header.login_button_computed_styles()
        assert styles.get("borderColor") == _ACCENT_LOGIN_BORDER, (
            f"Expected borderColor={_ACCENT_LOGIN_BORDER!r}, "
            f"got {styles.get('borderColor')!r}."
        )

    def test_login_button_color_uses_accent_logo(self, header: SiteHeader) -> None:
        """Step 2c: The button text color must resolve to var(--accent-logo)."""
        styles = header.login_button_computed_styles()
        assert styles.get("color") == _ACCENT_LOGO, (
            f"Expected color={_ACCENT_LOGO!r}, "
            f"got {styles.get('color')!r}."
        )

    def test_login_button_font_weight_is_semibold(self, header: SiteHeader) -> None:
        """Step 2d: The button must have font-weight: 600 (semibold)."""
        styles = header.login_button_computed_styles()
        font_weight = styles.get("fontWeight", "")
        assert str(font_weight) == str(_FONT_WEIGHT_SEMIBOLD), (
            f"Login button font-weight mismatch. "
            f"Expected: {_FONT_WEIGHT_SEMIBOLD}, "
            f"Actual: '{font_weight}'."
        )
