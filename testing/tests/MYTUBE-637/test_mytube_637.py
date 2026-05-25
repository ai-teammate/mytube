"""
MYTUBE-637: Avatar upload API error — error message displayed and URL preserved.

Objective
---------
Verify that the UI handles backend upload failures gracefully without losing
existing data.

Preconditions
-------------
User is on the Account Settings page (/settings). The "Avatar URL" field
contains an existing valid URL.

Steps
-----
1. Log in with a valid Firebase test account.
2. Navigate to /settings.
3. Confirm the Avatar URL field contains an existing valid URL.
4. Select a valid image file.
5. Use Playwright route interception to simulate a backend failure (HTTP 500)
   on POST /api/me/avatar.
6. Click the "Upload" button.
7. Assert an inline error message is displayed near the upload control.
8. Assert the Avatar URL field still contains the original value.

Expected Result
---------------
- An inline error message (role="alert") is visible near the upload control.
- The existing value in the Avatar URL text field remains unchanged.

Architecture
------------
- LoginPage and SettingsPage Page Objects handle all DOM interactions.
- Playwright route interception mocks the avatar upload endpoint.
- WebConfig from testing/core/config/web_config.py provides all env vars.
- Credentials required: FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD.

Run from repo root:
    pytest testing/tests/MYTUBE-637/test_mytube_637.py -v
"""
from __future__ import annotations

import base64
import json
import os
import sys
import tempfile

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, Route

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000      # ms — max time for initial page load
_NAVIGATION_TIMEOUT = 25_000     # ms — max time to wait for post-login redirect
_UPLOAD_RESPONSE_TIMEOUT = 10_000  # ms — max time to wait for upload error to appear

# A pre-existing Avatar URL that should remain untouched after a failed upload.
_EXISTING_AVATAR_URL = "https://www.gstatic.com/webp/gallery/1.jpg"

# Minimal valid 1×1 white JPEG (base64-encoded) — used as the upload file.
_MINIMAL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
    "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARC"
    "AABAAEDASIA2gABAREA/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAIxAAAQMEAgMBAAAAAAAAAAAAAQIDBAAFESExQVFh"
    "/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAA"
    "AAAAAAAAAAAAAP/aAAwDAQACEQMRAD8Amk2pa3pVoiu3CqNOmTUoSVJDSwFKA9yBvXisWtd2vMiTHt8B2Q3GdLTi0DYSobBH3rF0"
    "/8QAHRABAAICAwEBAAAAAAAAAAAAAQIDBAAR"
    "ITIUQP/aAAgBAQABPxCk2e63S4SY8aI884y4UOJQNkKHIIPkEf0qw2O0W2wxVxrXEbiwFKA9yBvXisWtd2vMiTHt8B2Q"
    "3GdLTi0DYSobBH3rF0//2Q=="
)


def _make_minimal_jpeg() -> bytes:
    """Return bytes of a minimal valid JPEG (1×1 white pixel)."""
    # Use a hardcoded minimal JPEG rather than the b64 above to avoid padding issues.
    minimal = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0x01, 0x02, 0x03, 0x00, 0x04, 0x11, 0x05, 0x12, 0x21, 0x31, 0x41, 0x06,
        0x13, 0x51, 0x61, 0x07, 0x22, 0x71, 0x14, 0x32, 0x81, 0x91, 0xA1, 0x08,
        0x23, 0x42, 0xB1, 0xC1, 0x15, 0x52, 0xD1, 0xF0, 0x24, 0x33, 0x62, 0x72,
        0x82, 0x09, 0x0A, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x25, 0x26, 0x27, 0x28,
        0x29, 0x2A, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39, 0x3A, 0x43, 0x44, 0x45,
        0x46, 0x47, 0x48, 0x49, 0x4A, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
        0x5A, 0x63, 0x64, 0x65, 0x66, 0x67, 0x68, 0x69, 0x6A, 0x73, 0x74, 0x75,
        0x76, 0x77, 0x78, 0x79, 0x7A, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
        0x8A, 0x92, 0x93, 0x94, 0x95, 0x96, 0x97, 0x98, 0x99, 0x9A, 0xA2, 0xA3,
        0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9, 0xAA, 0xB2, 0xB3, 0xB4, 0xB5, 0xB6,
        0xB7, 0xB8, 0xB9, 0xBA, 0xC2, 0xC3, 0xC4, 0xC5, 0xC6, 0xC7, 0xC8, 0xC9,
        0xCA, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA, 0xE1, 0xE2,
        0xE3, 0xE4, 0xE5, 0xE6, 0xE7, 0xE8, 0xE9, 0xEA, 0xF1, 0xF2, 0xF3, 0xF4,
        0xF5, 0xF6, 0xF7, 0xF8, 0xF9, 0xFA, 0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01,
        0x00, 0x00, 0x3F, 0x00, 0xFB, 0xD2, 0x8A, 0x28, 0x03, 0xFF, 0xD9,
    ])
    return minimal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig):
    """Skip the entire module when Firebase test credentials are not provided."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-637 avatar upload error test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-637 avatar upload error test. "
            "Set FIREBASE_TEST_PASSWORD to run this test."
        )


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    """Launch a Chromium browser instance for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def authenticated_page(web_config: WebConfig, browser: Browser) -> Page:
    """Login once and return the authenticated page.

    1. Open a fresh browser context.
    2. Navigate to /login and sign in with the test Firebase account.
    3. Wait for redirect to home page confirming successful auth.
    4. Yield the page for subsequent fixture/test use.
    """
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

    login_page = LoginPage(page)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)

    login_page.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)

    yield page
    context.close()


@pytest.fixture(scope="module")
def tmp_jpeg_file() -> str:
    """Create a minimal valid JPEG file in a temp directory and return its path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp.write(_make_minimal_jpeg())
    tmp.flush()
    tmp.close()
    return tmp.name


@pytest.fixture(scope="module")
def initial_avatar_url(authenticated_page: Page, web_config: WebConfig) -> str:
    """Navigate to /settings, wait for the profile to fully load, and return the
    Avatar URL value currently in the field.

    The settings page fetches the user's profile via GET /api/me in a useEffect
    hook. We must wait for that network request to complete before recording the
    'initial' URL so that the async response doesn't overwrite our recorded value
    after the test interaction.
    """
    settings_url = f"{web_config.base_url}/settings/"
    page_obj = SettingsPage(authenticated_page)
    page_obj.navigate(settings_url)
    assert page_obj.is_settings_page_loaded(), (
        f"Settings page did not load within timeout. URL: {settings_url}"
    )
    # Wait for network to go idle so the /api/me profile fetch completes and
    # populates the Avatar URL field before we record its value.
    authenticated_page.wait_for_load_state("networkidle", timeout=15_000)
    return page_obj.get_avatar_url_value()


@pytest.fixture(scope="module")
def upload_error_triggered(
    authenticated_page: Page,
    web_config: WebConfig,
    tmp_jpeg_file: str,
    initial_avatar_url: str,
) -> SettingsPage:
    """Intercept POST /api/me/avatar to return HTTP 500, select a file, click
    Upload, and return the SettingsPage object ready for assertions.

    The intercepted route returns a 500 with a JSON error body so the UI can
    display the ``error`` field from the response.
    """
    settings_url = f"{web_config.base_url}/settings/"
    page_obj = SettingsPage(authenticated_page)

    # Re-navigate to ensure a fresh state (profile already loaded in initial_avatar_url).
    page_obj.navigate(settings_url)
    assert page_obj.is_settings_page_loaded(), (
        f"Settings page did not load within timeout. URL: {settings_url}"
    )
    # Wait for the profile fetch so the avatar URL field is stable.
    authenticated_page.wait_for_load_state("networkidle", timeout=15_000)

    # Step 5: Intercept POST /api/me/avatar to return HTTP 500.
    def _mock_500(route: Route) -> None:
        route.fulfill(
            status=500,
            content_type="application/json",
            body=json.dumps({"error": "Internal server error. Please try again later."}),
        )

    authenticated_page.route("**/api/me/avatar", _mock_500)

    try:
        # Step 4+6: Select the file and click Upload.
        page_obj.set_avatar_file(tmp_jpeg_file)
        page_obj.click_upload_button()

        # Wait long enough for the upload response to be processed by the UI.
        page_obj.get_upload_error_message(timeout=_UPLOAD_RESPONSE_TIMEOUT)
    finally:
        # Always unregister the route so it doesn't affect subsequent tests.
        authenticated_page.unroute("**/api/me/avatar")

    return page_obj


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarUploadApiError:
    """MYTUBE-637 — Upload failure shows inline error and preserves Avatar URL."""

    def test_upload_error_message_is_visible(
        self, upload_error_triggered: SettingsPage
    ) -> None:
        """An inline error alert must be visible near the upload control after a 500.

        The settings page renders ``<p role="alert">`` with the error text when
        the upload API returns a non-OK response.  This test verifies the alert
        is visible so the user knows the upload failed.
        """
        assert upload_error_triggered.is_upload_error_visible(timeout=5_000), (
            "Expected an inline upload error alert (p[role='alert']) to be visible "
            "after the avatar upload API returned HTTP 500, but no alert was found. "
            "The UI must display an error message near the upload control when the "
            "backend rejects the upload."
        )

    def test_upload_error_message_content(
        self, upload_error_triggered: SettingsPage
    ) -> None:
        """The error message must contain meaningful text describing the failure.

        The settings page sets uploadError to the JSON ``error`` field from the
        response, or falls back to 'Upload failed. Please try again.' if the
        body cannot be parsed.  Either way, the message must be non-empty.
        """
        error_text = upload_error_triggered.get_upload_error_message(timeout=5_000)
        assert error_text, (
            "The upload error alert (p[role='alert']) was visible but contained no "
            "text. Expected a non-empty error message from the server or a fallback "
            "'Upload failed. Please try again.' message."
        )
        # The mocked 500 response returns a JSON body with an 'error' key.
        # The UI should display that text (or a fallback).
        assert len(error_text.strip()) > 0, (
            f"Upload error alert text was empty or whitespace-only: {error_text!r}"
        )

    def test_avatar_url_field_preserved_on_upload_error(
        self, upload_error_triggered: SettingsPage, initial_avatar_url: str
    ) -> None:
        """The Avatar URL text field must retain its original value after a failed upload.

        A successful upload updates avatarUrl in React state; a failure must NOT
        change it.  This test verifies data preservation: the Avatar URL that was
        present before the upload attempt is still in the input field after the
        500 error is returned.
        """
        current_value = upload_error_triggered.get_avatar_url_value()
        assert current_value == initial_avatar_url, (
            f"The Avatar URL field value changed after a failed upload. "
            f"Expected (original URL before upload): {initial_avatar_url!r}. "
            f"Actual (URL after failed upload): {current_value!r}. "
            "The UI must not modify the Avatar URL field when the upload fails — "
            "the existing URL must be preserved so the user does not lose their data."
        )

    def test_upload_error_is_near_upload_control(
        self, upload_error_triggered: SettingsPage
    ) -> None:
        """The error alert must be visible in the upload section, not the save section.

        The upload error is rendered as a ``<p role='alert'>`` directly under the
        file input.  It is distinct from the save-form error (``<div role='alert'>``).
        This test confirms the element rendered is the paragraph-level inline alert.
        """
        # The settings page uses <p role="alert"> for upload errors and
        # <div role="alert"> for save errors. We only expect the <p> variant here.
        error_locator = upload_error_triggered._page.locator('p[role="alert"]')
        assert error_locator.count() > 0, (
            "Expected a <p role='alert'> element (inline upload error) to be present "
            "in the DOM after the avatar upload failed, but none was found. "
            "The upload error should be displayed inline near the upload control "
            "as a paragraph, not as a div-level alert."
        )
        assert error_locator.first.is_visible(), (
            "Found a <p role='alert'> element but it was not visible. "
            "The upload error message must be displayed to the user."
        )
