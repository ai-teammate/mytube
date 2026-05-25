"""
MYTUBE-636: Client-side validation — file exceeds 5 MB → immediate error displayed.

Objective
---------
Verify that the Account Settings page prevents selecting an image file larger
than 5 MB by displaying a user-visible error message immediately in the UI,
without making any network request to the backend.

Preconditions
-------------
- User is on the Account Settings page (/settings).

Steps
-----
1. Navigate to /settings (login first if credentials are provided).
2. Simulate selecting an image file whose size exceeds 5 MB via the
   avatar file input (``id="avatar_file"``).
3. Assert that a ``<p role="alert">`` element appears immediately with the
   text "File is too large. Maximum size is 5 MB."
4. Assert that no network request was sent to the avatar upload endpoint
   (/api/me/avatar).

Expected Result
---------------
The error message "File is too large. Maximum size is 5 MB." is displayed
near the upload control without any network round-trip.

Architecture
------------
- WebConfig: base URL and credentials from environment variables.
- LoginPage: authentication flow.
- SettingsPage: page object with ``simulate_large_avatar_file()`` and
  ``wait_for_upload_error()`` / ``get_upload_error_text()``.
- Playwright route interception records upload requests to confirm none are made.

Environment variables
---------------------
APP_URL / WEB_BASE_URL      Base URL of the deployed web app.
                            Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL         Email for the test Firebase account (required).
FIREBASE_TEST_PASSWORD      Password for the test Firebase account (required).
PLAYWRIGHT_HEADLESS         Run headless (default: true).
PLAYWRIGHT_SLOW_MO          Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-636/test_mytube_636.py -v
"""
from __future__ import annotations

import os
import sys
from typing import List

import pytest
from playwright.sync_api import sync_playwright, Browser, Page, Request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.settings_page.settings_page import SettingsPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NAVIGATION_TIMEOUT = 25_000   # ms — wait for post-login redirect
_PAGE_LOAD_TIMEOUT = 30_000    # ms — default per-operation timeout
_ERROR_APPEAR_TIMEOUT = 5_000  # ms — error must appear within this window
_AVATAR_ENDPOINT_SUFFIX = "/api/me/avatar"
_EXPECTED_ERROR = "File is too large. Maximum size is 5 MB."
_FILE_SIZE_6MB = 6 * 1024 * 1024  # 6 MB — clearly over the 5 MB limit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module", autouse=True)
def require_credentials(web_config: WebConfig) -> None:
    """Skip the entire module when Firebase test credentials are not provided."""
    if not web_config.test_email:
        pytest.skip(
            "FIREBASE_TEST_EMAIL not set — skipping MYTUBE-636 client-side "
            "file-size validation test. "
            "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run."
        )
    if not web_config.test_password:
        pytest.skip(
            "FIREBASE_TEST_PASSWORD not set — skipping MYTUBE-636. "
            "Set FIREBASE_TEST_PASSWORD to run."
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


@pytest.fixture(scope="function")
def page(browser: Browser) -> Page:
    """Open a fresh browser context and page for each test."""
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="function")
def settings_page(page: Page) -> SettingsPage:
    return SettingsPage(page)


@pytest.fixture(scope="function")
def login_page(page: Page) -> LoginPage:
    return LoginPage(page)


@pytest.fixture(scope="function")
def authenticated_settings(
    web_config: WebConfig,
    login_page: LoginPage,
    settings_page: SettingsPage,
    page: Page,
) -> Page:
    """Authenticate and navigate to /settings. Yield the live Playwright Page."""
    # ---- Login ----
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)
    login_page.wait_for_navigation_to(
        web_config.home_url(), timeout=_NAVIGATION_TIMEOUT
    )
    # ---- Navigate to /settings ----
    settings_page.navigate(web_config.settings_url())
    yield page


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarFileSizeValidation:
    """MYTUBE-636: Avatar file > 5 MB triggers an immediate client-side error."""

    def test_oversized_file_shows_error_message(
        self,
        authenticated_settings: Page,
        settings_page: SettingsPage,
    ) -> None:
        """Selecting a file > 5 MB must render the error alert immediately.

        The ``handleFileChange`` handler in settings/page.tsx reads
        ``file.size`` synchronously; if it exceeds 5 MB it sets the
        ``uploadError`` React state, which renders
        ``<p role="alert">File is too large. Maximum size is 5 MB.</p>``
        without any async I/O.
        """
        # Simulate selecting a 6 MB JPEG via the file input.
        settings_page.simulate_large_avatar_file(size_bytes=_FILE_SIZE_6MB)

        # The error must appear without any additional trigger.
        settings_page.wait_for_upload_error(timeout=_ERROR_APPEAR_TIMEOUT)

        actual_error = settings_page.get_upload_error_text()
        assert actual_error == _EXPECTED_ERROR, (
            f"Expected upload error message: {_EXPECTED_ERROR!r}\n"
            f"Actual upload error message:  {actual_error!r}\n"
            "The client-side size validation must set uploadError to the exact "
            "string 'File is too large. Maximum size is 5 MB.' when the selected "
            "file exceeds the 5 MB limit."
        )

    def test_oversized_file_does_not_trigger_network_request(
        self,
        web_config: WebConfig,
        login_page: LoginPage,
        page: Page,
    ) -> None:
        """No POST to /api/me/avatar must occur when the client rejects the file.

        A fresh page/context is used so the request log is clean.  Route
        interception records every request that matches the avatar endpoint.
        """
        captured_upload_requests: List[Request] = []

        def _on_request(req: Request) -> None:
            if _AVATAR_ENDPOINT_SUFFIX in req.url:
                captured_upload_requests.append(req)

        page.on("request", _on_request)

        # Authenticate and reach /settings.
        lp = LoginPage(page)
        lp.navigate(web_config.login_url())
        lp.login_as(web_config.test_email, web_config.test_password)
        lp.wait_for_navigation_to(web_config.home_url(), timeout=_NAVIGATION_TIMEOUT)

        sp = SettingsPage(page)
        sp.navigate(web_config.settings_url())

        # Simulate the oversized file selection.
        sp.simulate_large_avatar_file(size_bytes=_FILE_SIZE_6MB)

        # Wait long enough for any async validation + potential XHR to fire.
        sp.wait_for_upload_error(timeout=_ERROR_APPEAR_TIMEOUT)

        # Give a short additional window for any rogue async request.
        page.wait_for_timeout(1_000)

        assert len(captured_upload_requests) == 0, (
            f"Expected 0 network requests to '{_AVATAR_ENDPOINT_SUFFIX}' when "
            f"the file is rejected client-side, but found "
            f"{len(captured_upload_requests)} request(s):\n"
            + "\n".join(
                f"  [{r.method}] {r.url}" for r in captured_upload_requests
            )
        )
