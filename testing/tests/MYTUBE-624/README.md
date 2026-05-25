# MYTUBE-624 — Upload valid JPEG avatar

## What this test verifies

POST `/api/me/avatar` with a valid JPEG file:
- Returns HTTP 200 OK
- Response JSON contains `avatar_url` pointing to GCS `avatars/` prefix
- Database `avatar_url` matches the returned URL

## Dependencies

Install from the repo root:

```bash
pip install -r testing/requirements.txt
```

## Required environment variables

| Variable | Description | Default |
|---|---|---|
| `API_BASE_URL` | Backend API base URL | `http://localhost:8080` |
| `FIREBASE_TEST_TOKEN` | Firebase ID token for CI test user | *(required — test skips if absent)* |
| `FIREBASE_TEST_UID` | Firebase UID of CI test user | `ci-test-user-001` |
| `CDN_BASE_URL` | Public CDN base URL for avatar objects | `https://storage.googleapis.com/mytube-hls-output` |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` / `SSL_MODE` | DB connection settings | sensible defaults |

## How to run

```bash
pytest testing/tests/MYTUBE-624/test_mytube_624.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-624/test_mytube_624.py::TestAvatarUpload::test_http_status_is_200 PASSED
testing/tests/MYTUBE-624/test_mytube_624.py::TestAvatarUpload::test_response_contains_avatar_url PASSED
testing/tests/MYTUBE-624/test_mytube_624.py::TestAvatarUpload::test_avatar_url_is_non_empty PASSED
testing/tests/MYTUBE-624/test_mytube_624.py::TestAvatarUpload::test_avatar_url_under_avatars_prefix PASSED
testing/tests/MYTUBE-624/test_mytube_624.py::TestAvatarUpload::test_avatar_url_starts_with_cdn_base PASSED
testing/tests/MYTUBE-624/test_mytube_624.py::TestAvatarUpload::test_avatar_url_ends_with_jpg_extension PASSED
testing/tests/MYTUBE-624/test_mytube_624.py::TestAvatarUpload::test_database_avatar_url_matches_response PASSED

7 passed
```
