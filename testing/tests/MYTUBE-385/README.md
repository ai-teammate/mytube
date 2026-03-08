# MYTUBE-385: POST /api/videos — new Firebase user auto-provisioned, 201 Created returned

## Objective

Verify that the API automatically provisions a user in the local database when a
first-time Firebase-authenticated user attempts to create a video, preventing a
404 error, and returns 201 Created with a signed GCS upload URL.

## Dependencies

```
pip install pytest psycopg2-binary
```

(All packages are listed in `testing/requirements.txt`.)

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `FIREBASE_TEST_TOKEN` | **Required** | Valid Firebase ID token for the CI test user |
| `API_BASE_URL` | Optional | Deployed API base URL (default: `http://localhost:8080`) |
| `FIREBASE_TEST_UID` | Optional | Firebase UID of the test user (used for DB check) |
| `DB_HOST` | Optional | Postgres host for DB provisioning check |
| `DB_PORT` | Optional | Postgres port (default 5432) |
| `DB_USER` | Optional | Postgres user |
| `DB_PASSWORD` | Optional | Postgres password |
| `DB_NAME` | Optional | Postgres database name |
| `SSL_MODE` | Optional | `disable` or `require` (default `disable`) |

## How to Run

```bash
cd /path/to/mytube
export FIREBASE_TEST_TOKEN="<your-token>"
export API_BASE_URL="https://mytube-api-jxl6bnwdaa-uc.a.run.app"

pytest testing/tests/MYTUBE-385/test_mytube_385.py -v
```

## Expected Output (pass)

```
PASSED  test_post_videos_returns_201
PASSED  test_response_contains_video_id
PASSED  test_response_contains_upload_url
PASSED  test_user_provisioned_in_db          (skipped if DB not reachable)
```
