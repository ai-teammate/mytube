# MYTUBE-637 — Avatar upload API error: error message displayed and URL preserved

## Objective

Verify that the UI handles backend upload failures gracefully without losing existing data.

## How to install dependencies

```bash
pip install -r testing/requirements.txt
playwright install chromium
```

## Required environment variables

| Variable | Description |
|----------|-------------|
| `FIREBASE_TEST_EMAIL` | Email of the Firebase test user |
| `FIREBASE_TEST_PASSWORD` | Password for the Firebase test user |
| `APP_URL` | Base URL of the deployed frontend (default: `https://ai-teammate.github.io/mytube`) |
| `API_BASE_URL` | Backend API URL (used to derive the upload endpoint to intercept) |

## Run command

```bash
pytest testing/tests/MYTUBE-637/test_mytube_637.py -v
```

## Expected output when the test passes

```
PASSED testing/tests/MYTUBE-637/test_mytube_637.py::TestAvatarUploadApiError::test_upload_error_message_is_visible
PASSED testing/tests/MYTUBE-637/test_mytube_637.py::TestAvatarUploadApiError::test_avatar_url_field_preserved_on_upload_error
PASSED testing/tests/MYTUBE-637/test_mytube_637.py::TestAvatarUploadApiError::test_upload_error_is_near_upload_control
```
