"""
MYTUBE-240: Navigate to registration page — page loads and "Create an account" heading is visible.

Objective
---------
Verify that the registration page is correctly served by the deployment environment and displays
the required UI elements.

Steps
-----
1. Navigate directly to the registration URL: https://ai-teammate.github.io/mytube/register/
2. Observe the page status and content.
3. Verify the presence of the main page heading.

Expected Result
---------------
The page loads successfully without an HTTP 404 error. An h1 heading with the text
"Create an account" is visible on the page.

Test approach
-------------
Uses the RegisterPage Page Object to encapsulate all interactions with the registration form.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses RegisterPage (Page Object) from testing/components/pages/register_page/
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.register_page.register_page import RegisterPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=web_config.headless, slow_mo=web_config.slow_mo)
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser) -> Page:
    """A page for navigation and assertions."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def loaded_register_page(page: Page, web_config: WebConfig) -> RegisterPage:
    """Navigate to the registration page and return a RegisterPage instance."""
    register = RegisterPage(page)
    register.navigate(web_config.base_url)
    yield register


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNavigateToRegistrationPage:
    """MYTUBE-240: Navigate to registration page — page loads and "Create an account" heading is visible."""

    def test_page_loads_successfully(self, loaded_register_page: RegisterPage) -> None:
        """The registration page must load without a 404 error."""
        url = loaded_register_page.current_url()
        assert "/register" in url, f"Expected /register in URL, but got {url}"
        # Verify the page actually loaded the registration form
        # (RegisterPage.navigate() waits for h1, so we reach here only if it found it)
        assert loaded_register_page.is_on_register_page(), (
            "Expected to see 'Create an account' heading on registration page"
        )

    def test_create_account_heading_is_visible(self, loaded_register_page: RegisterPage) -> None:
        """An h1 heading with text 'Create an account' must be visible on the page."""
        heading_visible = loaded_register_page.is_on_register_page()
        assert heading_visible, (
            "Expected 'Create an account' heading to be visible. "
            "The registration page may not have loaded correctly."
        )
