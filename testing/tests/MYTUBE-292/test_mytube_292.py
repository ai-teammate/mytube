"""
MYTUBE-292: Refresh category page on static deployment — dynamic route ID is maintained and error alert is avoided.

Objective
---------
Verify that performing a browser refresh on a category page in a static environment
(GitHub Pages) does not result in the dynamic route ID being lost or an
"Invalid category" error.

Preconditions
-------------
- Application is deployed to a static hosting environment (GitHub Pages).
- The web app is accessible at WEB_BASE_URL / APP_URL.

Test Steps
----------
1. Navigate to a specific category page (e.g. /category/3/).
2. Wait for the category content and video grid to load.
3. Perform a browser refresh.
4. Observe the URL and page content after the reload completes.

Expected Result
---------------
- The URL remains /category/3/ (not /category/_/).
- The h1 heading is visible with no "Invalid category" error.
- No error alert is shown.

Architecture
------------
- CategoryPage (Page Object) from testing/components/pages/category_page/.
- WebConfig from testing/core/config/web_config.py.
- Playwright sync API.

Environment Variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the web application.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser in headless mode (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.category_page.category_page import CategoryPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000       # ms
_CONTENT_TIMEOUT = 15_000         # ms
_CATEGORY_ID = 3                  # Category ID used throughout the test

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    """Return a WebConfig loaded from environment variables."""
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a single Chromium browser for the test module."""
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    """Return a new page with a default navigation timeout."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCategoryPageRefresh:
    """MYTUBE-292: Refresh on static deployment keeps dynamic route ID intact."""

    def test_initial_navigation_loads_category(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """
        Step 1 & 2: Navigate to /category/3/ and verify the category content loads.

        On GitHub Pages the request hits 404.html, which stores the ID in
        sessionStorage and redirects to /category/_/.  The client component
        resolves the stored ID and corrects the URL to /category/3/ via
        history.replaceState.
        """
        category_page = CategoryPage(page)
        try:
            category_page.navigate(web_config.base_url, _CATEGORY_ID)
        except Exception as exc:
            pytest.skip(
                f"Could not reach the web app at {web_config.base_url}: {exc}. "
                "Set APP_URL or WEB_BASE_URL to the deployed instance."
            )

        state = category_page.get_state()

        # An empty [role='alert'] live region is always present on the page as
        # an ARIA affordance — only a non-empty error text indicates a real error.
        assert not (state.has_error and state.error_text), (
            f"Step 2 failed: An error alert with content is visible before refresh. "
            f"Error text: {state.error_text!r}. "
            f"This indicates the category ID was not resolved correctly on initial load."
        )
        assert not state.is_loading, (
            "Step 2 failed: The page is still in loading state after waiting for content."
        )
        assert state.category_name is not None, (
            "Step 2 failed: No <h1> heading found after navigating to /category/3/. "
            "The category content did not render."
        )

    def test_initial_url_does_not_contain_placeholder(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """
        After initial navigation the URL must be /category/3/, not /category/_/.

        The client component calls history.replaceState to correct the URL
        from the shell path /category/_/ back to the real path /category/3/.
        If this correction is absent the URL will contain the placeholder segment.
        """
        category_page = CategoryPage(page)
        current_url = category_page.current_url()

        assert "/category/_/" not in current_url, (
            f"Step 2 (URL check) failed: URL still shows placeholder /category/_/ "
            f"after initial load. Actual URL: {current_url!r}. "
            f"The history.replaceState correction in CategoryPageClient was not applied."
        )
        assert f"/category/{_CATEGORY_ID}/" in current_url, (
            f"Step 2 (URL check) failed: Expected URL to contain /category/{_CATEGORY_ID}/ "
            f"but got {current_url!r}."
        )

    def test_refresh_restores_category_content(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """
        Step 3 & 4: Perform a browser refresh and verify the page reloads correctly.

        On GitHub Pages a hard reload of /category/3/ triggers the 404.html
        fallback again.  The fallback must store the ID (3) in sessionStorage and
        redirect to /category/_/; the client component must read it back and
        correct the URL once more.

        Assertions
        ----------
        - No "Invalid category" error is displayed.
        - The <h1> heading is present (category name or fallback label rendered).
        - The URL does not contain the placeholder segment /category/_/.
        - The URL contains /category/3/.
        """
        category_page = CategoryPage(page)

        # Step 3: Reload the page (equivalent to pressing Ctrl+R / Cmd+R).
        page.reload(wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

        # Wait specifically for the <h1> heading to appear after reload.
        # The SPA fallback goes: /category/3/ → 404.html → /category/_/ →
        # JS reads sessionStorage → history.replaceState to /category/3/ → load content.
        # We must wait for h1 (content ready) rather than [role='alert'] (always present).
        try:
            page.wait_for_selector(
                "h1",
                state="visible",
                timeout=_CONTENT_TIMEOUT,
            )
        except Exception:
            # If h1 doesn't appear, check for error state in assertions below.
            pass

        state = category_page.get_state()
        current_url = category_page.current_url()

        # Step 4 assertions -------------------------------------------------

        assert not (state.has_error and state.error_text), (
            f"Step 4 failed: An error alert with content appeared after refresh. "
            f"Error text: {state.error_text!r}. "
            f"Current URL: {current_url!r}. "
            f"This means the category ID was not preserved across the refresh cycle — "
            f"the sessionStorage fallback in 404.html or the ID resolution in "
            f"CategoryPageClient.tsx did not work correctly after reload."
        )

        assert not state.is_loading, (
            f"Step 4 failed: The page is still in loading state after refresh. "
            f"Current URL: {current_url!r}."
        )

        assert state.category_name is not None, (
            f"Step 4 failed: No <h1> heading found after refresh. "
            f"Current URL: {current_url!r}. "
            f"The category content did not render after the reload cycle."
        )

        assert "/category/_/" not in current_url, (
            f"Step 4 (URL check) failed: URL contains placeholder /category/_/ after refresh. "
            f"Actual URL: {current_url!r}. "
            f"The history.replaceState correction was not applied after the reload."
        )

        assert f"/category/{_CATEGORY_ID}/" in current_url, (
            f"Step 4 (URL check) failed: Expected URL to contain /category/{_CATEGORY_ID}/ "
            f"after refresh but got {current_url!r}."
        )


# ---------------------------------------------------------------------------
# Entry point for direct pytest invocation
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
