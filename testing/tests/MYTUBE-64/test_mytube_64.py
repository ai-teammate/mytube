"""
MYTUBE-64: Middleware context injection — firebase_uid is accessible to
downstream handlers.

Objective:
    Verify that the RequireAuth middleware correctly injects the verified
    firebase_uid (via *auth.TokenClaims) into the request context, and that
    downstream handlers can retrieve it using ClaimsFromContext.

Test strategy:
    Run the existing Go unit-test suite for the auth middleware package
    (api/internal/middleware/) using 'go test'.

    The Go tests in auth_test.go exercise the middleware with a stubbed
    TokenVerifier that returns controlled claims without calling Firebase:

      - TestRequireAuth_ValidToken_InjectsClaimsInContext
            Confirms that the UID and Email from the stub verifier are
            present in the context available to the downstream handler.

      - TestRequireAuth_ValidToken_CallsNext
            Confirms the downstream handler is invoked when the token is valid.

      - TestRequireAuth_MissingAuthHeader
            Confirms 401 is returned and downstream handler is not called.

      - TestRequireAuth_NonBearerScheme
            Confirms 401 is returned for non-Bearer auth schemes.

      - TestRequireAuth_EmptyToken
            Confirms 401 for a Bearer header with no token value.

      - TestRequireAuth_InvalidToken
            Confirms 401 when the verifier returns an error.

      - TestRequireAuth_BearerCaseInsensitive
            Confirms the Bearer scheme comparison is case-insensitive.

      - TestRequireAuth_401ResponseBody_IsJSON
            Confirms 401 responses carry a JSON body with an "error" key.

      - TestClaimsFromContext_Empty
            Confirms ClaimsFromContext returns nil when no claims were injected.

    The critical test for the ticket objective is
    TestRequireAuth_ValidToken_InjectsClaimsInContext, which uses a mock
    downstream handler to read the context and asserts that ClaimsFromContext
    returns claims whose UID matches the value returned by the stub verifier.

Architecture notes:
    - No running API server or database is required; these are pure Go unit tests.
    - The Python layer invokes `go test` via subprocess and asserts a zero exit code.
    - The middleware package is at: api/internal/middleware/
    - Go module root is at: api/
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_MIDDLEWARE_PKG = "github.com/ai-teammate/mytube/api/internal/middleware"
_MIDDLEWARE_IMPORT_PATH = "./internal/middleware/"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMiddlewareContextInjection:
    """
    Verifies firebase_uid context injection via the RequireAuth middleware.

    All assertions are backed by Go unit tests in the middleware package.
    Python orchestrates test execution and validates zero exit code.
    """

    def test_middleware_package_builds(self):
        """
        The middleware package and its dependencies must compile without errors.
        A failed build indicates a code-level defect before any test runs.
        """
        result = subprocess.run(
            ["go", "build", "./internal/middleware/"],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"go build failed for middleware package.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    def test_firebase_uid_injected_into_context(self):
        """
        Core ticket requirement: firebase_uid must be retrievable from the
        request context by downstream handlers.

        Runs TestRequireAuth_ValidToken_InjectsClaimsInContext which:
          1. Creates a stub verifier returning UID="firebase-uid-42"
          2. Wraps a capture handler with RequireAuth(stubVerifier)
          3. Issues a GET /api/me with a Bearer token
          4. In the capture handler, calls ClaimsFromContext(r.Context())
          5. Asserts claims != nil and claims.UID == "firebase-uid-42"
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestRequireAuth_ValidToken_InjectsClaimsInContext",
                _MIDDLEWARE_IMPORT_PATH,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestRequireAuth_ValidToken_InjectsClaimsInContext FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout, (
            f"Expected PASS in test output.\nSTDOUT:\n{result.stdout}"
        )

    def test_downstream_handler_called_with_valid_token(self):
        """
        With a valid token, RequireAuth must call the downstream handler.
        Verifies the happy-path middleware chain is not short-circuited.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestRequireAuth_ValidToken_CallsNext",
                _MIDDLEWARE_IMPORT_PATH,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestRequireAuth_ValidToken_CallsNext FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_missing_auth_header_returns_401(self):
        """
        A request without an Authorization header must be rejected with 401
        and the downstream handler must not be invoked.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestRequireAuth_MissingAuthHeader",
                _MIDDLEWARE_IMPORT_PATH,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestRequireAuth_MissingAuthHeader FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_invalid_token_returns_401(self):
        """
        A request with an invalid token (verifier returns error) must be
        rejected with 401; no context injection should occur.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestRequireAuth_InvalidToken",
                _MIDDLEWARE_IMPORT_PATH,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestRequireAuth_InvalidToken FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_claims_from_context_returns_nil_when_not_injected(self):
        """
        ClaimsFromContext must return nil when the middleware was not applied
        (i.e., no claims were stored in the context).
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestClaimsFromContext_Empty",
                _MIDDLEWARE_IMPORT_PATH,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestClaimsFromContext_Empty FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_full_middleware_test_suite_passes(self):
        """
        The complete middleware test suite must pass.

        This is the authoritative pass/fail gate: all 9 Go test functions in
        auth_test.go must succeed, confirming the full context-injection
        contract is met.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                _MIDDLEWARE_IMPORT_PATH,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"go test ./internal/middleware/ FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        # All 9 test functions must appear as PASS
        pass_count = result.stdout.count("--- PASS")
        assert pass_count == 9, (
            f"Expected 9 passing tests, got {pass_count}.\n"
            f"STDOUT:\n{result.stdout}"
        )
