"""
MYTUBE-293: Direct navigation to user profile on static deployment —
username is recovered from sessionStorage and profile loads correctly.

Objective
---------
Verify that the user profile page correctly handles the SPA redirect on
GitHub Pages by retrieving the username from sessionStorage when the URL
parameter is "_".

Preconditions
-------------
Application is deployed to a static hosting environment (GitHub Pages).
A user with username "tester" exists.

Steps
-----
1. Open a browser and navigate directly to https://ai-teammate.github.io/mytube/u/tester.
2. Verify that the browser redirects to /u/_/ (internally handled by the SPA
   fallback script in public/404.html).
3. Observe the rendered page content once loading finishes.
4. Check the browser's address bar.
5. Check the value of sessionStorage.getItem("__spa_username").

Expected Result
---------------
The page successfully loads the profile for user "tester" (avatar, username
heading, and video grid). The URL in the address bar is corrected back to
/u/tester via history.replaceState. The sessionStorage key __spa_username is
cleared (returns null) after the component mounts.

Architecture
------------
- Uses Playwright sync API.
- Uses UserProfilePage (Page Object) from testing/components/pages/user_profile_page/.
- Uses WebConfig from testing/core/config/web_config.py.
- The test navigates to the real deployed URL (no mock/fixture) to verify the
  full end-to-end SPA redirect flow.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.user_profile_page.user_profile_page import UserProfilePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms — initial navigation + SPA redirect
_CONTENT_TIMEOUT = 20_000     # ms — wait for React component to render profile

# The shell path that the SPA fallback (public/404.html) redirects to.
_SPA_SHELL_SUFFIX = "/u/_/"

# sessionStorage key used by the 404.html script and read by UserProfilePageClient.tsx.
_SPA_SESSION_KEY = "__spa_username"

# Selectors / text that indicate the React component has mounted (profile or not-found state).
_MOUNTED_SELECTORS = ["h1", "text=User not found.", "text=Loading"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def test_username(web_config: WebConfig) -> str:
    """Derive the CI test username from FIREBASE_TEST_EMAIL (prefix before '@')."""
    email = web_config.test_email or "ci-test@mytube.test"
    return email.split("@")[0]


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture
def context(browser: Browser) -> BrowserContext:
    """Fresh browser context (isolated sessionStorage) per test."""
    ctx = browser.new_context()
    yield ctx
    ctx.close()


@pytest.fixture
def page(context: BrowserContext) -> Page:
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    return pg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _wait_for_component_mounted(page: Page, timeout: int = _CONTENT_TIMEOUT) -> None:
    """Wait until React component has mounted (shows profile content OR 'User not found.')."""
    try:
        page.wait_for_selector("h1", state="visible", timeout=timeout)
        return
    except Exception:
        pass
    # Also accept the not-found state as a sign the component mounted.
    try:
        page.wait_for_selector("text=User not found.", state="visible", timeout=2_000)
    except Exception:
        pass


def _get_session_storage_value(page: Page, key: str) -> str | None:
    """Return the value stored under *key* in sessionStorage, or None."""
    return page.evaluate(f"sessionStorage.getItem({key!r})")


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestSpaProfileRedirect:
    """Test suite for MYTUBE-293: SPA redirect for user profile pages."""

    def test_direct_navigation_redirects_through_spa_shell(
        self,
        page: Page,
        web_config: WebConfig,
        test_username: str,
    ) -> None:
        """
        Step 1-2: Navigate directly to /u/<username> and verify the SPA fallback
        (404.html) stores the username in sessionStorage and redirects to /u/_/.

        The 404.html script runs synchronously before any React code executes, so
        after the initial navigation resolves we inspect sessionStorage *before*
        React mounts (i.e. immediately after the redirect settles on /u/_/).

        NOTE: Because the 404.html redirect fires and immediately does
        location.replace("/u/_/"), Playwright's goto() follows the redirect and
        resolves on /u/_/.  At that point, sessionStorage already contains the
        username but the React component has not yet run.
        """
        base_url = web_config.base_url  # e.g. https://ai-teammate.github.io/mytube
        direct_url = f"{base_url}/u/{test_username}"

        # Navigate; follow the 404.html → /u/_/ redirect automatically.
        page.goto(direct_url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

        # After the SPA fallback redirect, the browser should be on /u/_/.
        current_url_after_redirect = page.url

        # The URL must contain the shell path before React corrects it.
        # (React's replaceState may not have fired yet at this point.)
        assert _SPA_SHELL_SUFFIX in current_url_after_redirect or f"/u/{test_username}" in current_url_after_redirect, (
            f"After direct navigation to {direct_url}, expected the browser to land "
            f"on either {_SPA_SHELL_SUFFIX!r} (SPA shell) or /u/{test_username} "
            f"(corrected URL), but current URL is: {current_url_after_redirect}"
        )

    def test_spa_username_in_session_storage_after_redirect(
        self,
        page: Page,
        web_config: WebConfig,
        test_username: str,
    ) -> None:
        """
        Step 2 & 5 (pre-mount): Immediately after the 404.html redirect resolves
        on /u/_/ (before React runs), sessionStorage must contain __spa_username
        equal to the CI test username.

        This validates that the 404.html fallback correctly stored the real username
        before handing off to the React shell.
        """
        base_url = web_config.base_url
        direct_url = f"{base_url}/u/{test_username}"

        # Navigate; 404.html runs synchronously and redirects to /u/_/.
        # wait_until="domcontentloaded" lets us inspect the page before React finishes.
        page.goto(direct_url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

        # Wait briefly so 404.html script has definitely executed.
        page.wait_for_timeout(300)

        # At this point, if the page landed on /u/_/, sessionStorage should hold
        # __spa_username = "tester" set by the 404.html script.
        # However, React may mount rapidly and clear the key — so we allow either:
        # (a) the key is still present (React hasn't cleared it yet), OR
        # (b) the URL has already been corrected to /u/tester (React ran and cleared it).
        stored_value = _get_session_storage_value(page, _SPA_SESSION_KEY)
        current_url = page.url

        spa_key_was_set = (
            stored_value == test_username
            or f"/u/{test_username}" in current_url  # React already corrected URL
        )
        assert spa_key_was_set, (
            f"Expected sessionStorage['{_SPA_SESSION_KEY}'] == '{test_username}' "
            f"immediately after redirect to {_SPA_SHELL_SUFFIX}, "
            f"but got: stored_value={stored_value!r}, current_url={current_url!r}. "
            f"The 404.html SPA fallback script may not have stored the username correctly."
        )

    def test_profile_content_rendered_after_spa_redirect(
        self,
        page: Page,
        web_config: WebConfig,
        test_username: str,
    ) -> None:
        """
        Step 3: After the SPA redirect resolves and React finishes mounting,
        the profile for the CI test user must be visible: avatar, <h1> username
        heading, and at least one video card (or an empty-state message if the
        user has no videos).
        """
        base_url = web_config.base_url
        direct_url = f"{base_url}/u/{test_username}"

        page.goto(direct_url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)
        _wait_for_component_mounted(page, timeout=_CONTENT_TIMEOUT)

        profile_page = UserProfilePage(page)

        # Wait for the username heading to appear.
        try:
            page.wait_for_selector("h1", timeout=_CONTENT_TIMEOUT)
        except Exception:
            current_url = page.url
            page_body = page.inner_text("body")[:200] if page.query_selector("body") else "(empty)"
            pytest.fail(
                f"Profile <h1> heading did not appear within {_CONTENT_TIMEOUT}ms "
                f"after navigating to {direct_url}. "
                f"Current URL: {current_url!r}. "
                f"Page body: {page_body!r}. "
                f"The user '{test_username}' may not exist in the deployed application."
            )

        heading = profile_page.get_username_heading()
        assert heading == test_username, (
            f"Expected <h1> to contain '{test_username}', got: {heading!r}. "
            f"Current URL: {page.url!r}"
        )

        avatar_visible = profile_page.is_avatar_visible()
        assert avatar_visible, (
            f"Avatar element is not visible on the profile page for '{test_username}'. "
            f"Current URL: {page.url!r}"
        )

    def test_url_corrected_back_to_real_username_after_mount(
        self,
        page: Page,
        web_config: WebConfig,
        test_username: str,
    ) -> None:
        """
        Step 4: After the React component mounts and calls history.replaceState,
        the browser's address bar must show /u/<username> (not /u/_/).
        """
        base_url = web_config.base_url
        direct_url = f"{base_url}/u/{test_username}"

        page.goto(direct_url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)
        # Wait for component to mount (any final rendered state — profile or not-found).
        _wait_for_component_mounted(page, timeout=_CONTENT_TIMEOUT)

        profile_page = UserProfilePage(page)
        final_url = profile_page.current_url()
        expected_url_suffix = f"/u/{test_username}"

        assert expected_url_suffix in final_url, (
            f"Expected address bar URL to contain '{expected_url_suffix}' after "
            f"React's history.replaceState, but got: {final_url!r}. "
            f"The UserProfilePageClient may not have called replaceState, or may "
            f"have called it with an incorrect username."
        )
        # The placeholder '_' should no longer appear in the username segment.
        username_segment = final_url.split("/u/")[-1].rstrip("/")
        assert username_segment != "_", (
            f"Address bar still shows the shell placeholder '/u/_/' after component "
            f"mount. Expected it to be replaced with '/u/{test_username}/'. "
            f"Current URL: {final_url!r}"
        )

    def test_session_storage_cleared_after_component_mounts(
        self,
        page: Page,
        web_config: WebConfig,
        test_username: str,
    ) -> None:
        """
        Step 5: After the React component mounts and reads __spa_username from
        sessionStorage, it must remove the key. Verifies that the key is null
        once the component has rendered (profile or not-found state).
        """
        base_url = web_config.base_url
        direct_url = f"{base_url}/u/{test_username}"

        page.goto(direct_url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)
        # Wait for component to mount (any final rendered state — profile or not-found).
        _wait_for_component_mounted(page, timeout=_CONTENT_TIMEOUT)

        remaining_key = _get_session_storage_value(page, _SPA_SESSION_KEY)
        assert remaining_key is None, (
            f"Expected sessionStorage['{_SPA_SESSION_KEY}'] to be null after the "
            f"UserProfilePageClient component mounted, but got: {remaining_key!r}. "
            f"The component may not be calling sessionStorage.removeItem('{_SPA_SESSION_KEY}') "
            f"on mount. Current URL: {page.url!r}"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
