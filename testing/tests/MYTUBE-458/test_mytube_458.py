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
  navigation and basic auth-card visibility.
- Playwright sync API with pytest module-scoped fixtures.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Selector for the SVG icon inside the auth-card branding area.
_AUTH_CARD_SVG = ".auth-card svg"

# Selector for the "MYTUBE" wordmark span inside the auth-card.
# The AuthCardLogo component renders it as a direct-child <span> of a flex
# container that also holds the LogoIcon SVG.
_WORDMARK_SELECTOR = ".auth-card span"

_EXPECTED_LOGO_SIZE_PX = 48


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_css_var(page: Page, var_name: str) -> str:
    """Return the computed value of a CSS custom property from :root."""
    return page.evaluate(
        f"() => getComputedStyle(document.documentElement)"
        f".getPropertyValue('{var_name}').trim()"
    )


def _computed_color(page: Page, selector: str) -> str:
    """Return the computed ``color`` of the first element matching *selector*."""
    return page.evaluate(
        f"""(sel) => {{
            const el = document.querySelector(sel);
            if (!el) return '';
            return window.getComputedStyle(el).color;
        }}""",
        selector,
    )


def _computed_dimension(page: Page, selector: str, prop: str) -> float:
    """Return the computed CSS *prop* (e.g. 'width') as a float in pixels."""
    raw: str = page.evaluate(
        f"""(args) => {{
            const el = document.querySelector(args.sel);
            if (!el) return '';
            return window.getComputedStyle(el)[args.prop];
        }}""",
        {"sel": selector, "prop": prop},
    )
    # raw is like "48px"; strip the unit and convert.
    return float(raw.replace("px", "").strip()) if raw else -1.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def login_page_fixture(config: WebConfig):
    """Open the /login page and yield the Playwright Page object."""
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

        yield page

        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthPageBranding:
    """MYTUBE-458: LogoIcon and wordmark are correctly branded on the auth card."""

    # ------------------------------------------------------------------
    # Step 2a — LogoIcon SVG dimensions
    # ------------------------------------------------------------------

    def test_logo_icon_svg_is_present(self, login_page_fixture: Page) -> None:
        """The LogoIcon SVG must exist inside the .auth-card element."""
        count = login_page_fixture.locator(_AUTH_CARD_SVG).count()
        assert count >= 1, (
            f"No <svg> element found matching '{_AUTH_CARD_SVG}'. "
            "The LogoIcon component is expected to be rendered at the top of "
            "the auth card on the /login page."
        )

    def test_logo_icon_width_is_48px(self, login_page_fixture: Page) -> None:
        """The LogoIcon SVG must have a computed width of 48 px.

        AuthCardLogo passes style={{ width: 48, height: 48 }} to LogoIcon,
        which forwards it to the underlying <svg> element.
        """
        width = _computed_dimension(login_page_fixture, _AUTH_CARD_SVG, "width")
        assert width == _EXPECTED_LOGO_SIZE_PX, (
            f"LogoIcon SVG computed width is {width} px, expected {_EXPECTED_LOGO_SIZE_PX} px. "
            "AuthCardLogo must pass style={{{{ width: 48, height: 48 }}}} to <LogoIcon>."
        )

    def test_logo_icon_height_is_48px(self, login_page_fixture: Page) -> None:
        """The LogoIcon SVG must have a computed height of 48 px."""
        height = _computed_dimension(login_page_fixture, _AUTH_CARD_SVG, "height")
        assert height == _EXPECTED_LOGO_SIZE_PX, (
            f"LogoIcon SVG computed height is {height} px, expected {_EXPECTED_LOGO_SIZE_PX} px. "
            "AuthCardLogo must pass style={{{{ width: 48, height: 48 }}}} to <LogoIcon>."
        )

    # ------------------------------------------------------------------
    # Step 2b — "MYTUBE" wordmark
    # ------------------------------------------------------------------

    def test_wordmark_text_is_present(self, login_page_fixture: Page) -> None:
        """The "MYTUBE" wordmark text must be present inside the auth card."""
        wordmark_locator = login_page_fixture.locator(
            f"{_WORDMARK_SELECTOR}:has-text('MYTUBE')"
        )
        assert wordmark_locator.count() >= 1, (
            "No element matching '.auth-card span' with text 'MYTUBE' was found. "
            "AuthCardLogo must render a <span> with the text 'MYTUBE' inside .auth-card."
        )

    def test_wordmark_color_matches_accent_logo(self, login_page_fixture: Page) -> None:
        """The "MYTUBE" wordmark color must be set to var(--accent-logo).

        The test resolves --accent-logo from the :root computed style and then
        compares it with the computed color of the wordmark <span>.  Both values
        are expressed as RGB strings by the browser, making the comparison
        framework-independent and resilient to CSS-variable indirection.
        """
        # Use Playwright locator to find the wordmark span (supports :has-text)
        wordmark_locator = login_page_fixture.locator(_WORDMARK_SELECTOR).filter(has_text="MYTUBE").first

        # Resolve --accent-logo from :root
        accent_logo_value = _resolve_css_var(login_page_fixture, "--accent-logo")
        assert accent_logo_value, (
            "CSS custom property --accent-logo is not defined on :root. "
            "globals.css must declare --accent-logo in the :root block."
        )

        # Get the computed color of the wordmark span via element_handle
        wordmark_color: str = wordmark_locator.evaluate(
            "el => window.getComputedStyle(el).color"
        )
        assert wordmark_color, (
            "Could not read computed color for the MYTUBE wordmark span. "
            "The span was not found or has no computed color."
        )

        # Resolve --accent-logo to its browser-computed RGB value by
        # creating a temporary element styled with the variable and reading
        # its computed color — this normalises both sides to the same format.
        accent_logo_rgb: str = login_page_fixture.evaluate(
            """(accentValue) => {
                const tmp = document.createElement('span');
                tmp.style.color = accentValue;
                tmp.style.display = 'none';
                document.body.appendChild(tmp);
                const computed = window.getComputedStyle(tmp).color;
                document.body.removeChild(tmp);
                return computed;
            }""",
            accent_logo_value,
        )

        assert wordmark_color == accent_logo_rgb, (
            f"MYTUBE wordmark computed color '{wordmark_color}' does not match "
            f"the computed value of --accent-logo '{accent_logo_rgb}' "
            f"(raw CSS value: '{accent_logo_value}'). "
            "AuthCardLogo must pass style={{{{ color: 'var(--accent-logo)' }}}} to the "
            "wordmark <span>."
        )
