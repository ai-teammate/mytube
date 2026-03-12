"""
MYTUBE-460: Auth form input styling — inputs consume correct design tokens and focus states

Objective
---------
Verify that email and password fields on the login form use the redesigned
input styles consistent with the upload-card:

  • background: var(--bg-page)  (resolved to its computed colour value)
  • border-radius: 12px
  • On focus: a purple focus ring (box-shadow) is applied

Steps
-----
1. Navigate to the /login page and wait for the form to render.
2. Inspect the computed styles of the email and password inputs.
   Verify background matches the --bg-page token and border-radius is 12 px.
3. Focus the email input via JavaScript and verify a purple box-shadow is set.
4. Focus the password input via JavaScript and verify a purple box-shadow is set.

Test Approach
-------------
Playwright navigates to the deployed login page and reads computed CSS
properties directly from the DOM, triggering focus events via JS to exercise
the onFocus handler.

Run from repo root:
    pytest testing/tests/MYTUBE-460/test_mytube_460.py -v
"""
from __future__ import annotations

import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Expected values (mirrored from globals.css — light theme)
# ---------------------------------------------------------------------------

# The --bg-page light-theme value. Both light and dark are valid because the
# test environment may be running in either theme.
_BG_PAGE_LIGHT = "rgb(248, 249, 250)"   # #f8f9fa
_BG_PAGE_DARK  = "rgb(15, 15, 17)"      # #0f0f11

_EXPECTED_BORDER_RADIUS = "12px"

# The onFocus handler sets: boxShadow = "0 0 0 3px rgba(109,64,203,0.25)"
# Playwright / the browser may normalise the RGBA notation.  We accept any
# box-shadow that contains the purple colour component.
_PURPLE_SHADOW_PATTERN = re.compile(
    r"rgba?\(109,\s*64,\s*203",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Selectors (must match login_page.py)
# ---------------------------------------------------------------------------

_EMAIL_SEL    = 'input[id="email"]'
_PASSWORD_SEL = 'input[id="password"]'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _computed(page, selector: str, prop: str) -> str:
    """Return the computed CSS property *prop* for the element at *selector*."""
    return page.evaluate(
        """([sel, prop]) => {
            const el = document.querySelector(sel);
            if (!el) return '';
            return window.getComputedStyle(el).getPropertyValue(prop).trim();
        }""",
        [selector, prop],
    )


def _inline_style(page, selector: str, prop: str) -> str:
    """Return the *inline* style property *prop* set on the element via .style."""
    return page.evaluate(
        """([sel, prop]) => {
            const el = document.querySelector(sel);
            if (!el) return '';
            return (el.style.getPropertyValue(prop) || '').trim();
        }""",
        [selector, prop],
    )


def _focus_via_js(page, selector: str) -> None:
    """Focus the element programmatically and trigger the React onFocus handler."""
    page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (el) { el.focus(); el.dispatchEvent(new FocusEvent('focus', { bubbles: true })); }
        }""",
        selector,
    )


def _blur_via_js(page, selector: str) -> None:
    """Blur the element programmatically and trigger the React onBlur handler."""
    page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (el) { el.blur(); el.dispatchEvent(new FocusEvent('blur', { bubbles: true })); }
        }""",
        selector,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def page(config: WebConfig):
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo  = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        p = browser.new_page()
        login = LoginPage(p)
        login.navigate(config.login_url())
        login.wait_for_form(timeout=30_000)
        yield p
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAuthInputStyling:
    """MYTUBE-460: Auth form inputs use correct design tokens and focus states."""

    # ------------------------------------------------------------------
    # Step 2a — background colour
    # ------------------------------------------------------------------

    def test_email_input_background_uses_bg_page_token(self, page):
        """Email input background must resolve to the --bg-page CSS variable value."""
        bg = _computed(page, _EMAIL_SEL, "background-color")
        assert bg in (_BG_PAGE_LIGHT, _BG_PAGE_DARK), (
            f"Email input background-color '{bg}' does not match --bg-page token.\n"
            f"Expected one of: {_BG_PAGE_LIGHT!r} (light) or {_BG_PAGE_DARK!r} (dark)."
        )

    def test_password_input_background_uses_bg_page_token(self, page):
        """Password input background must resolve to the --bg-page CSS variable value."""
        bg = _computed(page, _PASSWORD_SEL, "background-color")
        assert bg in (_BG_PAGE_LIGHT, _BG_PAGE_DARK), (
            f"Password input background-color '{bg}' does not match --bg-page token.\n"
            f"Expected one of: {_BG_PAGE_LIGHT!r} (light) or {_BG_PAGE_DARK!r} (dark)."
        )

    # ------------------------------------------------------------------
    # Step 2b — border-radius
    # ------------------------------------------------------------------

    def test_email_input_border_radius_is_12px(self, page):
        """Email input must have border-radius of 12 px."""
        br = _computed(page, _EMAIL_SEL, "border-radius")
        assert br == _EXPECTED_BORDER_RADIUS, (
            f"Email input border-radius is '{br}', expected '{_EXPECTED_BORDER_RADIUS}'."
        )

    def test_password_input_border_radius_is_12px(self, page):
        """Password input must have border-radius of 12 px."""
        br = _computed(page, _PASSWORD_SEL, "border-radius")
        assert br == _EXPECTED_BORDER_RADIUS, (
            f"Password input border-radius is '{br}', expected '{_EXPECTED_BORDER_RADIUS}'."
        )

    # ------------------------------------------------------------------
    # Step 3 — purple focus ring on email input
    # ------------------------------------------------------------------

    def test_email_input_shows_purple_focus_ring_on_focus(self, page):
        """Focusing the email input must apply a purple box-shadow."""
        _blur_via_js(page, _PASSWORD_SEL)
        _focus_via_js(page, _EMAIL_SEL)

        shadow = _inline_style(page, _EMAIL_SEL, "box-shadow")
        assert _PURPLE_SHADOW_PATTERN.search(shadow), (
            f"Email input box-shadow after focus is '{shadow}'.\n"
            "Expected a purple shadow matching rgba(109, 64, 203, ...)."
        )

    # ------------------------------------------------------------------
    # Step 4 — purple focus ring on password input
    # ------------------------------------------------------------------

    def test_password_input_shows_purple_focus_ring_on_focus(self, page):
        """Focusing the password input must apply a purple box-shadow."""
        _blur_via_js(page, _EMAIL_SEL)
        _focus_via_js(page, _PASSWORD_SEL)

        shadow = _inline_style(page, _PASSWORD_SEL, "box-shadow")
        assert _PURPLE_SHADOW_PATTERN.search(shadow), (
            f"Password input box-shadow after focus is '{shadow}'.\n"
            "Expected a purple shadow matching rgba(109, 64, 203, ...)."
        )
