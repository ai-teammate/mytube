# MYTUBE-59: Authenticate with valid new Firebase token — user auto-provisioned in database

## Objective

Verify that when a new user authenticates via Firebase for the first time (sending
`GET /api/me` with a valid Bearer token), the API returns HTTP 200 and automatically
inserts a new row into the `users` table with a generated UUID, the correct
`firebase_uid`, and a `username` derived from the email prefix.

## Prerequisites

- Python 3.10+
- PostgreSQL 14+ running and accessible
- Go 1.24+ (to build the API server if not pre-built)
- `psycopg2-binary` and `pytest` installed
- A **real** Firebase project with a valid ID token for a user not yet in the DB

```bash
pip install pytest psycopg2-binary
```

## Environment Variables

| Variable               | Default       | Description                                                    |
|------------------------|---------------|----------------------------------------------------------------|
| `FIREBASE_TEST_TOKEN`  | *(required)*  | Valid Firebase ID token for a user not yet in the users table  |
| `FIREBASE_TEST_UID`    | *(required)*  | Firebase UID encoded in the token                              |
| `FIREBASE_TEST_EMAIL`  | *(required)*  | Email address associated with the token                        |
| `FIREBASE_PROJECT_ID`  | *(required)*  | Firebase project ID                                            |
| `DB_HOST`              | `localhost`   | PostgreSQL host                                                |
| `DB_PORT`              | `5432`        | PostgreSQL port                                                |
| `DB_USER`              | `testuser`    | PostgreSQL user                                                |
| `DB_PASSWORD`          | `testpass`    | PostgreSQL password                                            |
| `DB_NAME`              | `mytube_test` | PostgreSQL database name                                       |
| `SSL_MODE`             | `disable`     | PostgreSQL SSL mode                                            |
| `API_HOST`             | `localhost`   | API server host                                                |
| `API_PORT`             | `8080`        | API server port                                                |
| `API_SERVER_BINARY`    | `api/server`  | Path to the pre-built Go API binary                            |

## How to Run

```bash
export FIREBASE_TEST_TOKEN="<your-firebase-id-token>"
export FIREBASE_TEST_UID="<firebase-uid>"
export FIREBASE_TEST_EMAIL="user@example.com"
export FIREBASE_PROJECT_ID="<your-project-id>"

pytest testing/tests/MYTUBE-59/test_mytube_59.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-59/test_mytube_59.py::TestFirebaseAutoProvision::test_returns_200_ok PASSED
testing/tests/MYTUBE-59/test_mytube_59.py::TestFirebaseAutoProvision::test_response_body_is_valid_json PASSED
testing/tests/MYTUBE-59/test_mytube_59.py::TestFirebaseAutoProvision::test_response_body_contains_id PASSED
testing/tests/MYTUBE-59/test_mytube_59.py::TestFirebaseAutoProvision::test_response_body_contains_username PASSED
testing/tests/MYTUBE-59/test_mytube_59.py::TestFirebaseAutoProvision::test_user_row_exists_in_database PASSED
testing/tests/MYTUBE-59/test_mytube_59.py::TestFirebaseAutoProvision::test_user_row_has_generated_uuid PASSED
testing/tests/MYTUBE-59/test_mytube_59.py::TestFirebaseAutoProvision::test_user_row_has_correct_firebase_uid PASSED
testing/tests/MYTUBE-59/test_mytube_59.py::TestFirebaseAutoProvision::test_user_row_has_username_from_email_prefix PASSED

8 passed
```
