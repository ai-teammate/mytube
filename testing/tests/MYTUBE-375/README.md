# MYTUBE-375 — Delete video with DELETE_ON_VIDEO_DELETE=false: GCS files retained

## Summary
Verifies that setting `DELETE_ON_VIDEO_DELETE=false` prevents GCS file cleanup on video deletion,
while the database record is still updated to `deleted`.

## Dependencies
```
pip install -r testing/requirements.txt
```

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DB_HOST` | Layer B | `localhost` | PostgreSQL host |
| `DB_PORT` | Layer B | `5432` | PostgreSQL port |
| `DB_USER` | Layer B | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | Layer B | `testpass` | PostgreSQL password |
| `DB_NAME` | Layer B | `mytube_test` | PostgreSQL database |
| `FIREBASE_TEST_TOKEN` | Layer B | — | Firebase ID token for auth |
| `FIREBASE_PROJECT_ID` | Layer B | `ai-native-478811` | Firebase project ID |
| `FIREBASE_TEST_UID` | Layer B | `ci-test-user-001` | UID in the test token |
| `GOOGLE_APPLICATION_CREDENTIALS` | Layer B (GCS check) | — | GCS service-account JSON |
| `GCP_PROJECT_ID` | Layer B (GCS check) | `ai-native-478811` | GCP project ID |
| `API_BINARY` | Layer B | `api/mytube-api` | Path to Go binary |

## How to Run

```bash
# From the repository root:
cd /path/to/repo
python -m pytest testing/tests/MYTUBE-375/test_mytube_375.py -v
```

## Layer A — Go unit tests (always runs)
Runs `TestDeleteVideo_GCSCleanupDisabled_DoesNotDelete` from the Go handler test suite.
No database or network access required.

## Layer B — Integration tests (requires DB + Firebase token)
Starts the Go API binary with `DELETE_ON_VIDEO_DELETE=false`, seeds a video with GCS paths,
issues a `DELETE /api/videos/:id` request, and asserts:
- HTTP 204 No Content
- DB record status is `deleted`
- GCS raw file still exists (when `GOOGLE_APPLICATION_CREDENTIALS` is available)

## Expected Output (all passing)

```
PASSED testing/tests/MYTUBE-375/test_mytube_375.py::TestDeleteVideoGCSCleanupDisabledGoUnit::test_gcs_cleanup_disabled_does_not_delete
PASSED testing/tests/MYTUBE-375/test_mytube_375.py::TestDeleteVideoGCSCleanupDisabledIntegration::test_delete_returns_204
PASSED testing/tests/MYTUBE-375/test_mytube_375.py::TestDeleteVideoGCSCleanupDisabledIntegration::test_db_status_is_deleted
PASSED testing/tests/MYTUBE-375/test_mytube_375.py::TestDeleteVideoGCSCleanupDisabledIntegration::test_gcs_raw_file_still_exists
```
