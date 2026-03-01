# MYTUBE-35 — Validate rating stars field: database rejects stars values outside 1-5 range

## What this test verifies

The `ratings` table has a `CHECK (stars BETWEEN 1 AND 5)` constraint on the `stars` column.
This test confirms that:

- Inserting `stars = 0` raises a `CheckViolation` error.
- Inserting `stars = 6` raises a `CheckViolation` error.
- Inserting `stars = 5` succeeds and the row is readable.

## Dependencies

- MYTUBE-29 (initial schema migration must be present in the migration file)

## Prerequisites

A running PostgreSQL instance reachable with the credentials below (defaults work with the project's local Docker Compose stack).

## Environment variables

| Variable      | Default        | Description               |
|---------------|----------------|---------------------------|
| `DB_HOST`     | `localhost`    | PostgreSQL host           |
| `DB_PORT`     | `5432`         | PostgreSQL port           |
| `DB_USER`     | `testuser`     | Database user             |
| `DB_PASSWORD` | `testpass`     | Database password         |
| `DB_NAME`     | `mytube_test`  | Database name             |
| `SSL_MODE`    | `disable`      | SSL mode                  |

## Install dependencies

```bash
pip install psycopg2-binary pytest
```

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-35/test_mytube_35.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-35/test_mytube_35.py::TestRatingsStarsConstraint::test_stars_zero_rejected PASSED
testing/tests/MYTUBE-35/test_mytube_35.py::TestRatingsStarsConstraint::test_stars_six_rejected  PASSED
testing/tests/MYTUBE-35/test_mytube_35.py::TestRatingsStarsConstraint::test_stars_five_accepted PASSED

3 passed
```
