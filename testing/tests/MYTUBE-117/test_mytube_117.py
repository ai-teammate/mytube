"""
MYTUBE-117: Access profile of non-existent user — application returns 404.

Objective
---------
Verify that the system handles requests for non-existent usernames correctly.

Steps
-----
1. Navigate to /u/non_existent_user_999.

Expected Result
---------------
The application displays a 404 Not Found error (or "User not found." message)
for the page, or the API returns a 404 JSON response when accessed directly.

Test coverage
-------------
Part A — Jest unit tests (data layer):
    Verifies ApiUserProfileRepository.getByUsername() returns null when the
    backend API responds with HTTP 404.  This is the repository-level 404
    handling for GET /api/users/<username>.

Part B — Jest unit tests (component layer):
    Verifies the UserProfilePage React component renders "User not found."
    when the repository returns null (the null case caused by a 404 response).

Part C — Playwright end-to-end test:
    Navigates the deployed web application to /u/non_existent_user_999 and
    asserts the "User not found." message is rendered.
    Skipped automatically when the APP_URL is not reachable.

Architecture notes
------------------
- Test type: web (Jest + Playwright)
- Parts A & B run the existing Jest suites which prove the full 404 handling
  path at unit level without requiring a live server.
- Part C requires a reachable APP_URL and is skipped in environments where the
  deployed frontend is unavailable.
- WebConfig drives APP_URL for all URL construction.
- No hardcoded URLs, credentials, or sleeps.
"""
from __future__ import annotations

import os
import subprocess
import sys
import urllib.request
import urllib.error

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.user_profile_page.user_profile_page import (
    UserProfilePage,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_NON_EXISTENT_USERNAME = "non_existent_user_999"

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_WEB_DIR = os.path.join(_REPO_ROOT, "web")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _node_modules_present() -> bool:
    return os.path.isdir(os.path.join(_WEB_DIR, "node_modules"))


def _npm_available() -> bool:
    result = subprocess.run(
        ["npm", "--version"], capture_output=True, text=True
    )
    return result.returncode == 0


def _is_url_reachable(url: str, timeout: int = 10) -> bool:
    """Return True if the URL returns a non-4xx/5xx response."""
    try:
        req = urllib.request.Request(url, method="GET")
        res = urllib.request.urlopen(req, timeout=timeout)
        return res.status < 400
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Part A — Jest unit tests: data layer (ApiUserProfileRepository)
# ---------------------------------------------------------------------------


class TestUserProfileRepositoryReturnsNullOn404:
    """
    MYTUBE-117 Part A: repository-level 404 handling.

    ApiUserProfileRepository.getByUsername() must return null when the backend
    API responds with HTTP 404 for an unknown username.
    """

    @pytest.fixture(scope="class", autouse=True)
    def ensure_dependencies(self):
        if not _npm_available():
            pytest.skip("npm not available — skipping Jest unit tests")
        if not _node_modules_present():
            result = subprocess.run(
                ["npm", "install"],
                capture_output=True,
                text=True,
                cwd=_WEB_DIR,
            )
            if result.returncode != 0:
                pytest.fail(
                    f"npm install failed:\n{result.stdout}\n{result.stderr}"
                )

    def test_repository_returns_null_when_api_returns_404(self):
        """
        Jest: ApiUserProfileRepository.getByUsername() returns null on 404.

        Confirms the repository maps HTTP 404 to null, which the UI component
        then maps to the 'User not found.' message.
        """
        result = subprocess.run(
            [
                "npm",
                "test",
                "--",
                "--testPathPatterns=src/__tests__/data/userProfileRepository.test.ts",
                "--testNamePattern=returns null when the API responds with 404",
                "--no-coverage",
                "--forceExit",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            cwd=_WEB_DIR,
            timeout=120,
        )

        assert result.returncode == 0, (
            "Jest test 'returns null when the API responds with 404' FAILED.\n\n"
            f"--- stdout ---\n{result.stdout}\n\n"
            f"--- stderr ---\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Part B — Jest unit tests: component layer (UserProfilePage)
# ---------------------------------------------------------------------------


class TestUserProfilePageShowsNotFoundMessage:
    """
    MYTUBE-117 Part B: component-level not-found rendering.

    The UserProfilePage component must render 'User not found.' when the
    repository returns null (the null value produced by a 404 API response).
    """

    @pytest.fixture(scope="class", autouse=True)
    def ensure_dependencies(self):
        if not _npm_available():
            pytest.skip("npm not available — skipping Jest unit tests")
        if not _node_modules_present():
            result = subprocess.run(
                ["npm", "install"],
                capture_output=True,
                text=True,
                cwd=_WEB_DIR,
            )
            if result.returncode != 0:
                pytest.fail(
                    f"npm install failed:\n{result.stdout}\n{result.stderr}"
                )

    def test_component_shows_not_found_when_profile_is_null(self):
        """
        Jest: UserProfilePage renders 'User not found.' when repository returns null.

        This covers the full client-side 404 handling path:
        API returns 404 → repository returns null → component renders
        'User not found.' message.
        """
        result = subprocess.run(
            [
                "npm",
                "test",
                "--",
                "--testPathPatterns=src/__tests__/app/u/page.test.tsx",
                "--testNamePattern=shows not-found message when profile is null",
                "--no-coverage",
                "--forceExit",
                "--verbose",
            ],
            capture_output=True,
            text=True,
            cwd=_WEB_DIR,
            timeout=120,
        )

        assert result.returncode == 0, (
            "Jest test 'shows not-found message when profile is null' FAILED.\n\n"
            f"--- stdout ---\n{result.stdout}\n\n"
            f"--- stderr ---\n{result.stderr}"
        )

        combined = result.stdout + result.stderr
        assert "shows not-found message when profile is null" in combined, (
            "Expected Jest test case name to appear in output, but it was not found.\n"
            f"Full output:\n{combined}"
        )


# ---------------------------------------------------------------------------
# Part C — Playwright end-to-end test (requires reachable APP_URL)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def skip_if_unreachable(web_config: WebConfig):
    """Skip Playwright tests when the deployed frontend URL is not reachable."""
    home_url = web_config.base_url + "/"
    if not _is_url_reachable(home_url):
        pytest.skip(
            f"Deployed frontend at {web_config.base_url} is not reachable — "
            "skipping Playwright E2E tests. Set APP_URL to a live instance to run."
        )


@pytest.fixture(scope="module")
def browser(skip_if_unreachable):
    """Launch headless Chromium for the whole module."""
    with sync_playwright() as p:
        br = p.chromium.launch(headless=True)
        yield br
        br.close()


@pytest.fixture()
def page(browser):
    """Fresh browser context and page per test."""
    context = browser.new_context()
    pg = context.new_page()
    yield pg
    context.close()


@pytest.fixture()
def user_profile_page(page) -> UserProfilePage:
    return UserProfilePage(page)


class TestUserProfileNotFoundE2E:
    """
    MYTUBE-117 Part C: end-to-end Playwright test against the deployed app.

    Navigates to /u/non_existent_user_999 on the live frontend and asserts
    that the application correctly renders the 'User not found.' message.

    This test class is skipped when the APP_URL is not reachable.
    """

    def test_non_existent_user_profile_shows_not_found_message(
        self,
        user_profile_page: UserProfilePage,
        web_config: WebConfig,
    ):
        """
        Navigating to /u/non_existent_user_999 must display 'User not found.'

        The frontend calls GET /api/users/non_existent_user_999 which returns
        HTTP 404.  The page component maps that to null and renders the
        not-found message.
        """
        user_profile_page.navigate_to_user(
            web_config.base_url, _NON_EXISTENT_USERNAME
        )

        assert user_profile_page.is_not_found(), (
            f"Expected 'User not found.' to be visible after navigating to "
            f"/u/{_NON_EXISTENT_USERNAME}, but it was not found on the page. "
            f"Current URL: {user_profile_page.current_url()}"
        )

    def test_non_existent_user_profile_url_is_accessible(
        self,
        user_profile_page: UserProfilePage,
        web_config: WebConfig,
    ):
        """
        The /u/non_existent_user_999 URL must load without a browser-level error.

        No network failure, no uncaught exception — the page loads and handles
        the 404 gracefully.
        """
        errors: list[str] = []
        user_profile_page._page.on(
            "pageerror", lambda err: errors.append(str(err))
        )

        user_profile_page.navigate_to_user(
            web_config.base_url, _NON_EXISTENT_USERNAME
        )

        # Wait for the not-found message to confirm the page settled.
        user_profile_page.is_not_found()

        assert not errors, (
            f"Unexpected JavaScript errors on /u/{_NON_EXISTENT_USERNAME}: "
            + "; ".join(errors)
        )
