# MYTUBE-111 — Update user profile settings via PUT /api/me

Automates the test case that verifies `PUT /api/me` correctly updates the
user's `username` and `avatar_url` and persists the changes to the database.

## Prerequisites

- Python 3.11+
- Go toolchain (to build the API binary if not already built)
- PostgreSQL accessible with the credentials below
- A valid Firebase ID token (`FIREBASE_TEST_TOKEN`) whose `firebase_uid`
  matches `FIREBASE_TEST_UID`

## Environment Variables

| Variable             | Default                    | Required |
|----------------------|----------------------------|----------|
| `FIREBASE_TEST_TOKEN`| —                          | Yes      |
| `FIREBASE_PROJECT_ID`| —                          | Yes      |
| `FIREBASE_TEST_UID`  | `test-uid-mytube-111`      | No       |
| `API_BINARY`         | `<repo_root>/api/mytube-api` | No     |
| `DB_HOST`            | `localhost`                | No       |
| `DB_PORT`            | `5432`                     | No       |
| `DB_USER`            | `testuser`                 | No       |
| `DB_PASSWORD`        | `testpass`                 | No       |
| `DB_NAME`            | `mytube_test`              | No       |
| `SSL_MODE`           | `disable`                  | No       |

## Install Dependencies

```bash
pip install pytest psycopg2-binary
```

## Run the Test

```bash
cd <repo_root>
FIREBASE_TEST_TOKEN=<token> FIREBASE_PROJECT_ID=<project_id> \
  pytest testing/tests/MYTUBE-111/test_mytube_111.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-111/test_mytube_111.py::TestPutMeEndpoint::test_status_code_is_200 PASSED
testing/tests/MYTUBE-111/test_mytube_111.py::TestPutMeEndpoint::test_response_body_contains_username PASSED
testing/tests/MYTUBE-111/test_mytube_111.py::TestPutMeEndpoint::test_response_username_matches_submitted_value PASSED
testing/tests/MYTUBE-111/test_mytube_111.py::TestPutMeEndpoint::test_response_body_contains_avatar_url PASSED
testing/tests/MYTUBE-111/test_mytube_111.py::TestPutMeEndpoint::test_response_avatar_url_matches_submitted_value PASSED
testing/tests/MYTUBE-111/test_mytube_111.py::TestPutMeEndpoint::test_database_username_is_updated PASSED
testing/tests/MYTUBE-111/test_mytube_111.py::TestPutMeEndpoint::test_database_avatar_url_is_updated PASSED

7 passed in Xs
```

## Skip Behaviour

The entire module is skipped automatically when `FIREBASE_TEST_TOKEN` or
`FIREBASE_PROJECT_ID` are not set. No test will fail due to missing credentials.
