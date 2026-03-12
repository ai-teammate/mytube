"""
MYTUBE-463: Auth switch link — interaction and color match branding

Objective
---------
Verify the navigation link between login and registration pages for correct
color and hover behaviour.

Steps
-----
1. Locate the link to switch between Login and Register (on both pages).
2. Hover the cursor over the link.

Expected Result
---------------
The link color is var(--accent-logo). Upon hovering, the link displays an
underline decoration.

Test Approach
-------------
Playwright navigates to the deployed /login/ and /register/ pages and:
  1. Locates the auth-switch link on each page (Login → "Create one";
     Register → "Sign in") via the LoginPage and RegisterPage components.
  2. Reads the browser-computed ``color`` on the link element and compares it
     against the resolved value of the ``--accent-logo`` CSS custom property
     obtained from the document root — both values come from the live page so
     the comparison is always consistent with the deployed theme.
  3. Hovers over the link and reads the computed ``textDecorationLine`` to
     assert underline decoration is applied.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- LoginPage and RegisterPage page objects encapsulate all selectors and
  CSS inspection helpers — no raw selectors appear in the test body.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or credentials.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.register_page.register_page import RegisterPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_resolved_css_var(page: Page, var_name: str) -> str:
    """Return the resolved value of a CSS custom property from the document root."""
    return page.evaluate(
        "(v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim()",
        var_name,
    )


def _hex_to_rgb(hex_color: str) -> str:
    """Convert a 6-digit hex color string (e.g. '#6d40cb') to 'rgb(r, g, b)'."""
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgb({r}, {g}, {b})"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context()
        page = context.new_page()
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAuthSwitchLink:
    """MYTUBE-463: Auth switch link has correct brand color and hover underline."""

    # ------------------------------------------------------------------
    # Login page — "Create one" link → /register
    # ------------------------------------------------------------------

    def test_login_switch_link_color(self, browser_page: Page, config: WebConfig) -> None:
        """Step 1 (Login page): The switch link color matches --accent-logo."""
        login_page = LoginPage(browser_page)
        login_page.navigate(config.login_url())
        login_page.wait_for_switch_link(timeout=_PAGE_LOAD_TIMEOUT)

        expected_accent = _get_resolved_css_var(browser_page, "--accent-logo")
        assert expected_accent, (
            "--accent-logo CSS variable is not set on the document root. "
            "Check that globals.css is loaded correctly."
        )

        actual_color = login_page.get_switch_link_color()

        if expected_accent.startswith("#"):
            expected_rgb = _hex_to_rgb(expected_accent)
        else:
            expected_rgb = expected_accent

        assert actual_color == expected_rgb, (
            f"Login page 'Create one' link color does not match --accent-logo. "
            f"Expected: {expected_rgb} (from --accent-logo={expected_accent}), "
            f"Actual computed color: {actual_color}"
        )

    def test_login_switch_link_hover_underline(self, browser_page: Page, config: WebConfig) -> None:
        """Step 2 (Login page): Hovering the switch link applies underline decoration."""
        login_page = LoginPage(browser_page)
        login_page.navigate(config.login_url())
        login_page.wait_for_switch_link(timeout=_PAGE_LOAD_TIMEOUT)

        login_page.hover_switch_link()

        text_decoration = login_page.get_switch_link_text_decoration()

        assert "underline" in text_decoration, (
            f"Login page 'Create one' link does not show underline on hover. "
            f"Computed textDecorationLine after hover: '{text_decoration}'. "
            "The link should carry the Tailwind class 'hover:underline'."
        )

    # ------------------------------------------------------------------
    # Register page — "Sign in" link → /login
    # ------------------------------------------------------------------

    def test_register_switch_link_color(self, browser_page: Page, config: WebConfig) -> None:
        """Step 1 (Register page): The switch link color matches --accent-logo."""
        register_page = RegisterPage(browser_page)
        browser_page.goto(config.register_url(), wait_until="domcontentloaded")
        register_page.wait_for_switch_link(timeout=_PAGE_LOAD_TIMEOUT)

        expected_accent = _get_resolved_css_var(browser_page, "--accent-logo")
        assert expected_accent, (
            "--accent-logo CSS variable is not set on the document root. "
            "Check that globals.css is loaded correctly."
        )

        actual_color = register_page.get_switch_link_color()

        if expected_accent.startswith("#"):
            expected_rgb = _hex_to_rgb(expected_accent)
        else:
            expected_rgb = expected_accent

        assert actual_color == expected_rgb, (
            f"Register page 'Sign in' link color does not match --accent-logo. "
            f"Expected: {expected_rgb} (from --accent-logo={expected_accent}), "
            f"Actual computed color: {actual_color}"
        )

    def test_register_switch_link_hover_underline(self, browser_page: Page, config: WebConfig) -> None:
        """Step 2 (Register page): Hovering the switch link applies underline decoration."""
        register_page = RegisterPage(browser_page)
        browser_page.goto(config.register_url(), wait_until="domcontentloaded")
        register_page.wait_for_switch_link(timeout=_PAGE_LOAD_TIMEOUT)

        register_page.hover_switch_link()

        text_decoration = register_page.get_switch_link_text_decoration()

        assert "underline" in text_decoration, (
            f"Register page 'Sign in' link does not show underline on hover. "
            f"Computed textDecorationLine after hover: '{text_decoration}'. "
            "The link should carry the Tailwind class 'hover:underline'."
        )

