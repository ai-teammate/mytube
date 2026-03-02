"""
MYTUBE-108: Sign in with Google — user authenticated via Firebase and redirected.

This test verifies that clicking "Sign in with Google" on the /login page:
  1. Calls Firebase signInWithPopup with a GoogleAuthProvider.
  2. On successful authentication, the user object is stored in the auth context
     (ID token accessible via getIdToken).
  3. The user is redirected to the home page (/).

Because Google OAuth requires a real browser popup that cannot be driven by
automated tooling in CI, this test delegates to the existing Jest + React
Testing Library suite in web/src/__tests__/app/login/page.test.tsx.

The Jest tests mock Firebase's signInWithPopup and the AuthContext to confirm
the component wires everything correctly:
  - Google button click → signInWithPopup is called (1 invocation)
  - Successful popup response → router.replace("/") is called
  - signInWithPopup result user has getIdToken accessible in auth state

Run from the repo root:
    pytest testing/tests/MYTUBE-108/test_mytube_108.py -v
"""
import subprocess
import os
import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WEB_DIR = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "web")
)
TEST_PATTERN = "__tests__/app/login/page.test.tsx"


def _run_jest(extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run the Jest test suite for the login page inside web/ and return the result."""
    cmd = [
        "npm",
        "test",
        "--",
        f"--testPathPatterns={TEST_PATTERN}",
        "--verbose",
        "--no-coverage",
        "--forceExit",
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        cwd=WEB_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGoogleSignIn:
    """MYTUBE-108: Verify Google Sign-In flow authenticates and redirects."""

    def test_google_signin_full_suite_passes(self):
        """
        All Google sign-in related test cases pass:
          - signInWithPopup called once
          - router.replace('/') called on success
          - auth/popup-closed-by-user error shows user-friendly message
          - signInWithPopup result user has getIdToken accessible in auth state

        This is the authoritative end-to-end assertion for MYTUBE-108.
        """
        result = _run_jest()
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"Login page Jest test suite FAILED (exit code {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n"
            f"=== STDERR ===\n{result.stderr}"
        )

        google_cases = [
            "calls signInWithPopup on Google sign-in button click",
            "redirects to / on successful Google sign-in",
            "shows error on Google sign-in popup closed",
            "Google sign-in result user has getIdToken accessible in auth state",
        ]
        for case in google_cases:
            assert case in combined, (
                f"Expected Jest test case '{case}' to appear in output.\n"
                f"Full output:\n{combined}"
            )
