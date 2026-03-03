# MYTUBE-188 — Update video metadata as owner

Automated test for: **PUT /api/videos/:id** — verifies that the owner of a
video can update title, description, category_id, and tags, and that all
changes are reflected in both the API response and the database.

## Dependencies

```
pip install psycopg2-binary pytest
```

The Go API binary must be buildable (or pre-built at `api/mytube-api`):

```bash
cd api && go build -o mytube-api .
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FIREBASE_TEST_TOKEN` | Yes | — | Valid Firebase ID token for the test user |
| `FIREBASE_PROJECT_ID` | Yes | — | Firebase project ID (used by the API verifier) |
| `FIREBASE_TEST_UID` | No | `test-uid-mytube-188` | Firebase UID embedded in the test token |
| `API_BINARY` | No | `api/mytube-api` | Path to the pre-built Go binary |
| `DB_HOST` | No | `localhost` | PostgreSQL host |
| `DB_PORT` | No | `5432` | PostgreSQL port |
| `DB_USER` | No | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | No | `testpass` | PostgreSQL password |
| `DB_NAME` | No | `mytube_test` | PostgreSQL database name |
| `SSL_MODE` | No | `disable` | PostgreSQL SSL mode |

## How to run

From the repository root:

```bash
FIREBASE_TEST_TOKEN=<token> \
FIREBASE_PROJECT_ID=<project_id> \
DB_HOST=localhost DB_USER=... DB_PASSWORD=... DB_NAME=... \
pytest testing/tests/MYTUBE-188/test_mytube_188.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_put_status_code_is_200 PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_put_response_is_valid_json PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_put_response_title_is_updated PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_put_response_description_is_updated PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_put_response_category_id_is_updated PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_put_response_tags_are_updated PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_get_status_code_is_200 PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_get_response_title_persisted PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_get_response_description_persisted PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_get_response_category_id_persisted PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_get_response_tags_persisted PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_db_title_persisted PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_db_description_persisted PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_db_category_id_persisted PASSED
testing/tests/MYTUBE-188/test_mytube_188.py::TestUpdateVideoMetadata::test_db_tags_persisted PASSED

15 passed in X.XXs
```
