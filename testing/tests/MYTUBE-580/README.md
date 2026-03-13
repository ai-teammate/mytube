# MYTUBE-580 — Recommendation Exclusion Criteria: Self and Non-Ready Videos Are Filtered Out

## Objective

Verify that the recommendations endpoint excludes the video being watched (Video A) and any
videos that are not in `ready` status (Video B with `processing`, Video C with `failed`).

## Test Type

`api` — REST API integration test with Go unit-test layer.

## Test Structure

### Layer A — Go Unit Tests (always runs; no DB required)

Runs the existing Go handler unit tests for the recommendations handler:

1. `TestRecommendationsHandler` — all handler unit tests pass.
2. `TestRecommendationsHandler_GET_Success_ReturnsList` — handler maps repository results to correct JSON.
3. `TestRecommendationsHandler_GET_EmptySlice_WhenNoRecommendations` — empty slice serialised correctly.
4. `TestRecommendationsHandler_InvalidVideoID_Returns400` — invalid UUID returns HTTP 400.

### Layer B — Integration Tests via HTTP (requires DB)

1. Seeds a test user, a `Tech` category, and three videos:
   - **Video A**: `status='ready'`, `hls_manifest_path` set, `category='Tech'`
   - **Video B**: `status='processing'`, `category='Tech'`
   - **Video C**: `status='failed'`, `category='Tech'`
2. Starts the Go API binary on a local port.
3. Issues `GET /api/videos/{video_a_id}/recommendations`.
4. Asserts HTTP 200.
5. Asserts Video A is **not** in the recommendations list.
6. Asserts Video B is **not** in the recommendations list.
7. Asserts Video C is **not** in the recommendations list.
8. Teardown removes all seeded rows in FK-safe order.

## Prerequisites

- Python 3.10+
- `pytest`
- `psycopg2-binary` (Layer B only)
- Pre-built Go API binary at `api/mytube-api` (or set `API_BINARY`)

## Environment Variables

| Variable                          | Required for | Description                                              |
|-----------------------------------|--------------|----------------------------------------------------------|
| `API_BINARY`                      | Layer B      | Path to the pre-built Go binary (default: `api/mytube-api`) |
| `DB_HOST`                         | Layer B      | PostgreSQL host                                          |
| `DB_PORT`                         | Layer B      | PostgreSQL port (default: `5432`)                        |
| `DB_USER`                         | Layer B      | PostgreSQL user                                          |
| `DB_PASSWORD`                     | Layer B      | PostgreSQL password                                      |
| `DB_NAME`                         | Layer B      | PostgreSQL database name                                 |
| `SSL_MODE`                        | Layer B      | SSL mode (default: `disable`)                            |
| `FIREBASE_PROJECT_ID`             | Layer B      | Firebase project ID for the API process environment      |
| `GOOGLE_APPLICATION_CREDENTIALS`  | Layer B      | Path to service-account JSON                             |

## Running the Tests

```bash
# Layer A only (no external services needed):
pytest testing/tests/MYTUBE-580/test_mytube_580.py -v

# Both layers (with PostgreSQL available):
DB_HOST=localhost DB_PORT=5432 DB_USER=postgres DB_PASSWORD=secret DB_NAME=mytube \
    pytest testing/tests/MYTUBE-580/test_mytube_580.py -v
```

## Expected Output

```
PASSED  test_recommendations_handler_all_unit_tests_pass
PASSED  test_recommendations_handler_success_returns_list
PASSED  test_recommendations_handler_empty_slice_when_no_recommendations
PASSED  test_recommendations_handler_invalid_video_id_returns_400
SKIPPED test_response_status_is_200            [no DB]
SKIPPED test_response_is_valid_json            [no DB]
SKIPPED test_recommendations_key_present       [no DB]
SKIPPED test_video_a_not_in_recommendations    [no DB]
SKIPPED test_video_b_processing_not_in_recommendations   [no DB]
SKIPPED test_video_c_failed_not_in_recommendations       [no DB]
```

Layer B tests run when a PostgreSQL database is reachable.
