# MYTUBE-651 — Delete avatar without authentication: API returns 401 Unauthorized

## Objective

Ensure that the `DELETE /api/me/avatar` endpoint is protected and requires valid
authentication. A request sent without an `Authorization` header must be rejected
with HTTP 401 Unauthorized.

## Test Type

`api` — pytest (REST, stdlib `urllib`)

## Test Structure

Three assertions run in a single shared module-scoped server session:

1. **test_returns_401_status_code** — `DELETE /api/me/avatar` with no `Authorization`
   header returns HTTP 401.
2. **test_response_body_is_json** — The 401 response body is valid JSON containing a
   dict.
3. **test_response_body_contains_error_field** — The JSON body contains a non-empty
   `error` field.

## Prerequisites

- Python 3.10+
- `pytest`
- Go toolchain (only needed if `api/mytube-api` binary is absent — the test builds it
  automatically)

## Environment Variables

| Variable                        | Required | Description                                                     |
|---------------------------------|----------|-----------------------------------------------------------------|
| `API_BINARY`                    | No       | Path to the compiled Go binary (default: `api/mytube-api`).     |
| `GOOGLE_APPLICATION_CREDENTIALS`| No       | Path to mock Firebase service-account JSON (default: `testing/fixtures/mock_service_account.json`). |
| `FIREBASE_PROJECT_ID`           | No       | Firebase project ID (default: `mock-project-id`).               |
| `RAW_UPLOADS_BUCKET`            | No       | GCS bucket name placeholder (default: `mytube-raw-uploads`).    |

## Running the Tests

```bash
# From the repository root:
pytest testing/tests/MYTUBE-651/test_mytube_651.py -v
```

## Expected Output

```
PASSED  TestDeleteAvatarRequiresAuth::test_returns_401_status_code
PASSED  TestDeleteAvatarRequiresAuth::test_response_body_is_json
PASSED  TestDeleteAvatarRequiresAuth::test_response_body_contains_error_field
```
