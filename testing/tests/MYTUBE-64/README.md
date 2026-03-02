# MYTUBE-64: Middleware context injection — firebase_uid is accessible to downstream handlers

## Objective

Verify that the `RequireAuth` middleware correctly injects the verified `firebase_uid` (as part of `*auth.TokenClaims`) into the HTTP request context, and that downstream handlers can retrieve it via `ClaimsFromContext`.

## Test type

Unit test — no database, running server, or Firebase credentials required. The Python test orchestrates `go test` subprocess calls against the `api/internal/middleware/` package.

## Prerequisites

- **Go 1.24+** installed and on `PATH`
- **Python 3.10+**
- No environment variables required (pure unit tests, no I/O)

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-64/test_mytube_64.py -v
```

Or to run a specific test:

```bash
pytest testing/tests/MYTUBE-64/test_mytube_64.py::TestMiddlewareContextInjection::test_firebase_uid_injected_into_context -v
```

You can also run the Go tests directly:

```bash
cd api
go test -v -count=1 ./internal/middleware/
```

## Expected output (passing)

```
testing/tests/MYTUBE-64/test_mytube_64.py::TestMiddlewareContextInjection::test_middleware_package_builds PASSED
testing/tests/MYTUBE-64/test_mytube_64.py::TestMiddlewareContextInjection::test_firebase_uid_injected_into_context PASSED
testing/tests/MYTUBE-64/test_mytube_64.py::TestMiddlewareContextInjection::test_downstream_handler_called_with_valid_token PASSED
testing/tests/MYTUBE-64/test_mytube_64.py::TestMiddlewareContextInjection::test_missing_auth_header_returns_401 PASSED
testing/tests/MYTUBE-64/test_mytube_64.py::TestMiddlewareContextInjection::test_invalid_token_returns_401 PASSED
testing/tests/MYTUBE-64/test_mytube_64.py::TestMiddlewareContextInjection::test_claims_from_context_returns_nil_when_not_injected PASSED
testing/tests/MYTUBE-64/test_mytube_64.py::TestMiddlewareContextInjection::test_full_middleware_test_suite_passes PASSED

7 passed
```

## Test coverage

| Go test function | What it verifies |
|---|---|
| `TestRequireAuth_ValidToken_InjectsClaimsInContext` | **Core**: `firebase_uid` from stub verifier is retrievable from context via `ClaimsFromContext` |
| `TestRequireAuth_ValidToken_CallsNext` | Downstream handler is invoked on valid token |
| `TestRequireAuth_MissingAuthHeader` | 401 returned, downstream handler not called |
| `TestRequireAuth_NonBearerScheme` | 401 for non-Bearer auth schemes |
| `TestRequireAuth_EmptyToken` | 401 for `Bearer ` with no token |
| `TestRequireAuth_InvalidToken` | 401 when verifier returns error |
| `TestRequireAuth_BearerCaseInsensitive` | `BEARER` / `Bearer` / `bearer` all accepted |
| `TestRequireAuth_401ResponseBody_IsJSON` | 401 responses carry `{"error": "..."}` JSON body |
| `TestClaimsFromContext_Empty` | `ClaimsFromContext` returns nil on a plain context |

## Source files

- Middleware: `api/internal/middleware/auth.go`
- Go unit tests: `api/internal/middleware/auth_test.go`
- Auth interface: `api/internal/auth/verifier.go`
