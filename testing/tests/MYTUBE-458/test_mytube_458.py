"""
MYTUBE-458: Auth page branding — LogoIcon and wordmark style are consistent

Objective
---------
Ensure the branded logo and "MYTUBE" wordmark are correctly rendered within
the auth card on the /login page.

Steps
-----
1. Open the /login page.
2. Inspect the logo section at the top of the auth card.

Expected Result
---------------
- The LogoIcon SVG component is rendered with dimensions 48×48.
- The "MYTUBE" wordmark text is present and styled with color: var(--accent-logo).

Test approach
-------------
Playwright navigates to the deployed /login page and:
  1. Locates the SVG element inside the `.auth-card` branding area.
  2. Asserts its computed width and height are both 48 px.
  3. Locates the "MYTUBE" wordmark <span> inside the auth card.
  4. Resolves the CSS custom property --accent-logo from the :root element.
  5. Asserts the span's computed color matches the resolved --accent-logo value.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env-var access.
- LoginPage page object from testing/components/pages/login_page/ is used for
  navigation, basic auth-card visibility, and all branding queries.
- Playwright sync API with pytest module-scoped fixtures.
- All Playwright locator/evaluate calls are encapsulated inside LoginPage.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_EXPECTED_LOGO_SIZE_PX = 48


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def login_page_fixture(config: WebConfig) -> LoginPage:
    """Open the /login page and yield the LoginPage component."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo,
        )
        page = browser.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        login_pg = LoginPage(page)
        login_pg.navigate(config.login_url())
        # Wait until the auth form is present in the DOM.
        login_pg.wait_for_form(timeout=_PAGE_LOAD_TIMEOUT)

        yield login_pg

        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthPageBranding:
    """MYTUBE-458: LogoIcon and wordmark are correctly branded on the auth card."""

    # ------------------------------------------------------------------
    # Step 2a — LogoIcon SVG dimensions
    # ------------------------------------------------------------------

    def test_logo_icon_svg_is_present(self, login_page_fixture: LoginPage) -> None:
        """The LogoIcon SVG must exist inside the .auth-card element."""
        count = login_page_fixture.get_logo_svg_count()
        assert count >= 1, (
            "No <svg> element found inside '.auth-card'. "
            "The LogoIcon component is expected to be rendered at the top of "
            "the auth card on the /login page."
        )

    def test_logo_icon_width_is_48px(self, login_page_fixture: LoginPage) -> None:
        """The LogoIcon SVG must have a computed width of 48 px.

        AuthCardLogo passes style={{ width: 48, height: 48 }} to LogoIcon,
        which forwards it to the underlying <svg> element.
        """
        width = login_page_fixture.get_logo_svg_width()
        assert width == _EXPECTED_LOGO_SIZE_PX, (
            f"LogoIcon SVG computed width is {width} px, expected {_EXPECTED_LOGO_SIZE_PX} px. "
            "AuthCardLogo must pass style={{{{ width: 48, height: 48 }}}} to <LogoIcon>."
        )

    def test_logo_icon_height_is_48px(self, login_page_fixture: LoginPage) -> None:
        """The LogoIcon SVG must have a computed height of 48 px."""
        height = login_page_fixture.get_logo_svg_height()
        assert height == _EXPECTED_LOGO_SIZE_PX, (
            f"LogoIcon SVG computed height is {height} px, expected {_EXPECTED_LOGO_SIZE_PX} px. "
            "AuthCardLogo must pass style={{{{ width: 48, height: 48 }}}} to <LogoIcon>."
        )

    # ------------------------------------------------------------------
    # Step 2b — "MYTUBE" wordmark
    # ------------------------------------------------------------------

    def test_wordmark_text_is_present(self, login_page_fixture: LoginPage) -> None:
        """The "MYTUBE" wordmark text must be present inside the auth card."""
        count = login_page_fixture.get_wordmark_count()
        assert count >= 1, (
            "No element matching '.auth-card span' with text 'MYTUBE' was found. "
            "AuthCardLogo must render a <span> with the text 'MYTUBE' inside .auth-card."
        )

    def test_wordmark_color_matches_accent_logo(self, login_page_fixture: LoginPage) -> None:
        """The "MYTUBE" wordmark color must be set to var(--accent-logo).

        The test resolves --accent-logo from the :root computed style and then
        compares it with the computed color of the wordmark <span>.  Both values
        are expressed as RGB strings by the browser, making the comparison
        framework-independent and resilient to CSS-variable indirection.
        """
        accent_logo_value = login_page_fixture.resolve_css_variable("--accent-logo")
        assert accent_logo_value, (
            "CSS custom property --accent-logo is not defined on :root. "
            "globals.css must declare --accent-logo in the :root block."
        )

        wordmark_color = login_page_fixture.get_wordmark_computed_color()
        assert wordmark_color, (
            "Could not read computed color for the MYTUBE wordmark span. "
            "The span was not found or has no computed color."
        )

        accent_logo_rgb = login_page_fixture.resolve_css_variable_to_rgb("--accent-logo")

        assert wordmark_color == accent_logo_rgb, (
            f"MYTUBE wordmark computed color '{wordmark_color}' does not match "
            f"the computed value of --accent-logo '{accent_logo_rgb}' "
            f"(raw CSS value: '{accent_logo_value}'). "
            "AuthCardLogo must pass style={{{{ color: 'var(--accent-logo)' }}}} to the "
            "wordmark <span>."
        )
