# MYTUBE-649: GCS object key versioning — unique path per upload

## What this test verifies

Verifies that every avatar upload for the same user produces a **unique** GCS
object key (and thus a distinct CDN URL) to prevent browser/CDN cache staleness
(regression guard for bug MYTUBE-642).

The fix introduced a UUID component into the path:
`avatars/{userID}/{uuid}.{ext}` — making each upload cache-busting.

## How to install dependencies

```bash
pip install -r testing/requirements.txt
```

## How to run

```bash
pytest testing/tests/MYTUBE-649/test_mytube_649.py -v
```

## Required environment variables

| Variable | Required | Description |
|---|---|---|
| `FIREBASE_TEST_TOKEN` | ✅ | Firebase ID token for the test user |
| `FIREBASE_PROJECT_ID` | ✅ | Firebase project ID |
| `FIREBASE_TEST_UID` | optional | Firebase UID stored in DB (default: `ci-test-user-001`) |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` | optional | DB connection (defaults to localhost) |
| `HLS_BUCKET` | optional | GCS bucket for avatar storage |
| `CDN_BASE_URL` | optional | Public CDN URL for the bucket |
| `API_BINARY` | optional | Path to pre-built Go binary (default: `/tmp/mytube-api-649`) |

## Expected output when passing

```
testing/tests/MYTUBE-649/test_mytube_649.py::TestGCSKeyVersioningUniquePerUpload::test_first_upload_returns_200 PASSED
testing/tests/MYTUBE-649/test_mytube_649.py::TestGCSKeyVersioningUniquePerUpload::test_first_upload_returns_avatar_url PASSED
testing/tests/MYTUBE-649/test_mytube_649.py::TestGCSKeyVersioningUniquePerUpload::test_second_upload_returns_200 PASSED
testing/tests/MYTUBE-649/test_mytube_649.py::TestGCSKeyVersioningUniquePerUpload::test_second_upload_returns_avatar_url PASSED
testing/tests/MYTUBE-649/test_mytube_649.py::TestGCSKeyVersioningUniquePerUpload::test_consecutive_uploads_produce_unique_urls PASSED
testing/tests/MYTUBE-649/test_mytube_649.py::TestGCSKeyVersioningUniquePerUpload::test_first_url_contains_versioning_component PASSED
testing/tests/MYTUBE-649/test_mytube_649.py::TestGCSKeyVersioningUniquePerUpload::test_second_url_contains_versioning_component PASSED
testing/tests/MYTUBE-649/test_mytube_649.py::TestGCSKeyVersioningUniquePerUpload::test_url_pattern_uses_directory_per_user PASSED
testing/tests/MYTUBE-649/test_mytube_649.py::TestGCSKeyVersioningUniquePerUpload::test_version_uuids_differ_between_uploads PASSED

9 passed in ...s
```
