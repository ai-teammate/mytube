# MYTUBE-187: GET /api/me/videos — returns correct metadata for authenticated uploader

Verifies that `GET /api/me/videos` returns only the authenticated user's videos,
each containing the required metadata fields.

## Dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `FIREBASE_TEST_TOKEN` | Yes | Firebase ID token for the test user (expires in 1h — generate at runtime) |
| `FIREBASE_PROJECT_ID` | Yes | Firebase project ID (e.g. `ai-native-478811`) |
| `FIREBASE_TEST_UID` | No | firebase_uid of the test user (default: `test-uid-mytube-187`) |
| `API_BINARY` | No | Path to pre-built Go binary (default: `<repo_root>/api/mytube-api`) |
| `DB_HOST` | No | PostgreSQL host (default: `localhost`) |
| `DB_PORT` | No | PostgreSQL port (default: `5432`) |
| `DB_USER` | No | PostgreSQL user (default: `testuser`) |
| `DB_PASSWORD` | No | PostgreSQL password (default: `testpass`) |
| `DB_NAME` | No | PostgreSQL database name (default: `mytube_test`) |
| `SSL_MODE` | No | PostgreSQL SSL mode (default: `disable`) |

## How to Run

From the repository root:

```bash
pytest testing/tests/MYTUBE-187/test_mytube_187.py -v
```

## Expected Output (when credentials are set)

```
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_status_code_is_200 PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_response_body_is_valid_json PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_response_body_is_array PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_response_contains_all_owner_videos PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_response_excludes_other_user_videos PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_each_video_has_required_fields PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_video_id_is_non_empty_string PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_video_title_is_non_empty_string PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_video_status_is_string PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_video_view_count_is_non_negative_integer PASSED
testing/tests/MYTUBE-187/test_mytube_187.py::TestGetMeVideos::test_video_created_at_is_non_empty_string PASSED
```

## Expected Output (when credentials are missing)

```
SKIPPED - FIREBASE_TEST_TOKEN not set — skipping GET /api/me/videos integration test.
```
