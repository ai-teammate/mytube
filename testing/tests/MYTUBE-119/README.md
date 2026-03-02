# MYTUBE-119: Profile video list limit — API returns a maximum of 50 videos

## Purpose

Verifies that the public profile endpoint `GET /api/users/:username` enforces
the MVP limit of 50 videos per request, even when the user has more than 50
ready videos in the database.

## Prerequisites

- Python 3.11+
- Go toolchain (for building the API binary)
- PostgreSQL test database accessible via environment variables

## Install dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment variables

| Variable              | Default           | Required | Description                                           |
|-----------------------|-------------------|----------|-------------------------------------------------------|
| `FIREBASE_PROJECT_ID` | `dummy-project`   | No       | Firebase project ID (placeholder accepted; endpoint is public) |
| `API_BINARY`          | `api/mytube-api`  | No       | Path to pre-built Go binary                           |
| `DB_HOST`             | `localhost`       | No       | PostgreSQL host                                       |
| `DB_PORT`             | `5432`            | No       | PostgreSQL port                                       |
| `DB_USER`             | `testuser`        | No       | PostgreSQL user                                       |
| `DB_PASSWORD`         | `testpass`        | No       | PostgreSQL password                                   |
| `DB_NAME`             | `mytube_test`     | No       | PostgreSQL database name                              |

## Run

```bash
pytest testing/tests/MYTUBE-119/test_mytube_119.py -v
```

## Expected output (when passing)

```
PASSED testing/tests/MYTUBE-119/test_mytube_119.py::TestProfileVideoListLimit::test_status_code_is_200
PASSED testing/tests/MYTUBE-119/test_mytube_119.py::TestProfileVideoListLimit::test_response_body_is_valid_json
PASSED testing/tests/MYTUBE-119/test_mytube_119.py::TestProfileVideoListLimit::test_response_contains_videos_array
PASSED testing/tests/MYTUBE-119/test_mytube_119.py::TestProfileVideoListLimit::test_videos_array_is_a_list
PASSED testing/tests/MYTUBE-119/test_mytube_119.py::TestProfileVideoListLimit::test_videos_count_is_exactly_50
```

## Test structure

| Test | What it verifies |
|------|-----------------|
| `test_status_code_is_200` | The endpoint returns HTTP 200 OK |
| `test_response_body_is_valid_json` | The response body is parseable JSON |
| `test_response_contains_videos_array` | The JSON body contains a `videos` key |
| `test_videos_array_is_a_list` | The `videos` value is a JSON array |
| `test_videos_count_is_exactly_50` | The `videos` array contains exactly 50 items even though 60 were seeded |
