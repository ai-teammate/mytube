# MYTUBE-237 — View user profile with private playlists

Verifies that the public user profile endpoint (`GET /api/users/:username/playlists`)
filters out private playlists: only playlists with `is_private = FALSE` are returned to
unauthenticated callers.

## Dependencies

```bash
pip install pytest cloud-sql-python-connector[pg8000]
```

## Required environment variables

| Variable | Source | Description |
|---|---|---|
| `FIREBASE_TEST_UID` | CI variable | Firebase UID of the CI test user (default: `ci-test-user-001`) |
| `CLOUD_SQL_CONNECTION_NAME` | CI variable | Cloud SQL instance (default: `ai-native-478811:us-central1:learn-ai-db`) |
| `DB_USER` | CI secret | Database user (default: `mytube`) |
| `DB_PASSWORD` | CI secret | Database password |
| `DB_NAME` | CI variable | Database name (default: `mytube`) |
| `API_BASE_URL` | CI variable | API base URL (default: `https://mytube-api-80693608388.us-central1.run.app`) |

`GOOGLE_APPLICATION_CREDENTIALS` must also be set (configured by `google-github-actions/auth@v2`).

## Run

```bash
cd /path/to/mytube
pytest testing/tests/MYTUBE-237/test_mytube_237.py -v
```

## Expected output (passing)

```
PASSED  test_public_endpoint_returns_200
PASSED  test_public_playlist_present_in_response
PASSED  test_private_playlist_absent_from_response
```

The test is **skipped** (not failed) when:
- The deployed API is not reachable.
- `cloud-sql-python-connector` is not installed.
- The `is_private` column does not exist on the `playlists` table (feature not yet deployed).
