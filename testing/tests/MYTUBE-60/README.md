# MYTUBE-60: Authenticate with invalid Firebase token — API returns 401 Unauthorized

## Overview

Verifies that requests with invalid, expired, or malformed Firebase tokens are rejected
by the `RequireAuth` middleware with HTTP 401 Unauthorized and a JSON error body.

## Test Structure

| Part | Description | Requires infrastructure? |
|------|-------------|--------------------------|
| A — Go unit tests | Runs `go test ./internal/middleware/...` with stub verifiers | No |
| B — Static analysis | Reads `api/internal/middleware/auth.go` to confirm 401 path | No |
| C — Live integration | Starts API server and sends invalid tokens to `/api/me` | Yes (Firebase + PostgreSQL) |

Parts A and B always run. Part C is skipped gracefully when `FIREBASE_PROJECT_ID`
or PostgreSQL is not available.

## Dependencies

```bash
pip install pytest
```

Go toolchain must be available on `PATH` for Part A.

## Environment Variables

| Variable | Required for Part | Default | Description |
|----------|-------------------|---------|-------------|
| `FIREBASE_PROJECT_ID` | C only | — | Firebase project ID |
| `API_SERVER_BINARY` | C only | `api/server` | Path to pre-built API binary |
| `DB_HOST` | C only | `localhost` | PostgreSQL host |
| `DB_PORT` | C only | `5432` | PostgreSQL port |
| `DB_USER` | C only | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | C only | `testpass` | PostgreSQL password |
| `DB_NAME` | C only | `mytube_test` | PostgreSQL database name |

For Part C, Application Default Credentials (ADC) must be configured so the API
server can initialise the Firebase Admin SDK:

```bash
gcloud auth application-default login
```

## Running the Test

### Parts A + B only (no infrastructure required)

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-60/test_mytube_60.py \
    -v \
    -k "not TestInvalidTokenReturns401"
```

### All parts (full integration)

```bash
export FIREBASE_PROJECT_ID=your-firebase-project-id
# Ensure PostgreSQL is running and ADC is configured.
pytest testing/tests/MYTUBE-60/test_mytube_60.py -v
```

### From the testing/ root

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-60/ -v
```

## Expected Output When Tests Pass

```
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareGoUnitTests::test_go_unit_tests_pass PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareGoUnitTests::test_go_tests_cover_invalid_token_scenario PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareGoUnitTests::test_go_tests_cover_missing_header_scenario PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareGoUnitTests::test_go_tests_cover_json_error_body_scenario PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareStaticAnalysis::test_middleware_file_exists PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareStaticAnalysis::test_middleware_implements_require_auth PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareStaticAnalysis::test_middleware_rejects_missing_bearer_header PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareStaticAnalysis::test_middleware_calls_write_unauthorized_on_invalid_token PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareStaticAnalysis::test_write_unauthorized_sets_401_status PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareStaticAnalysis::test_write_unauthorized_returns_json_with_error_key PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareStaticAnalysis::test_middleware_calls_verify_id_token PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestAuthMiddlewareStaticAnalysis::test_content_type_is_json PASSED
testing/tests/MYTUBE-60/test_mytube_60.py::TestInvalidTokenReturns401::test_invalid_token_returns_401[...] SKIPPED (FIREBASE_PROJECT_ID is not set)
```
