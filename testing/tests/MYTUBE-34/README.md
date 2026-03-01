# MYTUBE-34 — Validate video status field: database rejects status values not in defined list

## What this test verifies

The `videos.status` column has a CHECK constraint:

```sql
CHECK (status IN ('pending','processing','ready','failed'))
```

This test confirms that:
1. An INSERT with `status = 'archived'` is rejected with a `CheckViolation` error.
2. An INSERT with `status = 'pending'` succeeds.

## Requirements

- Python 3.10+
- PostgreSQL 14+ (accessible via environment variables below)
- `psycopg2-binary` and `pytest`

## Environment variables

| Variable      | Default       | Description                  |
|---------------|---------------|------------------------------|
| `DB_HOST`     | `localhost`   | PostgreSQL host              |
| `DB_PORT`     | `5432`        | PostgreSQL port              |
| `DB_USER`     | `testuser`    | PostgreSQL user              |
| `DB_PASSWORD` | `testpass`    | PostgreSQL password          |
| `DB_NAME`     | `mytube_test` | Target database name         |
| `SSL_MODE`    | `disable`     | SSL mode                     |

## Install dependencies

```bash
pip install psycopg2-binary pytest
```

## Run the test

```bash
pytest testing/tests/MYTUBE-34/test_mytube_34.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-34/test_mytube_34.py::TestVideoStatusCheckConstraint::test_invalid_status_archived_is_rejected PASSED
testing/tests/MYTUBE-34/test_mytube_34.py::TestVideoStatusCheckConstraint::test_valid_status_pending_is_accepted PASSED
2 passed
```
