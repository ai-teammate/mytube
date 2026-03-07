"""
MYTUBE-364: Fill form fields in upload and edit pages — input text is visible.

Objective
---------
Verify that text entered into multi-field forms (upload/edit) is visible to the user.

Preconditions
-------------
User is authenticated and navigated to the /upload page.

Steps
-----
1. Locate the Title and Description input fields.
2. Enter text into the Title field.
3. Enter a multi-line description into the Description field.

Expected Result
---------------
The text in both fields is clearly visible as it is typed. The styling remains
consistent across all form controls.

Environment variables
---------------------
- FIREBASE_TEST_EMAIL    : Email of the registered Firebase test user (required).
- FIREBASE_TEST_PASSWORD : Password for the test Firebase user (required).
- APP_URL / WEB_BASE_URL : Base URL of the deployed web app.
                           Default: https://ai-teammate.github.io/mytube
- PLAYWRIGHT_HEADLESS    : Run browser headless (default: true).
- PLAYWRIGHT_SLOW_MO     : Slow-motion delay in ms (default: 0).

Architecture
------------
- LoginPage page-object to authenticate.
- UploadPage page-object to fill and inspect form fields.
- WebConfig centralises all env-var access.
- Playwright ``expect`` assertions with built-in auto-wait.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, expect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.upload_page.upload_page import UploadPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_AUTH_TIMEOUT      = 20_000   # ms
_FIELD_TIMEOUT     = 10_000   # ms — max time to wait for form fields to appear

_TEST_TITLE       = "My Test Video Title"
_TEST_DESCRIPTION = "Line one of the description.\nLine two of the description.\nLine three."


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are absent."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-364. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-364. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    with sync_playwright() as pw:
        b = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield b
        b.close()


@pytest.fixture(scope="module")
def upload_page_fixture(browser: Browser, web_config: WebConfig):
    """Authenticate and navigate to the /upload page.

    Yields a dict with:
      page        – the Playwright Page object
      upload_page – the UploadPage page-object wrapping the page
    """
    context: BrowserContext = browser.new_context()
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    # Authenticate
    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    page.wait_for_url(
        lambda url: "/login" not in url,
        timeout=_AUTH_TIMEOUT,
    )

    # Navigate to /upload
    upload_pg = UploadPage(page)
    upload_pg.navigate(web_config.base_url)

    yield {"page": page, "upload_page": upload_pg}

    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadFormFieldVisibility:
    """MYTUBE-364: Text entered into upload form fields is visible to the user."""

    def test_title_field_is_visible_and_accepts_input(
        self,
        upload_page_fixture: dict,
    ) -> None:
        """Step 1-2: Locate the Title input and verify entered text is visible.

        The Title input must be present on the /upload page, accept typed text,
        and display that text so the user can see what they have entered.
        """
        page: Page = upload_page_fixture["page"]
        upload_pg: UploadPage = upload_page_fixture["upload_page"]

        # Step 1 — Title field must be present and visible
        title_locator = page.locator('input[id="title"]')
        title_locator.wait_for(state="visible", timeout=_FIELD_TIMEOUT)

        # Step 2 — Fill the Title field
        upload_pg.fill_title(_TEST_TITLE)

        # Assertion — the field value must equal what was typed
        expect(title_locator).to_have_value(_TEST_TITLE)

    def test_description_field_is_visible_and_accepts_multiline_input(
        self,
        upload_page_fixture: dict,
    ) -> None:
        """Step 1 & 3: Locate the Description textarea and verify multi-line text is visible.

        The Description textarea must be present on the /upload page, accept
        multi-line text input, and retain the full content so the user can
        read what they have typed.
        """
        page: Page = upload_page_fixture["page"]
        upload_pg: UploadPage = upload_page_fixture["upload_page"]

        # Step 1 — Description field must be present and visible
        description_locator = page.locator('textarea[id="description"]')
        description_locator.wait_for(state="visible", timeout=_FIELD_TIMEOUT)

        # Step 3 — Fill the Description field with multi-line text
        upload_pg.fill_description(_TEST_DESCRIPTION)

        # Assertion — the textarea value must equal what was typed
        expect(description_locator).to_have_value(_TEST_DESCRIPTION)

    def test_both_fields_retain_text_simultaneously(
        self,
        upload_page_fixture: dict,
    ) -> None:
        """Verify that Title and Description can both hold text at the same time.

        This checks the overall form state after both fields have been filled,
        ensuring no field clears or overwrites the other and the styling is
        consistent (both fields remain visible and enabled).
        """
        page: Page = upload_page_fixture["page"]

        title_locator = page.locator('input[id="title"]')
        description_locator = page.locator('textarea[id="description"]')

        # Both fields must be visible
        expect(title_locator).to_be_visible()
        expect(description_locator).to_be_visible()

        # Both fields must be enabled (not disabled/greyed-out)
        expect(title_locator).to_be_enabled()
        expect(description_locator).to_be_enabled()

        # Both fields must retain their previously typed values
        expect(title_locator).to_have_value(_TEST_TITLE)
        expect(description_locator).to_have_value(_TEST_DESCRIPTION)
