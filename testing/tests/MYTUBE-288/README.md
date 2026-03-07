# MYTUBE-288 — Retrieve video metadata: category_id is included in response

Verifies that `GET /api/videos/:id` includes the `category_id` field in the
JSON response body, with its value matching what is stored in the database.

## Dependencies

```bash
pip install pytest psycopg2-binary
```

The Go API binary must be compiled or already present at `api/mytube-api`:

```bash
cd api && go build -o mytube-api .
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `API_BINARY` | no | `api/mytube-api` | Path to the pre-built Go binary |
| `DB_HOST` | no | `localhost` | PostgreSQL host |
| `DB_PORT` | no | `5432` | PostgreSQL port |
| `DB_USER` | no | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | no | `testpass` | PostgreSQL password |
| `DB_NAME` | no | `mytube_test` | PostgreSQL database name |
| `SSL_MODE` | no | `disable` | PostgreSQL SSL mode |
| `FIREBASE_PROJECT_ID` | no | `ai-native-478811` | Firebase project ID |
| `FIREBASE_TEST_UID` | no | `ci-test-user-288` | Firebase UID used for the test user |
| `GOOGLE_APPLICATION_CREDENTIALS` | no | `testing/fixtures/mock_service_account.json` | Path to GCS service-account JSON |
| `RAW_UPLOADS_BUCKET` | no | `mytube-raw-uploads` | GCS bucket name |

## Run the test

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-288/test_mytube_288.py -v
```

## Expected output

```
testing/tests/MYTUBE-288/test_mytube_288.py::TestVideoHandler_CategoryID_GoUnit::test_category_id_included_in_response PASSED
testing/tests/MYTUBE-288/test_mytube_288.py::TestVideoHandler_CategoryID_GoUnit::test_category_id_nil_when_not_set PASSED
testing/tests/MYTUBE-288/test_mytube_288.py::TestVideoMetadataCategoryID::test_status_code_is_200 PASSED
testing/tests/MYTUBE-288/test_mytube_288.py::TestVideoMetadataCategoryID::test_category_id_field_present PASSED
testing/tests/MYTUBE-288/test_mytube_288.py::TestVideoMetadataCategoryID::test_category_id_is_not_none PASSED
testing/tests/MYTUBE-288/test_mytube_288.py::TestVideoMetadataCategoryID::test_category_id_matches_stored_value PASSED
6 passed in ...s
```

When PostgreSQL is not reachable the Layer B integration tests are skipped
automatically:

```
SKIPPED [4] testing/tests/MYTUBE-288/test_mytube_288.py: PostgreSQL is not reachable at ...
```
