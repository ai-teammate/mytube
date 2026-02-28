# MYTUBE-32 — Startup with Invalid Database Connection

Verifies that the application correctly fails to start (or reports an error)
when the database connection credentials or host are invalid.

## What is tested

1. Connecting with a **wrong password** raises `psycopg2.OperationalError`
2. Connecting to an **invalid host** raises `psycopg2.OperationalError`
3. Connecting to a **closed port** raises `psycopg2.OperationalError`
4. Simulated `/health` ping fails with wrong password (maps to HTTP 500)
5. Simulated `/health` ping fails with invalid host (maps to HTTP 500)

These mirror the Go application's behaviour:
- `database.Open()` failure → `log.Fatalf("db open: %v", err)` (process exits)
- `migration.RunMigrations()` failure → `log.Fatalf("migrate: %v", err)` (process exits)
- `db.Ping()` failure in health handler → HTTP 500 `{"status":"error","db":"unavailable"}`

## Prerequisites

- Python 3.10+
- `psycopg2-binary` and `pytest` packages

## Install dependencies

```bash
pip install psycopg2-binary pytest
```

## Environment variables

No valid database connection is required — this test intentionally uses
invalid credentials. The `DBConfig` defaults are used only to derive
valid *host/port/user* values for the "wrong password" scenarios.

| Variable     | Default        | Description              |
|--------------|----------------|--------------------------|
| `DB_HOST`    | `localhost`    | PostgreSQL host          |
| `DB_PORT`    | `5432`         | PostgreSQL port          |
| `DB_USER`    | `testuser`     | Database user            |
| `DB_PASSWORD`| `testpass`     | Database password        |
| `DB_NAME`    | `mytube_test`  | Target database          |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-32/test_mytube_32.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-32/test_mytube_32.py::TestInvalidPasswordFails::test_wrong_password_raises_operational_error PASSED
testing/tests/MYTUBE-32/test_mytube_32.py::TestInvalidHostFails::test_invalid_host_raises_operational_error PASSED
testing/tests/MYTUBE-32/test_mytube_32.py::TestInvalidPortFails::test_invalid_port_raises_operational_error PASSED
testing/tests/MYTUBE-32/test_mytube_32.py::TestHealthCheckWithBadConnection::test_ping_fails_with_wrong_password PASSED
testing/tests/MYTUBE-32/test_mytube_32.py::TestHealthCheckWithBadConnection::test_ping_fails_with_invalid_host PASSED
================================================== 5 passed in X.XXs ==================================================
```
