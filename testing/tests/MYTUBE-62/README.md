# MYTUBE-62: GET /api/me — returns current user profile data

## Purpose

Verifies that the `/api/me` endpoint returns the authenticated user's identification and profile details when called with a valid Firebase Bearer token.

## Prerequisites

- Python 3.11+
- Go toolchain (for building the API binary)
- PostgreSQL test database accessible via environment variables
- A valid Firebase ID token for a test user

## Install dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment variables

| Variable             | Default          | Required | Description                                           |
|----------------------|------------------|----------|-------------------------------------------------------|
| `FIREBASE_TEST_TOKEN`| —                | **Yes**  | Valid Firebase ID token for the test user             |
| `FIREBASE_PROJECT_ID`| —                | **Yes**  | Firebase project ID used to initialise the verifier  |
| `FIREBASE_TEST_UID`  | `test-uid-mytube-62` | No   | firebase_uid that the token belongs to               |
| `API_BINARY`         | `api/mytube-api` | No       | Path to pre-built Go binary                           |
| `DB_HOST`            | `localhost`      | No       | PostgreSQL host                                       |
| `DB_PORT`            | `5432`           | No       | PostgreSQL port                                       |
| `DB_USER`            | `testuser`       | No       | PostgreSQL user                                       |
| `DB_PASSWORD`        | `testpass`       | No       | PostgreSQL password                                   |
| `DB_NAME`            | `mytube_test`    | No       | PostgreSQL database name                              |

## Run

```bash
FIREBASE_TEST_TOKEN=<token> FIREBASE_PROJECT_ID=<project> \
  pytest testing/tests/MYTUBE-62/test_mytube_62.py -v
```

## Expected output

```
PASSED test_mytube_62.py::TestGetMeEndpoint::test_status_code_is_200
PASSED test_mytube_62.py::TestGetMeEndpoint::test_response_body_contains_id
PASSED test_mytube_62.py::TestGetMeEndpoint::test_id_is_uuid
PASSED test_mytube_62.py::TestGetMeEndpoint::test_response_body_contains_username
PASSED test_mytube_62.py::TestGetMeEndpoint::test_username_is_non_empty_string
PASSED test_mytube_62.py::TestGetMeEndpoint::test_response_body_contains_avatar_url_key
```

## Skip behaviour

When `FIREBASE_TEST_TOKEN` or `FIREBASE_PROJECT_ID` are not set the entire test module is skipped with an informational message.
