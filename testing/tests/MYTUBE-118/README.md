# MYTUBE-118: Profile video list filtering — only "ready" videos are displayed

## Purpose

Verifies that the public profile endpoint `GET /api/users/:username` returns only
videos with `status = 'ready'`, and that videos with `status = 'processing'` (or any
other non-ready status) are excluded from the response.

## Prerequisites

- Python 3.11+
- Go toolchain (for building the API binary)
- PostgreSQL test database accessible via environment variables

## Install dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment variables

| Variable             | Default              | Required | Description                                          |
|----------------------|----------------------|----------|------------------------------------------------------|
| `FIREBASE_PROJECT_ID`| —                    | **Yes**  | Firebase project ID used to initialise the verifier |
| `API_BINARY`         | `api/mytube-api`     | No       | Path to pre-built Go binary                          |
| `DB_HOST`            | `localhost`          | No       | PostgreSQL host                                      |
| `DB_PORT`            | `5432`               | No       | PostgreSQL port                                      |
| `DB_USER`            | `testuser`           | No       | PostgreSQL user                                      |
| `DB_PASSWORD`        | `testpass`           | No       | PostgreSQL password                                  |
| `DB_NAME`            | `mytube_test`        | No       | PostgreSQL database name                             |

## Run

```bash
FIREBASE_PROJECT_ID=<project> \
  pytest testing/tests/MYTUBE-118/test_mytube_118.py -v
```

## Expected output (when passing)

```
PASSED test_mytube_118.py::TestProfileVideoListFiltering::test_status_code_is_200
PASSED test_mytube_118.py::TestProfileVideoListFiltering::test_response_body_contains_videos_array
PASSED test_mytube_118.py::TestProfileVideoListFiltering::test_ready_video_is_present
PASSED test_mytube_118.py::TestProfileVideoListFiltering::test_processing_video_is_excluded
PASSED test_mytube_118.py::TestProfileVideoListFiltering::test_videos_have_required_fields
```

## Skip behaviour

When `FIREBASE_PROJECT_ID` is not set the entire test module is skipped with an
informational message.
