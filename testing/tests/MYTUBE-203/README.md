# MYTUBE-203 — Delete own comment — comment is hard-deleted from the system

Automates the test case that verifies an authenticated user can permanently
delete their own comment via `DELETE /api/comments/:id`, and that the comment
is no longer returned by `GET /api/videos/:id/comments` afterwards.

## Prerequisites

- Python 3.11+
- A valid Firebase ID token (`FIREBASE_TEST_TOKEN`)

## Environment Variables

| Variable              | Default                                                   | Required |
|-----------------------|-----------------------------------------------------------|----------|
| `FIREBASE_TEST_TOKEN` | —                                                         | Yes      |
| `API_BASE_URL`        | `https://mytube-api-80693608388.us-central1.run.app`      | No       |

## Install Dependencies

```bash
pip install pytest
```

## Run the Test

```bash
cd <repo_root>
FIREBASE_TEST_TOKEN=<token> \
  pytest testing/tests/MYTUBE-203/test_mytube_203.py -v
```

To run against a local API server instead of the deployed API:

```bash
FIREBASE_TEST_TOKEN=<token> API_BASE_URL=http://localhost:8080 \
  pytest testing/tests/MYTUBE-203/test_mytube_203.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-203/test_mytube_203.py::TestDeleteOwnComment::test_post_comment_returns_201 PASSED
testing/tests/MYTUBE-203/test_mytube_203.py::TestDeleteOwnComment::test_post_comment_response_contains_id PASSED
testing/tests/MYTUBE-203/test_mytube_203.py::TestDeleteOwnComment::test_delete_comment_returns_204 PASSED
testing/tests/MYTUBE-203/test_mytube_203.py::TestDeleteOwnComment::test_comment_list_status_is_200 PASSED
testing/tests/MYTUBE-203/test_mytube_203.py::TestDeleteOwnComment::test_deleted_comment_absent_from_list PASSED

5 passed in Xs
```

## Skip Behaviour

The entire module is skipped automatically when `FIREBASE_TEST_TOKEN` is not set.
No test will fail due to missing credentials.
