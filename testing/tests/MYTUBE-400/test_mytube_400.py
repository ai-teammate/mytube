"""
MYTUBE-400: Access application with active network — no authentication error alert displayed

Objective
---------
Verify that the application does not display the "Authentication services are currently unavailable" error alert when Firebase services are reachable and the session is valid.

Preconditions
-------------
- FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD are set to a valid test user.

Steps
-----
1. Log in to the application with a valid account.
2. Navigate to the dashboard.
3. Verify the presence of the header and app shell.
4. Inspect the UI for any elements with role="alert".

Expected Result
---------------
The application does not display the error message: "Authentication services are currently unavailable." No element with role="alert" is present in the header or app shell.
"""
from __future__ import annotations

import os

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from testing.core.config.web_config import WebConfig
from testing.components.global_alerts.global_alerts import GlobalAlerts
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.site_header.site_header import SiteHeader
from testing.components.pages.dashboard_page.dashboard_page import DashboardPage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials(web_config: WebConfig):
    """Skip the module when Firebase test credentials are absent."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-400."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-400."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser instance shared across all tests in the module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(headless=web_config.headless, slow_mo=web_config.slow_mo)
        yield br
        br.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNoAuthErrorWhenNetworkActive:
    """MYTUBE-400: With active network and valid session the auth-error alert must NOT be shown."""

    def test_no_auth_error_alert_displayed(self, browser: Browser, web_config: WebConfig) -> None:
        """Login and open dashboard; assert no auth-error alert in header or app shell."""
        ctx = browser.new_context()
        page: Page = ctx.new_page()
        page.set_default_timeout(20_000)

        try:
            # Step 1 — Login
            login_pg = LoginPage(page)
            login_pg.navigate(web_config.login_url())
            login_pg.login_as(web_config.test_email, web_config.test_password)

            # Wait until login redirect completes (leave /login)
            try:
                page.wait_for_url(lambda u: "/login" not in u, timeout=20_000)
            except Exception:
                # swallow — assertions will detect incorrect state
                pass

            # Step 2 — Navigate to dashboard
            dashboard = DashboardPage(page)
            dashboard.navigate(web_config.dashboard_url())
            dashboard.wait_for_load()

            # Step 3 — Verify header and app shell presence
            site_header = SiteHeader(page)
            assert site_header.logo_is_visible(), "Site header logo not visible — header may not have rendered"

            # Step 4 — Inspect for alert elements
            # Primary: header-scoped auth-error alert should NOT be present
            assert not site_header.has_auth_error_alert(), (
                "Unexpected auth-error alert present in header: 'Authentication services are currently unavailable'"
            )

            # Secondary: ensure no global alert with the specific auth-unavailable text
            global_alerts = GlobalAlerts(page)
            assert not global_alerts.has_auth_unavailable_alert(), (
                "Found unexpected auth-unavailable alert"
            )

        finally:
            ctx.close()
