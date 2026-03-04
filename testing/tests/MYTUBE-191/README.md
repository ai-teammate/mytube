# MYTUBE-191 — Delete video as non-owner: 403 Forbidden

Verifies that an authenticated user receives `403 Forbidden` when attempting to delete a video they do not own, and that the video's status remains unchanged in the database.

## Type

API integration test (Go binary + PostgreSQL + Firebase Auth)

## Dependencies

| Variable | Description |
|---|---|
| `FIREBASE_TEST_TOKEN` | Valid Firebase ID token for User A (the non-owner). Generate at runtime. |
| `FIREBASE_PROJECT_ID` | Firebase project ID (`ai-native-478811`). Required by the API server. |
| `FIREBASE_TEST_UID` | `firebase_uid` matching the token. Defaults to `ci-test-user-001`. |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | PostgreSQL connection settings. |
| `API_BINARY` | Path to the compiled Go binary (default: `<repo_root>/api/mytube-api`). |

## Install dependencies

```bash
pip install pytest psycopg2-binary
```

## Run the test

```bash
cd <repo_root>
pytest testing/tests/MYTUBE-191/test_mytube_191.py -v
```

## Environment setup example

```bash
export FIREBASE_TEST_TOKEN="<id-token>"
export FIREBASE_PROJECT_ID="ai-native-478811"
export FIREBASE_TEST_UID="ci-test-user-001"
export DB_HOST=localhost
export DB_PORT=5432
export DB_USER=testuser
export DB_PASSWORD=testpass
export DB_NAME=mytube_test

pytest testing/tests/MYTUBE-191/test_mytube_191.py -v
```

## Expected output (passing)

```
PASSED testing/tests/MYTUBE-191/test_mytube_191.py::TestDeleteVideoNonOwner::test_returns_403_forbidden
PASSED testing/tests/MYTUBE-191/test_mytube_191.py::TestDeleteVideoNonOwner::test_video_status_unchanged_in_db
```

## Skip condition

The test is skipped automatically when `FIREBASE_TEST_TOKEN` or `FIREBASE_PROJECT_ID` is not set.
