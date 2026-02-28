# MYTUBE-29 — Initial Schema Migration Test

Verifies that `0001_initial_schema.up.sql` creates all 8 core tables with correct
column types, primary keys, foreign keys, and default values.

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ running locally (or via `DB_HOST`)
- `psycopg2-binary` and `pytest` packages

## Install dependencies

```bash
pip install psycopg2-binary pytest
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `testuser` | Database user |
| `DB_PASSWORD` | `testpass` | Database password |
| `DB_NAME` | `mytube_test` | Target database (must exist and be empty) |
| `SSL_MODE` | `disable` | SSL mode |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-29/test_mytube_29.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-29/test_mytube_29.py::TestAllTablesExist::test_table_exists[users] PASSED
testing/tests/MYTUBE-29/test_mytube_29.py::TestAllTablesExist::test_table_exists[videos] PASSED
...
================================================== 28 passed in X.XXs ==================================================
```
