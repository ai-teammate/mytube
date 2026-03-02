"""
MYTUBE-109: Register new account via UI — account created and upsert API triggered.

Verifies that:
  1. The /register page renders the registration form correctly.
  2. Submitting a valid new email + password creates a Firebase account.
  3. After successful registration, the app calls GET /api/me (detected via
     network interception) to trigger the backend database upsert.
  4. The user is then redirected away from /register (to the home page).

Architecture notes
------------------
- Test type: web UI (Playwright, headless Chromium)
- The Firebase Auth emulator is NOT used; the test targets the deployed
  application which talks to the production Firebase project.
- Network interception captures the GET /api/me call that the register page
  makes after Firebase account creation to provision the backend user row.
- A unique email address is generated per test run to satisfy the precondition
  that the email is not already registered.
- Page interactions are delegated to RegisterPage (Page Object pattern).
- Configuration (base URL) is loaded from WebConfig via the APP_URL env var.
"""
from __future__ import annotations

import os
import sys
import uuid

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.register_page.register_page import RegisterPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_PASSWORD = "TestPass123!"
"""A password that satisfies Firebase's minimum-6-characters requirement."""


def _unique_email() -> str:
    """Generate a unique email address that cannot already be registered."""
    uid = uuid.uuid4().hex[:8]
    return f"test.mytube.{uid}@mailinator.com"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser():
    """Launch a headless Chromium instance for the whole module."""
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        yield br
        br.close()


@pytest.fixture()
def page(browser):
    """Create a fresh browser context + page for each test."""
    context = browser.new_context()
    pg = context.new_page()
    yield pg
    context.close()


@pytest.fixture()
def register_page(page) -> RegisterPage:
    return RegisterPage(page)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRegisterPageLoads:
    """The /register page must be accessible and render the registration form."""

    def test_register_page_heading_is_visible(
        self, register_page: RegisterPage, web_config: WebConfig
    ):
        """Navigating to /register must display the 'Create an account' heading."""
        register_page.navigate(web_config.base_url)
        assert register_page.is_on_register_page(), (
            "Registration form heading 'Create an account' was not found on the page. "
            f"Current URL: {register_page._page.url}"
        )


class TestRegistrationFlow:
    """Full registration flow: Firebase account created, /api/me called, redirected."""

    def test_successful_registration_redirects_away(
        self, register_page: RegisterPage, web_config: WebConfig
    ):
        """After registering with a new email, the user must be redirected from /register."""
        register_page.navigate(web_config.base_url)

        email = _unique_email()
        result = register_page.register_and_capture(
            email=email,
            password=_VALID_PASSWORD,
            base_url=web_config.base_url,
        )

        assert result.redirected_away, (
            f"Expected redirect away from /register after successful registration, "
            f"but final URL was: {result.final_url}. "
            f"Error shown: {result.error_message!r}"
        )

    def test_successful_registration_calls_api_me(
        self, register_page: RegisterPage, web_config: WebConfig
    ):
        """After Firebase account creation, GET /api/me must be called to upsert the backend user."""
        register_page.navigate(web_config.base_url)

        email = _unique_email()
        result = register_page.register_and_capture(
            email=email,
            password=_VALID_PASSWORD,
            base_url=web_config.base_url,
        )

        assert result.api_me_called, (
            "Expected GET /api/me to be called after registration to trigger backend "
            "user upsert, but no such request was observed in the network log. "
            f"Final URL: {result.final_url}. Error shown: {result.error_message!r}"
        )

    def test_no_error_shown_on_successful_registration(
        self, register_page: RegisterPage, web_config: WebConfig
    ):
        """A successful registration must not display any error alert."""
        register_page.navigate(web_config.base_url)

        email = _unique_email()
        result = register_page.register_and_capture(
            email=email,
            password=_VALID_PASSWORD,
            base_url=web_config.base_url,
        )

        assert result.error_message is None, (
            f"Expected no error on successful registration, "
            f"but error was shown: {result.error_message!r}"
        )
