# MYTUBE-235 — Remove video from playlist via API

Verifies that the playlist owner can remove a specific video from their playlist:
the `DELETE /api/playlists/:id/videos/:video_id` endpoint returns a success status
and the subsequent `GET /api/playlists/:id` no longer contains the video.

## Dependencies

```bash
pip install pytest cloud-sql-python-connector[pg8000]
```

## Required environment variables

| Variable | Source | Description |
|---|---|---|
| `FIREBASE_TEST_TOKEN` | CI secret (generated at runtime) | Valid Firebase ID token for the CI test user |
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
pytest testing/tests/MYTUBE-235/test_mytube_235.py -v
```

## Expected output (passing)

```
PASSED  test_delete_video_from_playlist_returns_success_status
PASSED  test_get_playlist_returns_200
PASSED  test_video_absent_from_playlist_after_delete
```

The test is skipped (not failed) when `FIREBASE_TEST_TOKEN` is absent.
