# MYTUBE-32 — Startup with Invalid Database Connection

Verifies that the Go API correctly fails to start — exiting with a non-zero
code and logging an error — when the database connection is invalid.

## What is tested

1. **Wrong password** → API process exits non-zero (log.Fatalf path)
2. **Wrong password** → log output contains a DB connection error message
3. **Invalid host** → API process exits non-zero
4. **Invalid host** → log output contains a DB connection error message
5. **Closed port** → API process exits non-zero and logs connection error
   (confirms health endpoint cannot be reached when DB is unreachable)

These directly verify the Go application's behaviour:
- `migration.RunMigrations()` failure → `log.Fatalf("migrate: %v", err)` (process exits)
- `database.Open()` + Ping failure → `log.Fatalf("db open: %v", err)` (process exits)
- Application never starts serving when DB is unavailable — health endpoint is unreachable

## Prerequisites

- Python 3.10+
- `pytest` package
- The compiled Go API binary (`api/mytube-api`)

## Install dependencies

```bash
pip install pytest
```

## Build the Go binary

```bash
cd api && go build -o mytube-api .
```

## Environment variables

A valid PostgreSQL instance is **not required** for most tests. The `DBConfig`
defaults are used only to derive *host/port/user* values for wrong-password
scenarios. Set `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` to
point at a real DB if needed.

| Variable     | Default        | Description                     |
|--------------|----------------|---------------------------------|
| `DB_HOST`    | `localhost`    | PostgreSQL host                 |
| `DB_PORT`    | `5432`         | PostgreSQL port                 |
| `DB_USER`    | `testuser`     | Database user                   |
| `DB_PASSWORD`| `testpass`     | Database password               |
| `DB_NAME`    | `mytube_test`  | Target database                 |
| `API_BINARY` | `api/mytube-api` | Path to the compiled Go binary |

## Run the test

From the repository root:

```bash
API_BINARY=./api/mytube-api pytest testing/tests/MYTUBE-32/test_mytube_32.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-32/test_mytube_32.py::TestApiExitsOnBadCredentials::test_wrong_password_causes_nonzero_exit PASSED
testing/tests/MYTUBE-32/test_mytube_32.py::TestApiExitsOnBadCredentials::test_wrong_password_logs_connection_error PASSED
testing/tests/MYTUBE-32/test_mytube_32.py::TestApiExitsOnBadCredentials::test_invalid_host_causes_nonzero_exit PASSED
testing/tests/MYTUBE-32/test_mytube_32.py::TestApiExitsOnBadCredentials::test_invalid_host_logs_connection_error PASSED
testing/tests/MYTUBE-32/test_mytube_32.py::TestHealthEndpointWithBadConnection::test_health_returns_500_when_db_unreachable_at_handler_time PASSED
================================================== 5 passed in 0.XXs ==================================================
```
