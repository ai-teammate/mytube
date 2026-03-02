# MYTUBE-149: Access non-ready video — system returns 404 error

## Objective

Verifies that videos with `processing` or `failed` status are inaccessible via the public API.
`GET /api/videos/:id` must return HTTP 404 for any video that is not in the `ready` state.

## Test Type / Framework

- **Type:** API integration
- **Framework:** pytest + Go binary (subprocess) + psycopg2
- **Platform:** Go API server + PostgreSQL

## Prerequisites

- Python 3.10+
- `psycopg2-binary` Python package
- Go toolchain (1.21+) — only needed if the binary is not pre-built
- PostgreSQL 14+ (test database running and accessible)

Install Python dependencies:

```bash
pip install pytest psycopg2-binary requests
```

## Environment Variables

| Variable                        | Required | Default                        | Description                                      |
|---------------------------------|----------|--------------------------------|--------------------------------------------------|
| `API_BINARY`                    | No       | `<repo_root>/api/mytube-api`   | Path to pre-built Go API binary                  |
| `DB_HOST`                       | No       | `localhost`                    | PostgreSQL host                                  |
| `DB_PORT`                       | No       | `5432`                         | PostgreSQL port                                  |
| `DB_USER`                       | No       | `testuser`                     | PostgreSQL user                                  |
| `DB_PASSWORD`                   | No       | `testpass`                     | PostgreSQL password                              |
| `DB_NAME`                       | No       | `mytube_test`                  | PostgreSQL database name                         |
| `SSL_MODE`                      | No       | `disable`                      | PostgreSQL SSL mode                              |
| `FIREBASE_PROJECT_ID`           | No       | `test-project`                 | Firebase project ID (server init only)           |
| `GOOGLE_APPLICATION_CREDENTIALS`| No       | `testing/fixtures/mock_service_account.json` | Path to GCS service account JSON |
| `RAW_UPLOADS_BUCKET`            | No       | `test-raw-bucket`              | GCS bucket name (server init only)               |

## How to Run

```bash
pytest testing/tests/MYTUBE-149/test_mytube_149.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-149/test_mytube_149.py::TestProcessingVideoReturns404::test_status_code_is_404 PASSED
testing/tests/MYTUBE-149/test_mytube_149.py::TestProcessingVideoReturns404::test_response_is_json PASSED
testing/tests/MYTUBE-149/test_mytube_149.py::TestProcessingVideoReturns404::test_response_contains_error_field PASSED
testing/tests/MYTUBE-149/test_mytube_149.py::TestFailedVideoReturns404::test_status_code_is_404 PASSED
testing/tests/MYTUBE-149/test_mytube_149.py::TestFailedVideoReturns404::test_response_is_json PASSED
testing/tests/MYTUBE-149/test_mytube_149.py::TestFailedVideoReturns404::test_response_contains_error_field PASSED

6 passed in Xs
```

## Notes

- The test wipes all public tables before starting the Go server so migrations always run on a clean schema.
- Database rows are seeded via psycopg2 **after** the server is up (i.e., after migrations have run).
- No real Firebase or GCS credentials are required — the tested endpoint is unauthenticated and never touches GCS.
- Step 3 of the ticket (frontend `/v/[id]` 404 page) is not covered by this test; it is scoped to the API layer only.
