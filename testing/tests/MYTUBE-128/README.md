# MYTUBE-128: Run DB Integration Tests with Active PostgreSQL Service

## Objective

Verify that the DB integration tests in `TestMarkFailedSQLContract` (from MYTUBE-80) execute successfully when PostgreSQL is reachable — no "Connection refused" errors and all 3 tests pass.

## Prerequisites

- Python 3.10+
- PostgreSQL running and accessible at `localhost:5432` (or as configured via env vars)
- Database `mytube_test` exists with user `testuser` / password `testpass`
- `pytest` and `psycopg2-binary` installed

## Install Dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `testuser` | Database user |
| `DB_PASSWORD` | `testpass` | Database password |
| `DB_NAME` | `mytube_test` | Database name |
| `SSL_MODE` | `disable` | SSL mode |

## Run the Test

From the repository root:

```bash
python3 -m pytest testing/tests/MYTUBE-128/test_mytube_128.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-128/test_mytube_128.py::TestDBIntegrationWithPostgres::test_postgres_is_reachable PASSED
testing/tests/MYTUBE-128/test_mytube_128.py::TestDBIntegrationWithPostgres::test_mark_failed_sql_contract_all_pass PASSED

2 passed in X.XXs
```

## What Is Tested

1. **`test_postgres_is_reachable`** — Confirms a live PostgreSQL connection can be established without "Connection refused" errors.
2. **`test_mark_failed_sql_contract_all_pass`** — Runs all 3 `TestMarkFailedSQLContract` tests from MYTUBE-80 via pytest subprocess and verifies:
   - Exit code is 0 (all passed)
   - No tests were skipped (PostgreSQL was detected as available)
   - All 3 tests appear as PASSED in output:
     - `test_mark_failed_sets_status_to_failed`
     - `test_failed_status_accepted_by_check_constraint`
     - `test_mark_failed_does_not_affect_other_rows`
