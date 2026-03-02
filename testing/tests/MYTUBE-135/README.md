# MYTUBE-135: Access POST /api/videos without authentication — 401 Unauthorized returned

## Purpose

Verifies that `POST /api/videos` is protected and returns `401 Unauthorized`
when the request carries no `Authorization` header.

## Prerequisites

- Python 3.11+
- Go toolchain (for building the API binary)
- PostgreSQL test database accessible via environment variables

## Install dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment variables

| Variable              | Default          | Required | Description                                      |
|-----------------------|------------------|----------|--------------------------------------------------|
| `API_BINARY`          | `api/mytube-api` | No       | Path to pre-built Go binary                      |
| `FIREBASE_PROJECT_ID` | `dummy-project`  | No       | Firebase project ID placeholder                  |
| `DB_HOST`             | `localhost`      | No       | PostgreSQL host                                  |
| `DB_PORT`             | `5432`           | No       | PostgreSQL port                                  |
| `DB_USER`             | `testuser`       | No       | PostgreSQL user                                  |
| `DB_PASSWORD`         | `testpass`       | No       | PostgreSQL password                              |
| `DB_NAME`             | `mytube_test`    | No       | PostgreSQL database name                         |

## Run

```bash
pytest testing/tests/MYTUBE-135/test_mytube_135.py -v
```

## Expected output (when passing)

```
PASSED testing/tests/MYTUBE-135/test_mytube_135.py::TestPostVideosUnauthenticated::test_status_code_is_401
PASSED testing/tests/MYTUBE-135/test_mytube_135.py::TestPostVideosUnauthenticated::test_response_body_is_valid_json
PASSED testing/tests/MYTUBE-135/test_mytube_135.py::TestPostVideosUnauthenticated::test_response_contains_error_key
PASSED testing/tests/MYTUBE-135/test_mytube_135.py::TestPostVideosUnauthenticated::test_error_message_is_unauthorized
```

## Test structure

| Test | What it verifies |
|------|-----------------|
| `test_status_code_is_401` | The endpoint returns HTTP 401 Unauthorized |
| `test_response_body_is_valid_json` | The response body is parseable JSON |
| `test_response_contains_error_key` | The JSON body contains an `error` key |
| `test_error_message_is_unauthorized` | The `error` value is `"unauthorized"` |
