# MYTUBE-227: Create new playlist via API — playlist created with title and owner metadata

Verifies that an authenticated user can successfully create a new playlist via the API.
`POST /api/playlists` with body `{ "title": "My Workout Mix" }` must return 201 Created
and a JSON body containing a unique `id`, the `title`, and the `owner_username` matching
the authenticated user.

## Dependencies

```bash
pip install pytest 'cloud-sql-python-connector[pg8000]'
```

## Required environment variables

| Variable | Description |
|---|---|
| `FIREBASE_TEST_TOKEN` | Valid Firebase ID token for the CI test user |
| `FIREBASE_TEST_UID` | `firebase_uid` of the CI test user (default: `ci-test-user-001`) |
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
pytest testing/tests/MYTUBE-227/test_mytube_227.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-227/test_mytube_227.py::TestCreatePlaylist::test_status_code_is_201 PASSED
testing/tests/MYTUBE-227/test_mytube_227.py::TestCreatePlaylist::test_response_body_is_valid_json PASSED
testing/tests/MYTUBE-227/test_mytube_227.py::TestCreatePlaylist::test_response_contains_id PASSED
testing/tests/MYTUBE-227/test_mytube_227.py::TestCreatePlaylist::test_response_id_is_uuid PASSED
testing/tests/MYTUBE-227/test_mytube_227.py::TestCreatePlaylist::test_response_contains_title PASSED
testing/tests/MYTUBE-227/test_mytube_227.py::TestCreatePlaylist::test_response_title_matches_request PASSED
testing/tests/MYTUBE-227/test_mytube_227.py::TestCreatePlaylist::test_response_contains_owner_username PASSED
testing/tests/MYTUBE-227/test_mytube_227.py::TestCreatePlaylist::test_response_owner_username_matches_authenticated_user PASSED
```

## Notes

- The test is skipped when `FIREBASE_TEST_TOKEN` is not set or the API is not reachable.
- Uses `cloud-sql-python-connector` with `pg8000` for direct Cloud SQL access.
- The created playlist is deleted on teardown so repeated runs start clean.
- The CI test user row is upserted idempotently before the POST is issued.
