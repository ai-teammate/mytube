# MYTUBE-63 — Access protected endpoint without Authorization header

Verifies that `GET /api/me` returns **HTTP 401 Unauthorized** when the
`Authorization` header is absent.

## What is tested

The Firebase Auth middleware (`api/internal/middleware/auth.go`) must reject
any request that does not carry an `Authorization: Bearer <token>` header with
a 401 JSON response before the handler is ever invoked.

## Prerequisites

- Python 3.10+
- `pytest` (`pip install pytest`)
- A running PostgreSQL instance reachable with the DB env vars below
- Go 1.21+ (only required if the API binary is not already built)
- A structurally valid Firebase service-account JSON file (mock is fine — the
  test never actually calls Firebase; the SDK only needs to initialise)

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | `testpass` | PostgreSQL password |
| `DB_NAME` | `mytube_test` | PostgreSQL database name |
| `SSL_MODE` | `disable` | PostgreSQL SSL mode |
| `API_BASE_URL` | `http://localhost:8080` | API base URL (host/port only used for APIConfig; actual port is hardcoded to 18095 in the test) |
| `API_BINARY` | `api/mytube-api` | Path to the pre-built Go API binary |
| `FIREBASE_PROJECT_ID` | `mock-project-id` | Firebase project ID (any non-empty value works) |
| `GOOGLE_APPLICATION_CREDENTIALS` | `testing/fixtures/mock_service_account.json` | Path to service-account JSON for Firebase Admin SDK init |

## Install dependencies

```bash
pip install pytest
```

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-63/test_mytube_63.py -v
```

To use a custom binary path:

```bash
API_BINARY=/path/to/mytube-api pytest testing/tests/MYTUBE-63/test_mytube_63.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-63/test_mytube_63.py::TestProtectedEndpointRequiresAuth::test_returns_401_status_code PASSED
testing/tests/MYTUBE-63/test_mytube_63.py::TestProtectedEndpointRequiresAuth::test_response_body_is_json PASSED
testing/tests/MYTUBE-63/test_mytube_63.py::TestProtectedEndpointRequiresAuth::test_response_body_contains_error_field PASSED

3 passed in X.XXs
```
