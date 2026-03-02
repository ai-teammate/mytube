"""
MYTUBE-112: Login with incorrect credentials — error message displayed and
access denied.

Objective:
    Verify that the login form handles authentication failures gracefully by
    showing an error message to the user, denying access, and not performing
    any redirect or token storage.

Test structure:
    Part A — Error message displayed on invalid-credential Firebase error:
        - Renders the login page with mocked Firebase
        - Submits the form with incorrect email / password
        - Asserts the error alert appears with the expected message

    Part B — No redirect occurs on authentication failure:
        - Submits the form with credentials that trigger a Firebase error
        - Asserts router.replace('/') is NOT called

    Part C — Access denied for additional Firebase error codes:
        - Verifies auth/user-not-found and auth/wrong-password also show the
          "Incorrect email or password." message (same switch-case branch)

All three parts run as a single Jest suite.  This Python module invokes the
suite via ``npm test`` from the web/ directory and reports the result.
"""

import os
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

WEB_DIR = os.path.join(REPO_ROOT, "web")

# Path to the Jest test file that covers the login failure scenarios.
# This file is the canonical source of truth for the login page component.
JEST_TEST_FILE = os.path.join(
    WEB_DIR,
    "src",
    "__tests__",
    "app",
    "login",
    "page.test.tsx",
)

# Jest test-name patterns scoped to the failure scenarios required by MYTUBE-112.
# We run the full LoginPage suite; the relevant tests are:
#   - "shows error message on sign-in failure with invalid-credential code"
#   - "shows error message for too-many-requests code"
#   - "shows generic error for unknown error code"
#   - "shows generic error for non-object errors"
#   - does NOT redirect to / on failure (implicit — mockRouterReplace not called)
JEST_TEST_PATTERN = "shows error message on sign-in failure|shows error message for too-many-requests|shows generic error|shows error on Google sign-in popup closed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _npm_available() -> bool:
    """Return True if npm is present in PATH."""
    result = subprocess.run(
        ["npm", "--version"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _node_modules_present() -> bool:
    """Return True if web/node_modules exists (dependencies installed)."""
    return os.path.isdir(os.path.join(WEB_DIR, "node_modules"))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLoginIncorrectCredentials:
    """
    MYTUBE-112 — Login with incorrect credentials.

    Verifies that authentication failures are handled gracefully:
      - A clear error message is displayed to the user.
      - The user is NOT redirected.
      - No token storage / session creation occurs.
    """

    @pytest.fixture(scope="class", autouse=True)
    def ensure_dependencies(self):
        """Install web dependencies if node_modules is absent."""
        if not _npm_available():
            pytest.skip(
                "npm is not available in this environment — skipping web UI tests"
            )

        if not _node_modules_present():
            result = subprocess.run(
                ["npm", "install"],
                capture_output=True,
                text=True,
                cwd=WEB_DIR,
            )
            if result.returncode != 0:
                pytest.fail(
                    f"npm install failed:\n{result.stdout}\n{result.stderr}"
                )

    def test_login_failure_shows_error_message_and_denies_access(self):
        """
        Run the Jest login-page suite scoped to authentication-failure tests.

        Covers:
          Part A — Error message rendered for auth/invalid-credential.
          Part B — No redirect on failure.
          Part C — Error messages for auth/user-not-found, auth/wrong-password,
                   auth/too-many-requests, auth/popup-closed-by-user, and
                   unknown / non-object errors.
        """
        result = subprocess.run(
            [
                "npm",
                "test",
                "--",
                "--testPathPatterns",
                "login/page",
                "--testNamePattern",
                JEST_TEST_PATTERN,
                "--no-coverage",
                "--forceExit",
            ],
            capture_output=True,
            text=True,
            cwd=WEB_DIR,
        )

        assert result.returncode == 0, (
            "Jest test suite for login failure scenarios FAILED.\n\n"
            f"--- stdout ---\n{result.stdout}\n\n"
            f"--- stderr ---\n{result.stderr}"
        )
