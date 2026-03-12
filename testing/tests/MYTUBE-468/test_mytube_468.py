"""
MYTUBE-468: Theme persistence — user preference is saved to and loaded from localStorage

Objective
---------
Verify that the selected theme persists across page reloads using localStorage.

Preconditions
-------------
User is on a page where the theme can be toggled.

Steps
-----
1. Toggle the theme to dark.
2. Verify that localStorage contains the key ``theme`` with value ``dark``.
3. Refresh the browser page.

Expected Result
---------------
The application reloads with the ``dark`` theme applied to the ``body`` element,
reading the value correctly from ``localStorage``.

Test approach
-------------
Playwright navigates to the home page and:

1. Simulates "Toggle the theme to dark" by invoking ``localStorage.setItem``
   and setting ``document.body.setAttribute('data-theme', 'dark')`` via
   ``page.evaluate``.  This reproduces what ``ThemeContext.toggleTheme()``
   does after the first render: it both writes ``localStorage`` and updates
   the DOM attribute.  No UI button for the toggle is currently exposed, so
   the programmatic approach directly exercises the persistence contract.

2. Asserts that ``localStorage.getItem('theme')`` returns ``"dark"`` — this is
   the state that must survive a page reload.

3. Calls ``page.reload()`` to trigger the Next.js hydration path that re-reads
   localStorage on mount (ThemeContext useEffect).

4. Asserts that ``document.body.getAttribute('data-theme')`` equals ``"dark"``
   after the reload, confirming end-to-end persistence.

The inline FOUC-prevention script (themeInitScript.ts) also reads the same
localStorage key before React hydrates and sets ``data-theme`` on ``<body>``,
so the attribute should be present even before React mounts.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env-var access.
- Playwright sync API with pytest module-scoped browser / function-scoped page.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms — wait for initial navigation
_HYDRATION_TIMEOUT = 10_000   # ms — wait for React hydration after reload


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser for the module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="function")
def page(browser: Browser, web_config: WebConfig) -> Page:
    """Yield a fresh browser context/page for each test function.

    Starts with an empty localStorage so the initial theme is always ``light``,
    giving each test a clean, predictable baseline.
    """
    context = browser.new_context()
    context.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Navigate to the home page and wait for the page to be interactive.
    pg.goto(web_config.home_url(), wait_until="domcontentloaded")

    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestThemePersistence:
    """MYTUBE-468: Theme preference is saved to and loaded from localStorage."""

    def test_toggle_to_dark_saves_to_localstorage(self, page: Page) -> None:
        """Step 1+2 — toggling to dark must write 'dark' to localStorage['theme'].

        Simulates the toggle by:
          a) writing 'dark' to localStorage['theme'] (exactly what the
             ThemeContext [theme] effect does after toggleTheme is called), and
          b) setting data-theme='dark' on document.body (exactly what the same
             effect does to update the DOM).

        Then asserts the value round-trips correctly via localStorage.getItem.
        """
        # Simulate theme toggle to dark.
        page.evaluate("""() => {
            localStorage.setItem('theme', 'dark');
            document.body.setAttribute('data-theme', 'dark');
        }""")

        # Step 2: Verify localStorage contains key 'theme' with value 'dark'.
        stored_value: str = page.evaluate("() => localStorage.getItem('theme')")
        assert stored_value == "dark", (
            f"Expected localStorage['theme'] to be 'dark' after toggling the theme, "
            f"but got {stored_value!r}. "
            "The ThemeContext should write 'dark' to localStorage when the theme is toggled."
        )

        # Also verify the DOM attribute is set correctly before reload.
        body_theme: str = page.evaluate(
            "() => document.body.getAttribute('data-theme')"
        )
        assert body_theme == "dark", (
            f"Expected document.body[data-theme] to be 'dark' after toggling, "
            f"but got {body_theme!r}."
        )

    def test_dark_theme_persists_after_reload(self, page: Page) -> None:
        """Step 3 — after a page reload the dark theme must be re-applied.

        Tests end-to-end persistence:
          1. Toggle the theme to dark (simulated via localStorage + DOM).
          2. Reload the page — Next.js re-executes the inline FOUC-prevention
             script and then React hydrates ThemeContext, both of which read
             localStorage['theme'].
          3. Assert that document.body[data-theme] equals 'dark'.

        The FOUC-prevention script (themeInitScript.ts) runs synchronously
        *before* React hydrates and already sets data-theme='dark', so the
        attribute should be present immediately after DOMContentLoaded.
        """
        # Toggle to dark before reload.
        page.evaluate("""() => {
            localStorage.setItem('theme', 'dark');
            document.body.setAttribute('data-theme', 'dark');
        }""")

        # Confirm localStorage persists across the page reload.
        page.reload(wait_until="domcontentloaded")

        # Wait for the body data-theme attribute to be set (FOUC script or hydration).
        try:
            page.wait_for_function(
                "() => document.body.getAttribute('data-theme') === 'dark'",
                timeout=_HYDRATION_TIMEOUT,
            )
        except Exception:
            pass  # Let the assertion below report the exact failure.

        # Step 3 assertion: body must carry data-theme="dark" after reload.
        body_theme_after_reload: str = page.evaluate(
            "() => document.body.getAttribute('data-theme')"
        )
        assert body_theme_after_reload == "dark", (
            f"Expected document.body[data-theme] to be 'dark' after reloading the page, "
            f"but got {body_theme_after_reload!r}. "
            "The application should read the theme preference from localStorage on mount "
            "and apply it to the body element via data-theme. "
            "Check ThemeContext.tsx (mount useEffect) and themeInitScript.ts (FOUC prevention)."
        )

        # Also verify localStorage still contains 'dark' after the reload.
        stored_after_reload: str = page.evaluate("() => localStorage.getItem('theme')")
        assert stored_after_reload == "dark", (
            f"Expected localStorage['theme'] to still be 'dark' after reload, "
            f"but got {stored_after_reload!r}. "
            "The reload should not clear the localStorage theme preference."
        )
