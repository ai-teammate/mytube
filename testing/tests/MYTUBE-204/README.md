# MYTUBE-204: Delete another user's comment — system returns 403 forbidden

Verifies that an authenticated user cannot delete a comment they do not own.
`DELETE /api/comments/{id}` must return `403 Forbidden` when the requester is
not the comment author.

## Dependencies

```bash
pip install pytest psycopg2-binary 'cloud-sql-python-connector[pg8000]'
```

## Required environment variables

| Variable | Description |
|---|---|
| `FIREBASE_TEST_TOKEN` | Valid Firebase ID token for the CI test user (User B) |
| `FIREBASE_TEST_UID` | `firebase_uid` of the CI test user / User B (default: `ci-test-user-001`) |
| `CLOUD_SQL_CONNECTION_NAME` | Cloud SQL instance connection name (default: `ai-native-478811:us-central1:learn-ai-db`) |
| `DB_USER` | Database user (default: `mytube`) |
| `DB_PASSWORD` | Database password |
| `DB_NAME` | Database name (default: `mytube`) |

Optional:

| Variable | Default |
|---|---|
| `API_BASE_URL` | `https://mytube-api-80693608388.us-central1.run.app` |

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-204/test_mytube_204.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-204/test_mytube_204.py::TestDeleteOtherUsersComment::test_response_status_is_403_forbidden PASSED
testing/tests/MYTUBE-204/test_mytube_204.py::TestDeleteOtherUsersComment::test_comment_still_exists_in_database PASSED
```

## Notes

- The test is skipped when `FIREBASE_TEST_TOKEN` is not set or the API is not reachable.
- User A (the comment owner) is a synthetic DB-only user — no real Firebase account is needed.
- User B is the CI test user identified by `FIREBASE_TEST_UID`.
- The test video and comment are deleted on teardown; User A's row is retained.
- Uses `cloud-sql-python-connector` with `pg8000` for direct Cloud SQL access.
