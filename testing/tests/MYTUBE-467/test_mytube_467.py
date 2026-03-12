"""
MYTUBE-467: Auth routes layout exclusion — shell container is not applied to
login or register pages.

Objective
---------
Confirm that the shell-based layout is correctly bypassed for authentication
routes (/login and /register).

Steps
-----
1. Navigate to /login.
2. Inspect the DOM for the presence of the .shell wrapper around the content.
3. Navigate to /register and repeat the inspection.

Expected Result
---------------
The .shell class and its associated styles (rounded corners, shadow, max-width)
are not applied to the login or register pages, preserving the no-shell layout
behaviour.

Implementation notes
--------------------
AppShell.tsx returns ``<>{children}</>`` (no wrapper) for AUTH_ROUTES
(["/login", "/register"]).  For all other routes it wraps content in::

    <div class="page-wrap">
      ...
      <div class="shell">...</div>
    </div>

This test verifies, for both auth routes, that:
  1. No element with class "shell" exists in the DOM.
  2. No element with class "page-wrap" exists in the DOM.
  3. The computed styles that characterise the shell (border-radius, max-width,
     box-shadow) are NOT present on any top-level wrapper.

Run from repo root:
    pytest testing/tests/MYTUBE-467/test_mytube_467.py -v
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


class TestAuthRoutesShellExclusion:
    """Verify that .shell wrapper is absent on /login and /register."""

    # ------------------------------------------------------------------
    # /login
    # ------------------------------------------------------------------

    def test_login_has_no_shell_class(self, config: WebConfig, browser_context) -> None:
        """The .shell element must NOT be present on the /login page."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.login_url()
            login = LoginPage(page)
            login.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert not login.has_shell_class(), (
                f"Expected no .shell element on {url}, but shell class was found. "
                "AppShell should bypass the shell wrapper for auth routes."
            )
        finally:
            page.close()

    def test_login_has_no_page_wrap_class(self, config: WebConfig, browser_context) -> None:
        """The .page-wrap element must NOT be present on the /login page."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.login_url()
            login = LoginPage(page)
            login.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert not login.has_page_wrap_class(), (
                f"Expected no .page-wrap element on {url}, but page-wrap class was found. "
                "AppShell should return children directly for auth routes."
            )
        finally:
            page.close()

    def test_login_shell_styles_not_applied(self, config: WebConfig, browser_context) -> None:
        """The distinctive .shell styles (border-radius, max-width) must not
        appear on any top-level wrapper on /login."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.login_url()
            login = LoginPage(page)
            login.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            shell_like = login.has_shell_like_styles()
            assert shell_like is None, (
                f"Found an element on {url} with shell-like styles "
                f"(borderRadius=24px, maxWidth=1320px): {shell_like!r}. "
                "The shell layout should not be applied to auth routes."
            )
        finally:
            page.close()

    # ------------------------------------------------------------------
    # /register
    # ------------------------------------------------------------------

    def test_register_has_no_shell_class(self, config: WebConfig, browser_context) -> None:
        """The .shell element must NOT be present on the /register page."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.register_url()
            register = RegisterPage(page)
            register.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert not register.has_shell_class(), (
                f"Expected no .shell element on {url}, but shell class was found. "
                "AppShell should bypass the shell wrapper for auth routes."
            )
        finally:
            page.close()

    def test_register_has_no_page_wrap_class(self, config: WebConfig, browser_context) -> None:
        """The .page-wrap element must NOT be present on the /register page."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.register_url()
            register = RegisterPage(page)
            register.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert not register.has_page_wrap_class(), (
                f"Expected no .page-wrap element on {url}, but page-wrap class was found. "
                "AppShell should return children directly for auth routes."
            )
        finally:
            page.close()

    def test_register_shell_styles_not_applied(self, config: WebConfig, browser_context) -> None:
        """The distinctive .shell styles (border-radius, max-width) must not
        appear on any top-level wrapper on /register."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = config.register_url()
            register = RegisterPage(page)
            register.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            shell_like = register.has_shell_like_styles()
            assert shell_like is None, (
                f"Found an element on {url} with shell-like styles "
                f"(borderRadius=24px, maxWidth=1320px): {shell_like!r}. "
                "The shell layout should not be applied to auth routes."
            )
        finally:
            page.close()
