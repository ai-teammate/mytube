"""
MYTUBE-306: Direct navigation to fallback URL without session data — 'User not found' is displayed.

Objective
---------
Verify the system's behavior when the SPA fallback URL (/u/_/) is accessed
directly without the required username stored in sessionStorage.

Background
----------
GitHub Pages cannot serve dynamic routes, so the app uses a 404.html SPA
fallback: when a user navigates to /u/<username>/, the 404.html script stores
the real username in sessionStorage['__spa_username'] and redirects to the
pre-built static shell at /u/_/.  The UserProfilePageClient then reads the
session key, removes it, and loads the real profile.

When /u/_/ is opened directly (no sessionStorage entry), the app has no
username to resolve.  It must display "User not found." and must NOT attempt
to correct the URL to a valid username.

Test Steps
----------
1. Clear sessionStorage before navigation (ensured by a fresh browser context).
2. Navigate directly to <APP_URL>/u/_/.
3. Wait for the loading state to complete.
4. Assert: "User not found." message is visible.
5. Assert: URL remains at /u/_/ (no redirect to a valid username profile).

Expected Result
---------------
- "User not found." text is displayed.
- The browser URL ends with /u/_/ — it is not rewritten to /u/<username>/.

Environment Variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses UserProfilePage (Page Object) from testing/components/pages/user_profile_page/.
- Uses WebConfig for environment variable access.
- Playwright sync API with pytest function-scoped fixtures.
- No credentials required — this is a pure UI / client-side-state test.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.user_profile_page.user_profile_page import UserProfilePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FALLBACK_PATH = "/u/_/"
_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser():
    """Launch a single Chromium browser instance for the entire module."""
    with sync_playwright() as pw:
        cfg = WebConfig()
        b = pw.chromium.launch(headless=cfg.headless, slow_mo=cfg.slow_mo)
        yield b
        b.close()


@pytest.fixture()
def page(browser: Browser):
    """Fresh browser context per test — guarantees empty sessionStorage."""
    context = browser.new_context()
    pg = context.new_page()
    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fallback_url(base_url: str) -> str:
    return base_url.rstrip("/") + _FALLBACK_PATH


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDirectFallbackURLWithoutSessionData:
    """MYTUBE-306: /u/_/ opened without sessionStorage shows 'User not found'."""

    def test_user_not_found_message_is_displayed(
        self, page: Page, web_config: WebConfig
    ) -> None:
        """Navigating to /u/_/ without a stored username shows 'User not found.'"""
        url = _fallback_url(web_config.base_url)

        profile_page = UserProfilePage(page)
        # Navigate first — sessionStorage can only be read within a document origin.
        page.goto(url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

        # Confirm sessionStorage is clean (fresh context guarantees this, but we
        # check explicitly to document the precondition and catch regressions).
        stored = page.evaluate("() => sessionStorage.getItem('__spa_username')")
        assert stored is None, (
            f"Precondition failed: sessionStorage['__spa_username'] = {stored!r}; "
            "expected None (empty session)"
        )

        # Wait for the loading spinner to disappear.
        try:
            page.wait_for_selector("text=Loading…", state="hidden", timeout=15_000)
        except Exception:
            pass  # spinner absent — that's fine

        assert profile_page.is_not_found(timeout=15_000), (
            f"Expected 'User not found.' to be visible at {url} "
            f"when sessionStorage is empty. "
            f"Page URL after load: {page.url!r}. "
            f"Visible text sample: {page.inner_text('body')[:300]!r}"
        )

    def test_url_is_not_corrected_to_real_username(
        self, page: Page, web_config: WebConfig
    ) -> None:
        """URL must stay at /u/_/ — not rewritten to /u/<username>/ — when no session data exists."""
        url = _fallback_url(web_config.base_url)
        page.goto(url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

        # Give any potential client-side redirect time to execute.
        try:
            page.wait_for_url(
                lambda u: not u.rstrip("/").endswith("/u/_"),
                timeout=5_000,
            )
            # If we reach here, the URL was changed — note it for the assertion.
            final_url = page.url
        except Exception:
            # Timeout means URL stayed at /u/_/ — the expected behaviour.
            final_url = page.url

        assert "_" in final_url.rstrip("/").split("/")[-1], (
            f"URL was unexpectedly rewritten from {url!r} to {final_url!r}. "
            "When sessionStorage contains no username, the app must NOT correct the "
            "URL to a valid username profile."
        )
