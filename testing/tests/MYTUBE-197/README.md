# MYTUBE-197: Submit and update video rating — rating is upserted and average calculated correctly

Verifies that `POST /api/videos/:id/rating` accepts a star rating (1-5), upserts
it for the authenticated user, and returns a correct `average_rating`, `rating_count`,
and `my_rating` in the response.

## Dependencies

```bash
pip install pytest psycopg2-binary
```

Go toolchain is required for Layer A (unit tests).

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FIREBASE_TEST_TOKEN` | Layer B only | Valid Firebase ID token for the test user |
| `FIREBASE_PROJECT_ID` | Layer B only | Firebase project (default: `ai-native-478811`) |
| `FIREBASE_TEST_UID` | Layer B only | Firebase UID of the test user (default: `ci-test-user-001`) |
| `API_BINARY` | No | Path to the pre-built Go binary (default: `api/mytube-api`) |
| `DB_HOST` | No | PostgreSQL host (default: `localhost`) |
| `DB_PORT` | No | PostgreSQL port (default: `5432`) |
| `DB_USER` | No | PostgreSQL user |
| `DB_PASSWORD` | No | PostgreSQL password |
| `DB_NAME` | No | PostgreSQL database name |
| `SSL_MODE` | No | SSL mode (default: `disable`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | No | GCS service-account JSON path (falls back to mock fixture) |
| `RAW_UPLOADS_BUCKET` | No | GCS bucket name (default: `mytube-raw-uploads`) |

## Running the test

```bash
# From the repo root
pytest testing/tests/MYTUBE-197/test_mytube_197.py -v
```

Layer B (Integration) tests are skipped automatically when `FIREBASE_TEST_TOKEN` is not set.

## Expected output when passing

```
testing/tests/MYTUBE-197/test_mytube_197.py::TestRatingHandler_GoUnit::test_rating_handler_all_unit_tests_pass PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestRatingHandler_GoUnit::test_post_valid_stars_returns_updated_summary PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestRatingHandler_GoUnit::test_post_all_valid_star_values PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestRatingHandler_GoUnit::test_post_no_auth_returns_401 PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestRatingHandler_GoUnit::test_post_invalid_stars_returns_422 PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_first_rating_status_200 PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_first_rating_response_is_valid_json PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_first_rating_fields_present PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_first_rating_average_is_5 PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_first_rating_count_is_1 PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_first_rating_my_rating_is_5 PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_upsert_rating_status_200 PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_upsert_rating_response_is_valid_json PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_upsert_rating_fields_present PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_upsert_rating_average_is_2 PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_upsert_rating_count_remains_1 PASSED
testing/tests/MYTUBE-197/test_mytube_197.py::TestSubmitAndUpdateRating::test_upsert_rating_my_rating_is_2 PASSED
```

## Notes

- Layer A (Go unit tests) always runs and does not require any external services.
- Layer B uses a local Go API server started as a subprocess. The test seeds
  its own user and video rows and cleans up the ratings it creates.
- The rating endpoint uses `ON CONFLICT (video_id, user_id) DO UPDATE` so a
  second POST by the same user overwrites rather than duplicates the rating.
