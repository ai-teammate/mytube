# MYTUBE-200 — Post video comment

Automates the test case: **Post video comment — comment created with author info and returned in response**.

## What is tested

`POST /api/videos/:id/comments` with a valid Firebase Bearer token must return **HTTP 201** and a JSON body containing:

| Field | Expected |
|---|---|
| `id` | UUID string |
| `body` | The submitted comment text |
| `author.username` | Non-empty string |
| `author.avatar_url` | Present (may be `null`) |
| `created_at` | Non-empty timestamp string |

## Test structure

| Layer | What runs | When |
|---|---|---|
| **A** — Go unit tests | `go test ./internal/handler/ -run TestVideoCommentsHandler_POST_*` | Always |
| **B** — HTTP integration | Full API server + real HTTP POST | `FIREBASE_TEST_TOKEN` is set |

## Dependencies

```bash
pip install pytest psycopg2-binary
```

Go toolchain must be installed for Layer A (and for building the binary in Layer B).

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `FIREBASE_TEST_TOKEN` | Layer B only | Valid Firebase ID token |
| `FIREBASE_PROJECT_ID` | Layer B only | Firebase project ID (default: `test-project`) |
| `FIREBASE_TEST_UID` | Layer B only | UID for the test user row (default: `test-uid-mytube-200`) |
| `API_BINARY` | Layer B only | Path to the pre-built Go binary (default: `<repo_root>/api/mytube-api`) |
| `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME` | Layer B only | Database connection |

## How to run

### Layer A only (no credentials needed)

```bash
cd <repo_root>
pytest testing/tests/MYTUBE-200/test_mytube_200.py::TestPostCommentGoUnit -v
```

### Full test (Layer A + B)

```bash
export FIREBASE_TEST_TOKEN=<your-firebase-id-token>
export FIREBASE_PROJECT_ID=ai-native-478811
export FIREBASE_TEST_UID=ci-test-user-001
export DB_HOST=localhost DB_PORT=5432 DB_USER=... DB_PASSWORD=... DB_NAME=...

cd <repo_root>
pytest testing/tests/MYTUBE-200/test_mytube_200.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostCommentGoUnit::test_post_comment_success_returns_201_unit PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostCommentGoUnit::test_post_comment_no_auth_returns_401_unit PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostCommentGoUnit::test_post_comment_empty_body_returns_422_unit PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_status_code_is_201 PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_response_body_is_valid_json PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_response_contains_id PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_id_is_uuid PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_response_contains_body PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_body_matches_submitted_text PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_response_contains_author PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_author_has_username PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_author_has_avatar_url_key PASSED
testing/tests/MYTUBE-200/test_mytube_200.py::TestPostVideoComment::test_response_contains_created_at PASSED
```
