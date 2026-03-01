# MYTUBE-61: Authenticate with existing user — no duplicate record creation

## Objective

Verify that the auto-provisioning logic correctly handles users who already exist
in the database by ignoring the insert conflict (`ON CONFLICT (firebase_uid) DO NOTHING`).

## Test type

DB integration test (PostgreSQL). No live Firebase project or valid JWT tokens required.

## Preconditions

- PostgreSQL reachable at `DB_HOST:DB_PORT` (defaults: `localhost:5432`)
- Database `mytube_test` accessible with `testuser`/`testpass` (or env overrides)
- Migration `api/migrations/0001_initial_schema.up.sql` applied automatically by the fixture

## Environment variables

| Variable      | Default     | Description               |
|---------------|-------------|---------------------------|
| `DB_HOST`     | `localhost` | PostgreSQL host            |
| `DB_PORT`     | `5432`      | PostgreSQL port            |
| `DB_USER`     | `testuser`  | PostgreSQL user            |
| `DB_PASSWORD` | `testpass`  | PostgreSQL password        |
| `DB_NAME`     | `mytube_test` | Database name            |
| `SSL_MODE`    | `disable`   | SSL mode                   |

## Run

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-61/ -v
```

## Expected output

```
PASSED test_precondition_user_exists_before_upsert
PASSED test_upsert_does_not_insert_when_conflict
PASSED test_only_one_record_remains_after_repeated_upserts
PASSED test_original_user_id_is_unchanged
PASSED test_username_is_unchanged_after_upserts
PASSED test_upsert_executed_correct_number_of_times
```

## Approach

The test directly exercises the upsert SQL from `api/internal/repository/user.go`:

```sql
INSERT INTO users (firebase_uid, username)
VALUES ($1, $2)
ON CONFLICT (firebase_uid) DO NOTHING
```

1. A user row is pre-seeded (simulating an existing user).
2. The upsert is executed 5 times for the same `firebase_uid`.
3. The test asserts:
   - Every upsert returns `rowcount == 0` (conflict suppressed insert)
   - Exactly 1 row remains in the table
   - The row's `id` and `username` are unchanged
