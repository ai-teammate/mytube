"""
MYTUBE-496: Auth routes on GitHub Pages — layout wrappers and styles are
excluded for base path and trailing slashes.

Objective
---------
Verify that the AppShell components (.shell and .page-wrap) and their
associated styles are correctly excluded when authentication routes are
accessed under the GitHub Pages base path with trailing slashes.

Steps
-----
1. Navigate to https://ai-teammate.github.io/mytube/login/.
2. Inspect the DOM for the presence of the .shell container class.
3. Inspect the DOM for the presence of the .page-wrap container class.
4. Verify that no elements (excluding .auth-card) have max-width:1320px or
   border-radius:24px shell styles.
5. Repeat steps 1-4 for https://ai-teammate.github.io/mytube/register/.

Expected Result
---------------
Neither .shell nor .page-wrap is present in the DOM. The shell-based styles
(rounded corners and max-width) are not applied to the page containers,
ensuring auth pages use their dedicated standalone layout.

Background
----------
Bug MYTUBE-495 identified that AppShell.tsx compared pathname against
hardcoded AUTH_ROUTES (["/login", "/register"]) using an exact match.
Under the GitHub Pages base path (/mytube), usePathname() returns
/mytube/login/ and /mytube/register/, which never matched the list, so
the shell wrapper was incorrectly rendered on auth pages.

The fix normalises the pathname by stripping the NEXT_PUBLIC_BASE_PATH
prefix and trailing slash before the auth-route check.

Run from repo root:
    pytest testing/tests/MYTUBE-496/test_mytube_496.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.register_page.register_page import RegisterPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# JavaScript that checks for shell-like styles while excluding .auth-card.
# The .auth-card element legitimately uses border-radius for its card design;
# we only care about shell-specific layout elements (max-width + border-radius).
_CHECK_SHELL_STYLES_JS = """() => {
    for (const el of document.querySelectorAll('body *')) {
        if (el.closest('.auth-card')) continue;
        const s = window.getComputedStyle(el);
        if (s.borderRadius === '24px' && s.maxWidth === '1320px')
            return el.className || el.tagName;
    }
    return null;
}"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_context(config: WebConfig):
    """Launch Chromium and yield (browser, context) for the module."""
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context()
        yield browser, context
        context.close()
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuthRoutesGitHubPagesBasePathExclusion:
    """Verify AppShell layout is bypassed for auth routes under GitHub Pages base path."""

    # ------------------------------------------------------------------
    # /login/ (with base path and trailing slash)
    # ------------------------------------------------------------------

    def test_login_has_no_shell_class(self, config: WebConfig, browser_context) -> None:
        """The .shell element must NOT be present on /login/ under the GitHub Pages base path."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.login_url()
            login = LoginPage(page)
            login.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert not login.has_shell_class(), (
                f"Expected no .shell element on {url}, but found {page.locator('.shell').count()}. "
                "AppShell should bypass the shell wrapper for auth routes under the GitHub Pages base path."
            )
        finally:
            page.close()

    def test_login_has_no_page_wrap_class(self, config: WebConfig, browser_context) -> None:
        """The .page-wrap element must NOT be present on /login/ under the GitHub Pages base path."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.login_url()
            login = LoginPage(page)
            login.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert not login.has_page_wrap_class(), (
                f"Expected no .page-wrap element on {url}, but found {page.locator('.page-wrap').count()}. "
                "AppShell should return children directly for auth routes."
            )
        finally:
            page.close()

    def test_login_shell_styles_not_applied(self, config: WebConfig, browser_context) -> None:
        """Shell-specific styles (border-radius:24px, max-width:1320px) must not appear
        on any element outside .auth-card on the /login/ page."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.login_url()
            login = LoginPage(page)
            login.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            shell_like = page.evaluate(_CHECK_SHELL_STYLES_JS)
            assert shell_like is None, (
                f"Found an element on {url} with shell-like styles "
                f"(borderRadius=24px, maxWidth=1320px) outside .auth-card: {shell_like!r}. "
                "The shell layout should not be applied to auth routes."
            )
        finally:
            page.close()

    # ------------------------------------------------------------------
    # /register/ (with base path and trailing slash)
    # ------------------------------------------------------------------

    def test_register_has_no_shell_class(self, config: WebConfig, browser_context) -> None:
        """The .shell element must NOT be present on /register/ under the GitHub Pages base path."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.register_url()
            register = RegisterPage(page)
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert not register.has_shell_class(), (
                f"Expected no .shell element on {url}, but found {page.locator('.shell').count()}. "
                "AppShell should bypass the shell wrapper for auth routes under the GitHub Pages base path."
            )
        finally:
            page.close()

    def test_register_has_no_page_wrap_class(self, config: WebConfig, browser_context) -> None:
        """The .page-wrap element must NOT be present on /register/ under the GitHub Pages base path."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.register_url()
            register = RegisterPage(page)
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert not register.has_page_wrap_class(), (
                f"Expected no .page-wrap element on {url}, but found {page.locator('.page-wrap').count()}. "
                "AppShell should return children directly for auth routes."
            )
        finally:
            page.close()

    def test_register_shell_styles_not_applied(self, config: WebConfig, browser_context) -> None:
        """Shell-specific styles (border-radius:24px, max-width:1320px) must not appear
        on any element outside .auth-card on the /register/ page."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.register_url()
            register = RegisterPage(page)
            page.goto(url, wait_until="domcontentloaded")
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            shell_like = page.evaluate(_CHECK_SHELL_STYLES_JS)
            assert shell_like is None, (
                f"Found an element on {url} with shell-like styles "
                f"(borderRadius=24px, maxWidth=1320px) outside .auth-card: {shell_like!r}. "
                "The shell layout should not be applied to auth routes."
            )
        finally:
            page.close()
