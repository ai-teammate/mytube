"""
MYTUBE-497: Non-auth route with auth prefix — AppShell layout is correctly applied.

Objective
---------
Ensure that the layout exclusion logic (normalisation and prefix check) inside
``AppShell.tsx`` uses *exact* matching — not *startsWith* matching — for
AUTH_ROUTES.  Routes whose pathname begins with "/login" or "/register" but are
NOT those routes (e.g. "/login-help", "/register-confirmation") must still
receive the full shell wrapper.

Context (linked bug MYTUBE-495)
--------------------------------
The bug fix for MYTUBE-495 changed AUTH_ROUTES checking from a bare
``includes(pathname)`` (which failed under the GitHub Pages ``/mytube`` base
path) to a normalisation step followed by ``AUTH_ROUTES.includes(normalizedPathname)``.

The normalisation strips the base-path prefix and the trailing slash:
  "/mytube/login/"  →  "/login"   (excluded — auth route)
  "/mytube/login-help/"  →  "/login-help"   (NOT in AUTH_ROUTES — shell applied)

This test verifies the second case: that the fix does not accidentally match
on a *prefix* of an auth route string.

Steps
-----
1. Navigate to ``{base_url}/login-help/`` — a route sharing the "/login" prefix.
2. Inspect DOM: ``.shell`` and ``.page-wrap`` elements must be present.
3. Verify shell-like styles (``max-width: 1320px``) are applied.
4. Navigate to ``{base_url}/register-confirmation/`` — shares "/register" prefix.
5. Repeat DOM and style inspection.

Expected Result
---------------
- ``.shell`` element **is present** on both routes.
- ``.page-wrap`` element **is present** on both routes.
- An element with ``maxWidth: 1320px`` **is detected** on both routes.

Note on 404 behaviour
---------------------
Both ``/login-help/`` and ``/register-confirmation/`` do not correspond to real
pages.  GitHub Pages serves the statically-exported ``404.html`` for these URLs.
That file is generated from the Next.js root layout which includes ``AppShell``.
Because neither path normalises to "/login" or "/register", ``AppShell`` renders
the full shell wrapper — which is exactly what this test asserts.

Run from repo root
------------------
    pytest testing/tests/MYTUBE-497/test_mytube_497.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.non_auth_shell_page.non_auth_shell_page import NonAuthShellPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Routes that share a prefix with auth routes but are NOT auth routes
_LOGIN_PREFIX_ROUTE = "login-help"
_REGISTER_PREFIX_ROUTE = "register-confirmation"


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


class TestNonAuthRoutesShellPresence:
    """Verify that the AppShell IS applied to routes that share a string
    prefix with /login or /register but are not those exact auth routes."""

    # ------------------------------------------------------------------
    # /login-help  (shares "/login" prefix)
    # ------------------------------------------------------------------

    def test_login_prefix_has_shell_class(
        self, config: WebConfig, browser_context
    ) -> None:
        """The .shell element MUST be present on a route starting with /login."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = f"{config.base_url}/{_LOGIN_PREFIX_ROUTE}/"
            non_auth = NonAuthShellPage(page)
            non_auth.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert non_auth.has_shell_class(), (
                f"Expected .shell element on {url} (non-auth route sharing '/login' prefix), "
                "but no .shell was found. The AppShell exclusion guard must use exact "
                "matching — not prefix/startsWith matching — so this route should be "
                "wrapped by the shell."
            )
        finally:
            page.close()

    def test_login_prefix_has_page_wrap_class(
        self, config: WebConfig, browser_context
    ) -> None:
        """The .page-wrap element MUST be present on a route starting with /login."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = f"{config.base_url}/{_LOGIN_PREFIX_ROUTE}/"
            non_auth = NonAuthShellPage(page)
            non_auth.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert non_auth.has_page_wrap_class(), (
                f"Expected .page-wrap element on {url} (non-auth route sharing '/login' prefix), "
                "but no .page-wrap was found. AppShell should render the full page-wrap "
                "for any route that is not an exact match for an auth route."
            )
        finally:
            page.close()

    def test_login_prefix_shell_styles_applied(
        self, config: WebConfig, browser_context
    ) -> None:
        """Shell styles (max-width: 1320px) MUST be present on a /login-prefixed route."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = f"{config.base_url}/{_LOGIN_PREFIX_ROUTE}/"
            non_auth = NonAuthShellPage(page)
            non_auth.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            shell_like = non_auth.has_shell_like_styles()
            assert shell_like is not None, (
                f"Expected to find an element with shell-like styles (borderRadius=24px, "
                f"maxWidth=1320px) on {url}, but none was found. The AppShell should "
                "apply its full wrapper to non-auth routes."
            )
        finally:
            page.close()

    # ------------------------------------------------------------------
    # /register-confirmation  (shares "/register" prefix)
    # ------------------------------------------------------------------

    def test_register_prefix_has_shell_class(
        self, config: WebConfig, browser_context
    ) -> None:
        """The .shell element MUST be present on a route starting with /register."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = f"{config.base_url}/{_REGISTER_PREFIX_ROUTE}/"
            non_auth = NonAuthShellPage(page)
            non_auth.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert non_auth.has_shell_class(), (
                f"Expected .shell element on {url} (non-auth route sharing '/register' prefix), "
                "but no .shell was found. The AppShell exclusion guard must use exact "
                "matching — not prefix/startsWith matching — so this route should be "
                "wrapped by the shell."
            )
        finally:
            page.close()

    def test_register_prefix_has_page_wrap_class(
        self, config: WebConfig, browser_context
    ) -> None:
        """The .page-wrap element MUST be present on a route starting with /register."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = f"{config.base_url}/{_REGISTER_PREFIX_ROUTE}/"
            non_auth = NonAuthShellPage(page)
            non_auth.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            assert non_auth.has_page_wrap_class(), (
                f"Expected .page-wrap element on {url} (non-auth route sharing '/register' "
                "prefix), but no .page-wrap was found. AppShell should render the full "
                "page-wrap for any route that is not an exact match for an auth route."
            )
        finally:
            page.close()

    def test_register_prefix_shell_styles_applied(
        self, config: WebConfig, browser_context
    ) -> None:
        """Shell styles (max-width: 1320px) MUST be present on a /register-prefixed route."""
        _, context = browser_context
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
        try:
            url = f"{config.base_url}/{_REGISTER_PREFIX_ROUTE}/"
            non_auth = NonAuthShellPage(page)
            non_auth.navigate(url)
            page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)
            shell_like = non_auth.has_shell_like_styles()
            assert shell_like is not None, (
                f"Expected to find an element with shell-like styles (borderRadius=24px, "
                f"maxWidth=1320px) on {url}, but none was found. The AppShell should "
                "apply its full wrapper to non-auth routes."
            )
        finally:
            page.close()
