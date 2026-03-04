# MYTUBE-231 — Delete playlist as owner

Verifies that `DELETE /api/playlists/:id` removes the playlist record and all
associated `playlist_videos` rows.

## Dependencies

```bash
pip install pytest psycopg2-binary
```

The Go API binary must be compiled or already present at `api/mytube-api`:

```bash
cd api && go build -o mytube-api .
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FIREBASE_TEST_TOKEN` | **yes** | — | Firebase ID token for the test user |
| `FIREBASE_PROJECT_ID` | **yes** | — | Firebase project ID (e.g. `ai-native-478811`) |
| `FIREBASE_TEST_UID` | no | `test-uid-mytube-231` | `firebase_uid` embedded in the token |
| `API_BINARY` | no | `api/mytube-api` | Path to the pre-built Go binary |
| `DB_HOST` | no | `localhost` | PostgreSQL host |
| `DB_PORT` | no | `5432` | PostgreSQL port |
| `DB_USER` | no | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | no | `testpass` | PostgreSQL password |
| `DB_NAME` | no | `mytube_test` | PostgreSQL database name |
| `SSL_MODE` | no | `disable` | PostgreSQL SSL mode |

## Run the test

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-231/test_mytube_231.py -v
```

## Expected output (when all credentials are present)

```
testing/tests/MYTUBE-231/test_mytube_231.py::TestDeletePlaylistAsOwner::test_delete_returns_204 PASSED
testing/tests/MYTUBE-231/test_mytube_231.py::TestDeletePlaylistAsOwner::test_get_returns_404_after_delete PASSED
testing/tests/MYTUBE-231/test_mytube_231.py::TestDeletePlaylistAsOwner::test_playlist_videos_purged_from_db PASSED
testing/tests/MYTUBE-231/test_mytube_231.py::TestDeletePlaylistAsOwner::test_playlist_row_purged_from_db PASSED
4 passed in ...s
```

When `FIREBASE_TEST_TOKEN` or `FIREBASE_PROJECT_ID` is absent the entire module is
skipped:

```
SKIPPED [4] testing/tests/MYTUBE-231/test_mytube_231.py: FIREBASE_TEST_TOKEN not set — ...
```
