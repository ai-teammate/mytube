# MYTUBE-147: Increment video view count — count is updated atomically on page load

## Purpose

Verifies that accessing `GET /api/videos/:id` increments the `view_count` in
the database by 1 on each request, and that the API response reflects the
post-increment value. The update must be atomic (no race conditions).

## Prerequisites

- Python 3.11+
- Go toolchain (for building the API binary)
- PostgreSQL test database accessible via environment variables

## Install dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment variables

| Variable              | Default           | Required | Description                                           |
|-----------------------|-------------------|----------|-------------------------------------------------------|
| `FIREBASE_PROJECT_ID` | `dummy-project`   | No       | Firebase project ID (placeholder accepted; endpoint is public) |
| `API_BINARY`          | `api/mytube-api`  | No       | Path to pre-built Go binary                           |
| `DB_HOST`             | `localhost`       | No       | PostgreSQL host                                       |
| `DB_PORT`             | `5432`            | No       | PostgreSQL port                                       |
| `DB_USER`             | `testuser`        | No       | PostgreSQL user                                       |
| `DB_PASSWORD`         | `testpass`        | No       | PostgreSQL password                                   |
| `DB_NAME`             | `mytube_test`     | No       | PostgreSQL database name                              |

## Run

```bash
pytest testing/tests/MYTUBE-147/test_mytube_147.py -v
```

## Expected output (when passing)

```
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_initial_db_view_count_is_10
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_first_request_returns_200
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_first_request_response_is_valid_json
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_first_request_response_view_count_is_11
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_first_request_db_view_count_is_11
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_second_request_returns_200
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_second_request_response_is_valid_json
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_second_request_response_view_count_is_12
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_second_request_db_view_count_is_12
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_view_count_field_is_present_in_response
PASSED testing/tests/MYTUBE-147/test_mytube_147.py::TestViewCountIncrement::test_view_count_field_is_integer
```

## Test structure

| Test | What it verifies |
|------|-----------------|
| `test_initial_db_view_count_is_10` | Sanity check: seeded video starts at view_count = 10 |
| `test_first_request_returns_200` | First GET returns HTTP 200 OK |
| `test_first_request_response_is_valid_json` | First response body is parseable JSON |
| `test_first_request_response_view_count_is_11` | First response contains view_count = 11 (post-increment) |
| `test_first_request_db_view_count_is_11` | DB view_count = 11 after first request |
| `test_second_request_returns_200` | Second GET returns HTTP 200 OK |
| `test_second_request_response_is_valid_json` | Second response body is parseable JSON |
| `test_second_request_response_view_count_is_12` | Second response contains view_count = 12 (post-increment) |
| `test_second_request_db_view_count_is_12` | DB view_count = 12 after second request |
| `test_view_count_field_is_present_in_response` | Response includes a `view_count` field |
| `test_view_count_field_is_integer` | `view_count` field is an integer type |
