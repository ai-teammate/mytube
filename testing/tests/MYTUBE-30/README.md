# MYTUBE-30: Access health endpoint — GET /health returns success after migration

## Objective

Verify that `GET /health` returns HTTP 200 OK with `{"status":"ok","db":"connected"}` once
the database schema migration has completed and the API server is running.

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ running and accessible
- Go 1.24+ (to build the API server, if not pre-built)
- `pytest` installed (`pip install pytest`)

## Environment Variables

| Variable       | Default         | Description                         |
|----------------|-----------------|-------------------------------------|
| `DB_HOST`      | `localhost`     | PostgreSQL host                     |
| `DB_PORT`      | `5432`          | PostgreSQL port                     |
| `DB_USER`      | `testuser`      | PostgreSQL user                     |
| `DB_PASSWORD`  | `testpass`      | PostgreSQL password                 |
| `DB_NAME`      | `mytube_test`   | PostgreSQL database name            |
| `SSL_MODE`     | `disable`       | PostgreSQL SSL mode                 |
| `API_HOST`     | `localhost`     | API server host                     |
| `API_PORT`     | `8080`          | API server port                     |
| `HEALTH_TOKEN` | *(empty)*       | Optional X-Health-Token header value|

## How to Run

```bash
pytest testing/tests/MYTUBE-30/test_mytube_30.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-30/test_mytube_30.py::TestHealthEndpoint::test_returns_200_ok PASSED
testing/tests/MYTUBE-30/test_mytube_30.py::TestHealthEndpoint::test_response_body_status_ok PASSED
testing/tests/MYTUBE-30/test_mytube_30.py::TestHealthEndpoint::test_response_body_db_connected PASSED
testing/tests/MYTUBE-30/test_mytube_30.py::TestHealthEndpoint::test_content_type_is_json PASSED

4 passed
```
