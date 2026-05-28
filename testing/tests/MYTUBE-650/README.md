# MYTUBE-650: Delete avatar via API — avatar URL cleared and 204 returned

## Overview

Tests that `DELETE /api/me/avatar` returns HTTP 204 No Content and clears the
user's `avatar_url` field in the database, verified via a subsequent `GET /api/me`.

## Dependencies

Install Python dependencies from the repository requirements file:

```bash
pip install -r testing/requirements.txt
```

## Required environment variables

| Variable | Description |
|---|---|
| `FIREBASE_TEST_TOKEN` | Firebase ID token for the test user (required) |
| `FIREBASE_PROJECT_ID` | Firebase project ID (required by API server) |
| `FIREBASE_TEST_UID` | Firebase UID stored in the DB row (default: `ci-test-user-001`) |
| `DB_HOST` | PostgreSQL host (default: `localhost`) |
| `DB_PORT` | PostgreSQL port (default: `5432`) |
| `DB_USER` | PostgreSQL user (default: `postgres`) |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_NAME` | PostgreSQL database name (default: `mytube`) |
| `SSL_MODE` | PostgreSQL SSL mode (default: `disable`) |
| `HLS_BUCKET` | GCS bucket name (default: `mytube-hls-output`) |
| `CDN_BASE_URL` | CDN base URL (default: `https://storage.googleapis.com/mytube-hls-output`) |

## Run command

```bash
pytest testing/tests/MYTUBE-650/test_mytube_650.py -v
```

## Expected output when passing

```
PASSED testing/tests/MYTUBE-650/test_mytube_650.py::TestDeleteAvatar::test_delete_returns_204
PASSED testing/tests/MYTUBE-650/test_mytube_650.py::TestDeleteAvatar::test_delete_response_body_is_empty
PASSED testing/tests/MYTUBE-650/test_mytube_650.py::TestDeleteAvatar::test_get_me_returns_200
PASSED testing/tests/MYTUBE-650/test_mytube_650.py::TestDeleteAvatar::test_avatar_url_is_cleared
4 passed
```
