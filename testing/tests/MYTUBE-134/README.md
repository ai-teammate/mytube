# MYTUBE-134: Create video metadata via POST /api/videos

Verifies that an authenticated user can successfully submit video metadata to
`POST /api/videos` and receive a GCS signed PUT URL for upload.

## Dependencies

```
pip install pytest psycopg2-binary
```

The Go API binary is built automatically if not present. Go 1.21+ must be in `PATH`.

## Required environment variables

| Variable | Description |
|---|---|
| `FIREBASE_TEST_TOKEN` | Valid Firebase ID token for the test user |
| `FIREBASE_PROJECT_ID` | Firebase project ID (used by the API's token verifier) |
| `FIREBASE_TEST_UID` | `firebase_uid` of the test user matching the token (default: `test-uid-mytube-134`) |
| `RAW_UPLOADS_BUCKET` | GCS bucket for raw uploads (default: `mytube-raw-uploads`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON with `iam.serviceAccounts.signBlob` permission |

Database variables (all have defaults matching the test DB):

| Variable | Default |
|---|---|
| `DB_HOST` | `localhost` |
| `DB_PORT` | `5432` |
| `DB_USER` | `testuser` |
| `DB_PASSWORD` | `testpass` |
| `DB_NAME` | `mytube_test` |
| `SSL_MODE` | `disable` |

## How to run

From the repository root:

```bash
pytest testing/tests/MYTUBE-134/test_mytube_134.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-134/test_mytube_134.py::TestCreateVideoMetadata::test_status_code_is_201 PASSED
testing/tests/MYTUBE-134/test_mytube_134.py::TestCreateVideoMetadata::test_response_body_is_valid_json PASSED
testing/tests/MYTUBE-134/test_mytube_134.py::TestCreateVideoMetadata::test_response_contains_video_id PASSED
testing/tests/MYTUBE-134/test_mytube_134.py::TestCreateVideoMetadata::test_video_id_is_uuid PASSED
testing/tests/MYTUBE-134/test_mytube_134.py::TestCreateVideoMetadata::test_response_contains_upload_url PASSED
testing/tests/MYTUBE-134/test_mytube_134.py::TestCreateVideoMetadata::test_upload_url_is_non_empty_string PASSED
testing/tests/MYTUBE-134/test_mytube_134.py::TestCreateVideoMetadata::test_upload_url_is_gcs_signed_url PASSED
testing/tests/MYTUBE-134/test_mytube_134.py::TestCreateVideoMetadata::test_video_row_exists_in_database PASSED
```

## Notes

- The test is skipped (not failed) when `FIREBASE_TEST_TOKEN` or `FIREBASE_PROJECT_ID` are not set.
- The Go API binary is built from `api/` if `api/mytube-api` does not already exist.
- Port `18134` is used to avoid conflicts with other integration tests.
