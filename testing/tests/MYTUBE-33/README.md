# MYTUBE-33 — Migration Idempotency Test

Verifies that running migrations multiple times is safe: subsequent runs skip
already-applied migrations without error and leave the schema unchanged.

The test validates the `ErrNoChange` handling in
`api/internal/migration/migration.go` — the production code uses
`golang-migrate`, which tracks applied versions in a `schema_migrations` table
and silently skips them on subsequent startup.

## What is tested

1. Migrations applied once → all 8 tables and `schema_migrations` version record exist.
2. The `schema_migrations` table shows the database is already at the latest version.
3. Re-applying migration SQL directly raises an error (tables already exist), confirming
   that the golang-migrate tracker is the idempotency guard.
4. Schema state after the "second run" is identical to the state after the first run —
   no tables dropped, no data lost.

## Scope limitation

The ticket steps describe starting and restarting the Go API binary and verifying
application log output. This test covers the same idempotency guarantee at the
**SQL / database level** via psycopg2, which avoids the need for a compiled binary in
CI. The `migration.go` → `m.Up()` → `ErrNoChange` code path is not exercised
directly. API-level log assertion (verifying "already at latest version" in Go logs)
is out of scope for this test and should be addressed in a follow-up integration test.

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
| `DB_NAME` | `mytube_test` | Target database (must exist) |
| `SSL_MODE` | `disable` | SSL mode |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-33/test_mytube_33.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-33/test_mytube_33.py::TestFirstRunState::test_schema_migrations_table_exists PASSED
testing/tests/MYTUBE-33/test_mytube_33.py::TestFirstRunState::test_schema_migrations_version_is_latest PASSED
testing/tests/MYTUBE-33/test_mytube_33.py::TestFirstRunState::test_schema_migrations_not_dirty PASSED
testing/tests/MYTUBE-33/test_mytube_33.py::TestFirstRunState::test_all_tables_present PASSED
testing/tests/MYTUBE-33/test_mytube_33.py::TestSecondRunIdempotency::test_reapply_schema_sql_fails_without_tracker PASSED
testing/tests/MYTUBE-33/test_mytube_33.py::TestSecondRunIdempotency::test_schema_migrations_version_unchanged_after_second_run PASSED
testing/tests/MYTUBE-33/test_mytube_33.py::TestSecondRunIdempotency::test_table_count_unchanged_after_second_run PASSED
testing/tests/MYTUBE-33/test_mytube_33.py::TestSecondRunIdempotency::test_categories_data_unchanged_after_second_run PASSED
================================================== 8 passed in X.XXs ==================================================
```
