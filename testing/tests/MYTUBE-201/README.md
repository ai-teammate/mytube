# MYTUBE-201: Post comment exceeding character limit

Verifies that `POST /api/videos/:id/comments` rejects a comment body exceeding
2000 characters with HTTP 400 Bad Request.

## Dependencies

```
pip install pytest
```

No additional packages are required — the test uses only Python standard-library
HTTP utilities (`urllib`).

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `FIREBASE_TEST_TOKEN` | **Yes** | Firebase ID token for the CI test user. Test is skipped when absent. |
| `API_BASE_URL` | No | Base URL of the deployed API. Defaults to `https://mytube-api-80693608388.us-central1.run.app` |
| `MYTUBE_201_VIDEO_ID` | No | UUID of a specific video to target. When absent, a ready video is discovered automatically. |

## How to run

```bash
# From repo root
export API_BASE_URL=https://mytube-api-80693608388.us-central1.run.app
export FIREBASE_TEST_TOKEN=<your-firebase-id-token>

pytest testing/tests/MYTUBE-201/test_mytube_201.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-201/test_mytube_201.py::TestCommentCharacterLimitEnforced::test_oversized_comment_body_is_2001_chars PASSED
testing/tests/MYTUBE-201/test_mytube_201.py::TestCommentCharacterLimitEnforced::test_response_status_is_400 PASSED
testing/tests/MYTUBE-201/test_mytube_201.py::TestCommentCharacterLimitEnforced::test_response_body_contains_error_message PASSED
testing/tests/MYTUBE-201/test_mytube_201.py::TestCommentCharacterLimitEnforced::test_response_body_is_json PASSED
testing/tests/MYTUBE-201/test_mytube_201.py::TestCommentCharacterLimitEnforced::test_error_message_mentions_comment_length PASSED

5 passed in <Xs>
```

## Architecture

- **CommentsService** (`testing/components/services/comments_service.py`) — wraps
  `POST /api/videos/:id/comments` with Bearer token authentication.
- **VideoApiService** (`testing/components/services/video_api_service.py`) — discovers
  a ready video from the deployed API when no override is specified.
- **APIConfig** (`testing/core/config/api_config.py`) — loads `API_BASE_URL` from
  the environment.
