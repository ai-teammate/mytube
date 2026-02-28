# MYTUBE-36 — Migration Rollback Test

Verifies that `0001_initial_schema.down.sql` cleanly removes all schema objects
created by the UP migration: all 8 core tables, the `set_updated_at` trigger
function, and associated indexes/triggers.

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
pytest testing/tests/MYTUBE-36/test_mytube_36.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-36/test_mytube_36.py::TestAllTablesDropped::test_table_does_not_exist[users] PASSED
testing/tests/MYTUBE-36/test_mytube_36.py::TestAllTablesDropped::test_table_does_not_exist[videos] PASSED
testing/tests/MYTUBE-36/test_mytube_36.py::TestAllTablesDropped::test_table_does_not_exist[categories] PASSED
testing/tests/MYTUBE-36/test_mytube_36.py::TestAllTablesDropped::test_table_does_not_exist[video_tags] PASSED
testing/tests/MYTUBE-36/test_mytube_36.py::TestAllTablesDropped::test_table_does_not_exist[playlists] PASSED
testing/tests/MYTUBE-36/test_mytube_36.py::TestAllTablesDropped::test_table_does_not_exist[playlist_videos] PASSED
testing/tests/MYTUBE-36/test_mytube_36.py::TestAllTablesDropped::test_table_does_not_exist[comments] PASSED
testing/tests/MYTUBE-36/test_mytube_36.py::TestAllTablesDropped::test_table_does_not_exist[ratings] PASSED
testing/tests/MYTUBE-36/test_mytube_36.py::TestTriggerFunctionDropped::test_set_updated_at_function_dropped PASSED
testing/tests/MYTUBE-36/test_mytube_36.py::TestNoPublicTablesRemain::test_schema_is_empty PASSED
================================================== 10 passed in X.XXs ==================================================
```
