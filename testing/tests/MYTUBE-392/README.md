# MYTUBE-392 — POST /api/videos by registered user

## Objective
Verify that an already-registered user can create a video record via POST /api/videos and receive HTTP 201 with `video_id` and `upload_url`, without triggering duplicate user creation.

## Preconditions
- `FIREBASE_TEST_TOKEN` — valid Firebase ID token for the test user
- `FIREBASE_TEST_UID` — Firebase UID of the pre-existing user (default: `ci-registered-user`)
- Database connection env vars: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `SSL_MODE`
- `API_BASE_URL` — base URL of the deployed API

## How to run
```
pytest testing/tests/MYTUBE-392/
```
