"""
MYTUBE-366: Use different browsers — text visibility is consistent across
Chrome, Firefox, and Safari.

Objective
---------
Confirm that the CSS fix for text visibility is cross-browser compatible and
does not regress on specific engines by verifying that input text, placeholders,
and button labels are visible and correctly styled in Chromium, Firefox, and
WebKit (Safari engine).

Steps
-----
1. Open the application in Chromium, Firefox, and WebKit (Safari engine).
2. Check the search bar input (placeholder and aria-label) in the site header.
3. Check the login page email and password inputs (placeholder visibility).
4. Check the Sign In button label on the login page.

Expected Result
---------------
In all three browsers:
- The search input is visible and has a non-empty placeholder.
- The login email and password inputs are visible with non-empty placeholders.
- The Sign In button is visible with a readable label.

Architecture
------------
- Browser lifecycle is managed by the ``pw_page`` fixture in conftest.py.
- Search bar assertions go through HeaderPage (testing/components/pages/header_page/).
- Login page assertions go through LoginPage (testing/components/pages/login_page/).
- No raw selectors, page.locator(), or framework calls appear in this file.
- Parametrised over browser types so each browser runs the same assertions.
- WebKit is skipped automatically by the fixture if system dependencies are absent.

Environment Variables
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
from playwright.sync_api import Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.header_page.header_page import HeaderPage
from testing.components.pages.login_page.login_page import LoginPage

# Browser types to test — chromium ≈ Chrome, webkit ≈ Safari
_BROWSER_NAMES = ["chromium", "firefox", "webkit"]


# ---------------------------------------------------------------------------
# Parametrised test class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("browser_name", _BROWSER_NAMES)
class TestCrossBrowserTextVisibility:
    """MYTUBE-366: Verify text visibility is consistent across three browser engines."""

    def test_search_bar_visibility(self, browser_name: str, pw_page: Page, web_config: WebConfig) -> None:
        """Step 2: Search input is visible and placeholder text is non-empty in *browser_name*."""
        header = HeaderPage(pw_page)
        header.navigate_to(web_config.home_url())

        assert header.is_search_input_visible(), (
            f"[{browser_name}] Search input is not visible on the home page."
        )
        assert header.get_search_placeholder(), (
            f"[{browser_name}] Search input has no placeholder text — "
            f"element may not be rendering correctly."
        )
        assert header.is_search_input_text_color_visible(), (
            f"[{browser_name}] Search input text colour is fully transparent — "
            f"text is invisible."
        )

    def test_search_button_label_visibility(self, browser_name: str, pw_page: Page, web_config: WebConfig) -> None:
        """Step 2: Search submit button is visible and has a readable label in *browser_name*."""
        header = HeaderPage(pw_page)
        header.navigate_to(web_config.home_url())

        assert header.is_search_button_visible(), (
            f"[{browser_name}] Search submit button is not visible on the home page."
        )
        assert header.get_search_button_label(), (
            f"[{browser_name}] Search button has no accessible label / text."
        )

    def test_login_inputs_visibility(self, browser_name: str, pw_page: Page, web_config: WebConfig) -> None:
        """Step 3: Login email and password inputs are visible with placeholders in *browser_name*."""
        login_page = LoginPage(pw_page)
        login_page.navigate(web_config.login_url())
        login_page.wait_for_form()

        assert login_page.is_email_input_visible(), (
            f"[{browser_name}] Email input is not visible on the login page."
        )
        assert login_page.get_email_placeholder(), (
            f"[{browser_name}] Email input has no placeholder text."
        )
        assert login_page.is_email_text_color_visible(), (
            f"[{browser_name}] Email input text colour is fully transparent."
        )

        assert login_page.is_password_input_visible(), (
            f"[{browser_name}] Password input is not visible on the login page."
        )
        assert login_page.get_password_placeholder(), (
            f"[{browser_name}] Password input has no placeholder text."
        )
        assert login_page.is_password_text_color_visible(), (
            f"[{browser_name}] Password input text colour is fully transparent."
        )

    def test_sign_in_button_label_visibility(self, browser_name: str, pw_page: Page, web_config: WebConfig) -> None:
        """Step 4: Sign In button is visible with a readable label in *browser_name*."""
        login_page = LoginPage(pw_page)
        login_page.navigate(web_config.login_url())
        login_page.wait_for_form()

        assert login_page.is_sign_in_button_visible(), (
            f"[{browser_name}] Sign In button is not visible on the login page."
        )
        assert login_page.get_sign_in_button_label(), (
            f"[{browser_name}] Sign In button has no visible text label."
        )
        assert login_page.is_sign_in_button_text_color_visible(), (
            f"[{browser_name}] Sign In button text colour is fully transparent."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
