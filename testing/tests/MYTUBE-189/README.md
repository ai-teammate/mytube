# MYTUBE-189 — Update video metadata as non-owner: 403 Forbidden returned

## What this test verifies

Sends a PUT request to `/api/videos/{id}` as User A (authenticated), where the video
is owned by User C (a different user). Asserts that:

1. The API returns **403 Forbidden** (ownership rejection).
2. The video's title and description in the database remain unchanged.

## Test type

API integration test — runs the Go binary in a subprocess against a real PostgreSQL
database, issues authenticated HTTP requests using a Firebase Bearer token.

## Dependencies

- Python 3.11+
- `psycopg2-binary`
- `pytest`
- Go toolchain (only if binary is not pre-built)

## Environment variables

| Variable              | Default                  | Description                                          |
|-----------------------|--------------------------|------------------------------------------------------|
| `FIREBASE_TEST_TOKEN` | *(required)*             | Firebase ID token for User A (the non-owner caller)  |
| `FIREBASE_PROJECT_ID` | *(required)*             | Firebase project ID for server token verification    |
| `FIREBASE_TEST_UID`   | `test-uid-user-a-189`    | firebase_uid that matches `FIREBASE_TEST_TOKEN`      |
| `API_BINARY`          | `api/mytube-api`         | Path to the pre-built Go binary                      |
| `DB_HOST`             | `localhost`              | PostgreSQL host                                      |
| `DB_PORT`             | `5432`                   | PostgreSQL port                                      |
| `DB_USER`             | `testuser`               | PostgreSQL username                                  |
| `DB_PASSWORD`         | `testpass`               | PostgreSQL password                                  |
| `DB_NAME`             | `mytube_test`            | PostgreSQL database name                             |

## How to run

```bash
pytest testing/tests/MYTUBE-189/test_mytube_189.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-189/test_mytube_189.py::TestUpdateVideoNonOwner::test_response_status_is_403 PASSED
testing/tests/MYTUBE-189/test_mytube_189.py::TestUpdateVideoNonOwner::test_video_title_unchanged_in_db PASSED
testing/tests/MYTUBE-189/test_mytube_189.py::TestUpdateVideoNonOwner::test_video_description_unchanged_in_db PASSED
```
