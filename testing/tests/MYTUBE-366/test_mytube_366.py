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
- Uses Playwright sync API with chromium, firefox, and webkit.
- Reuses WebConfig from testing/core/config/web_config.py.
- Reuses LoginPage from testing/components/pages/login_page.
- Parametrised over browser types so each browser runs the same assertions.
- WebKit is skipped if its system dependencies are not present in the host OS.

Environment Variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import contextlib
import os
import sys
from typing import Generator

import pytest
from playwright.sync_api import sync_playwright, Playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Selectors for search header elements (shared across all pages)
_SEARCH_INPUT_SELECTOR = 'input[type="search"]'
_SEARCH_BUTTON_SELECTOR = 'button[aria-label="Submit search"]'

# Login page selectors (also available through LoginPage, but kept here for
# direct colour / CSS visibility checks that the page object abstracts away)
_EMAIL_INPUT_SELECTOR = 'input[id="email"]'
_PASSWORD_INPUT_SELECTOR = 'input[id="password"]'
_SIGN_IN_BUTTON_SELECTOR = 'button[type="submit"]:not([aria-label="Submit search"])'

# Browser types to test — chromium ≈ Chrome, webkit ≈ Safari
_BROWSER_NAMES = ["chromium", "firefox", "webkit"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@contextlib.contextmanager
def _browser_page(browser_name: str, config: WebConfig) -> Generator[Page, None, None]:
    """Context manager: launch *browser_name*, yield a Page, then clean up.

    Raises ``pytest.skip`` if the browser cannot be launched due to missing
    system dependencies (common for WebKit on headless Linux CI runners).
    """
    with sync_playwright() as pw:
        launcher = getattr(pw, browser_name)
        try:
            browser: Browser = launcher.launch(
                headless=config.headless,
                slow_mo=config.slow_mo,
            )
        except Exception as exc:
            # WebKit (and occasionally Firefox) may be unavailable on stripped
            # CI images.  Skip gracefully rather than fail with a system error.
            pytest.skip(
                f"Browser '{browser_name}' could not be launched: {exc}"
            )
        context: BrowserContext = browser.new_context()
        page: Page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            yield page
        finally:
            context.close()
            browser.close()


def _check_text_color_not_invisible(page: Page, selector: str) -> None:
    """Assert the computed ``color`` CSS property is not fully transparent."""
    color = page.evaluate(
        """(selector) => {
            const el = document.querySelector(selector);
            if (!el) return null;
            return window.getComputedStyle(el).color;
        }""",
        selector,
    )
    assert color is not None, (
        f"Element not found for selector {selector!r} on {page.url!r}"
    )
    assert color != "rgba(0, 0, 0, 0)", (
        f"Text color for {selector!r} is fully transparent (rgba(0, 0, 0, 0)) — "
        f"text is invisible. URL: {page.url!r}"
    )


def _get_placeholder(page: Page, selector: str) -> str:
    """Return the placeholder attribute value of the element at *selector*."""
    return page.evaluate(
        """(selector) => {
            const el = document.querySelector(selector);
            return el ? (el.placeholder || '') : '';
        }""",
        selector,
    )


def _get_button_label(page: Page, selector: str) -> str:
    """Return the visible text / aria-label of the button at *selector*."""
    return page.evaluate(
        """(selector) => {
            const el = document.querySelector(selector);
            if (!el) return '';
            return (el.innerText || el.textContent || el.getAttribute('aria-label') || '').trim();
        }""",
        selector,
    )


# ---------------------------------------------------------------------------
# Parametrised test class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("browser_name", _BROWSER_NAMES)
class TestCrossBrowserTextVisibility:
    """MYTUBE-366: Verify text visibility is consistent across three browser engines."""

    def test_search_bar_visibility(self, browser_name: str) -> None:
        """Step 2: Search input is visible and placeholder text is non-empty in *browser_name*."""
        config = WebConfig()
        with _browser_page(browser_name, config) as page:
            page.goto(config.home_url(), wait_until="domcontentloaded")
            page.wait_for_selector(_SEARCH_INPUT_SELECTOR, timeout=_PAGE_LOAD_TIMEOUT)

            assert page.locator(_SEARCH_INPUT_SELECTOR).is_visible(), (
                f"[{browser_name}] Search input is not visible on the home page."
            )

            placeholder = _get_placeholder(page, _SEARCH_INPUT_SELECTOR)
            assert placeholder, (
                f"[{browser_name}] Search input has no placeholder text — "
                f"element may not be rendering correctly."
            )

            _check_text_color_not_invisible(page, _SEARCH_INPUT_SELECTOR)

    def test_search_button_label_visibility(self, browser_name: str) -> None:
        """Step 2: Search submit button is visible and has a readable label in *browser_name*."""
        config = WebConfig()
        with _browser_page(browser_name, config) as page:
            page.goto(config.home_url(), wait_until="domcontentloaded")
            page.wait_for_selector(_SEARCH_BUTTON_SELECTOR, timeout=_PAGE_LOAD_TIMEOUT)

            assert page.locator(_SEARCH_BUTTON_SELECTOR).is_visible(), (
                f"[{browser_name}] Search submit button is not visible on the home page."
            )

            label = _get_button_label(page, _SEARCH_BUTTON_SELECTOR)
            assert label, (
                f"[{browser_name}] Search button has no accessible label / text."
            )

    def test_login_inputs_visibility(self, browser_name: str) -> None:
        """Step 3: Login email and password inputs are visible with placeholders in *browser_name*."""
        config = WebConfig()
        with _browser_page(browser_name, config) as page:
            login_page = LoginPage(page)
            login_page.navigate(config.login_url())
            # Wait for React to finish rendering the login form
            page.wait_for_selector(_EMAIL_INPUT_SELECTOR, timeout=_PAGE_LOAD_TIMEOUT)

            assert page.locator(_EMAIL_INPUT_SELECTOR).is_visible(), (
                f"[{browser_name}] Email input is not visible on the login page."
            )
            email_placeholder = _get_placeholder(page, _EMAIL_INPUT_SELECTOR)
            assert email_placeholder, (
                f"[{browser_name}] Email input has no placeholder text."
            )
            _check_text_color_not_invisible(page, _EMAIL_INPUT_SELECTOR)

            assert page.locator(_PASSWORD_INPUT_SELECTOR).is_visible(), (
                f"[{browser_name}] Password input is not visible on the login page."
            )
            password_placeholder = _get_placeholder(page, _PASSWORD_INPUT_SELECTOR)
            assert password_placeholder, (
                f"[{browser_name}] Password input has no placeholder text."
            )
            _check_text_color_not_invisible(page, _PASSWORD_INPUT_SELECTOR)

    def test_sign_in_button_label_visibility(self, browser_name: str) -> None:
        """Step 4: Sign In button is visible with a readable label in *browser_name*."""
        config = WebConfig()
        with _browser_page(browser_name, config) as page:
            login_page = LoginPage(page)
            login_page.navigate(config.login_url())
            # Wait for React to finish rendering the login form
            page.wait_for_selector(_SIGN_IN_BUTTON_SELECTOR, timeout=_PAGE_LOAD_TIMEOUT)

            assert page.locator(_SIGN_IN_BUTTON_SELECTOR).is_visible(), (
                f"[{browser_name}] Sign In button is not visible on the login page."
            )

            label = _get_button_label(page, _SIGN_IN_BUTTON_SELECTOR)
            assert label, (
                f"[{browser_name}] Sign In button has no visible text label."
            )

            _check_text_color_not_invisible(page, _SIGN_IN_BUTTON_SELECTOR)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
