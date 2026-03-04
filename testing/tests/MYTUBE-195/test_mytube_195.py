"""
MYTUBE-195: Navigate to upload page via dashboard CTA — redirection successful.

Verifies that the "Upload new video" call-to-action on the dashboard correctly
links to the upload page, causing the browser to navigate to /upload when clicked.

Objective
---------
Verify that the "Upload new video" CTA on the /dashboard page correctly redirects
the user to the /upload page.

Preconditions
-------------
- User is authenticated and on the /dashboard page.
- The web application is deployed and reachable at WEB_BASE_URL.

Steps
-----
1. Register a fresh account to obtain an authenticated browser session.
2. Navigate to /dashboard.
3. Assert the "Upload new video" CTA is visible.
4. Click the "Upload new video" CTA.
5. Assert the browser URL contains /upload.

Expected Result
---------------
The browser navigates to the /upload page.

Authentication strategy
-----------------------
A fresh Firebase account is registered via /register for each test module run.
This makes the test self-contained — no pre-existing credentials or environment
variables are required beyond WEB_BASE_URL.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  : Base URL of the deployed web app.
                          Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses DashboardPage (Page Object) from testing/components/pages/dashboard_page/.
- Uses RegisterPage (Page Object) from testing/components/pages/register_page/.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest fixtures (module-scoped browser).
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.register_page.register_page import RegisterPage
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_REGISTER_TIMEOUT = 30_000    # ms
_VALID_PASSWORD = "TestPass195!"


def _unique_email() -> str:
    """Return a unique throwaway email address for test registration."""
    uid = uuid.uuid4().hex[:8]
    return f"test.mytube.195.{uid}@mailinator.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    """Open a fresh browser context with no stored auth state."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def dashboard_page(web_config: WebConfig, page: Page) -> DashboardPage:
    """Register a fresh Firebase account, then navigate to /dashboard.

    Skips the module gracefully if the app is unreachable or registration fails.
    Returns a DashboardPage instance already loaded at the dashboard URL.
    """
    register_page = RegisterPage(page)

    try:
        register_page.navigate(web_config.base_url)
    except Exception as exc:
        pytest.skip(
            f"Could not reach {web_config.base_url} — skipping test. Error: {exc}"
        )

    if not register_page.is_on_register_page():
        pytest.skip(
            f"Registration page did not load — URL: {register_page.current_url()}"
        )

    email = _unique_email()
    result = register_page.register_and_capture(
        email=email,
        password=_VALID_PASSWORD,
        base_url=web_config.base_url,
        timeout_ms=_REGISTER_TIMEOUT,
    )

    if not result.redirected_away:
        error = result.error_message or "Unknown error"
        pytest.skip(
            f"Registration did not redirect — cannot test dashboard CTA. "
            f"Error: {error!r}. Final URL: {result.final_url}"
        )

    dashboard = DashboardPage(page)
    dashboard.navigate(web_config.dashboard_url())
    return dashboard


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDashboardUploadCTA:
    """MYTUBE-195: Dashboard 'Upload new video' CTA navigates to /upload."""

    def test_upload_cta_is_visible_on_dashboard(
        self, dashboard_page: DashboardPage
    ) -> None:
        """The 'Upload new video' CTA must be visible on the dashboard page."""
        assert dashboard_page.is_upload_cta_visible(), (
            "Expected 'Upload new video' CTA to be visible on the /dashboard page, "
            "but it was not found."
        )

    def test_clicking_upload_cta_navigates_to_upload_page(
        self, dashboard_page: DashboardPage
    ) -> None:
        """Clicking the 'Upload new video' CTA must navigate to the /upload page."""
        # click_upload_new_video_cta() internally waits for the URL to contain /upload
        dashboard_page.click_upload_new_video_cta()

        current_url = dashboard_page.current_url()
        assert "/upload" in current_url, (
            f"Expected the browser to navigate to a URL containing '/upload' "
            f"after clicking the 'Upload new video' CTA on /dashboard, "
            f"but the URL is: {current_url!r}"
        )
