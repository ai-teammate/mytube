# MYTUBE-136: Submit video metadata without required title — API returns 4xx

Verifies that `POST /api/videos` rejects requests where the `title` field is
empty, null, or absent, returning a 4xx status with a JSON error body that
mentions "title".

## Dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FIREBASE_TEST_TOKEN` | Yes | Valid Firebase ID token for an authenticated user |
| `FIREBASE_PROJECT_ID` | Yes | Firebase project the token was issued for |
| `API_BINARY` | No | Path to the pre-built Go binary (default: `api/mytube-api`) |
| `DB_HOST` | No | PostgreSQL host (default: `localhost`) |
| `DB_PORT` | No | PostgreSQL port (default: `5432`) |
| `DB_USER` | No | PostgreSQL user |
| `DB_PASSWORD` | No | PostgreSQL password |
| `DB_NAME` | No | PostgreSQL database name |
| `SSL_MODE` | No | SSL mode (default: `disable`) |

## Running the test

```bash
pytest testing/tests/MYTUBE-136/test_mytube_136.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-136/test_mytube_136.py::TestSubmitVideoWithoutTitle::test_empty_title_returns_4xx_status PASSED
testing/tests/MYTUBE-136/test_mytube_136.py::TestSubmitVideoWithoutTitle::test_empty_title_response_is_valid_json PASSED
testing/tests/MYTUBE-136/test_mytube_136.py::TestSubmitVideoWithoutTitle::test_empty_title_response_contains_error_field PASSED
testing/tests/MYTUBE-136/test_mytube_136.py::TestSubmitVideoWithoutTitle::test_empty_title_error_mentions_title PASSED
testing/tests/MYTUBE-136/test_mytube_136.py::TestSubmitVideoWithoutTitle::test_null_title_returns_4xx_status PASSED
testing/tests/MYTUBE-136/test_mytube_136.py::TestSubmitVideoWithoutTitle::test_null_title_response_contains_error_field PASSED
testing/tests/MYTUBE-136/test_mytube_136.py::TestSubmitVideoWithoutTitle::test_missing_title_returns_4xx_status PASSED
testing/tests/MYTUBE-136/test_mytube_136.py::TestSubmitVideoWithoutTitle::test_missing_title_response_contains_error_field PASSED
```

## Notes

The API returns **HTTP 422 Unprocessable Entity** (not 400) for validation
failures. The test accepts any 4xx status code to remain consistent with the
intent of the ticket (reject invalid input) while accurately reflecting the
actual implementation.
