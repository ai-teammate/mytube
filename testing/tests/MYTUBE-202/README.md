# MYTUBE-202: GET /api/videos/:id/comments — descending order, 100 item cap

## Purpose

Verifies that `GET /api/videos/:id/comments` returns a flat list of comments ordered
by newest first and capped at exactly 100 items, with author details on every item.

## Prerequisites

- Python 3.11+
- Go toolchain (for building the API binary)
- PostgreSQL test database accessible via environment variables

## Install dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment variables

| Variable             | Default              | Required | Description                                           |
|----------------------|----------------------|----------|-------------------------------------------------------|
| `FIREBASE_PROJECT_ID`| —                    | **Yes**  | Firebase project ID used to initialise the API verifier |
| `API_BINARY`         | `api/mytube-api`     | No       | Path to pre-built Go binary                           |
| `DB_HOST`            | `localhost`          | No       | PostgreSQL host                                       |
| `DB_PORT`            | `5432`               | No       | PostgreSQL port                                       |
| `DB_USER`            | `testuser`           | No       | PostgreSQL user                                       |
| `DB_PASSWORD`        | `testpass`           | No       | PostgreSQL password                                   |
| `DB_NAME`            | `mytube_test`        | No       | PostgreSQL database name                              |

## Run

```bash
FIREBASE_PROJECT_ID=ai-native-478811 \
  pytest testing/tests/MYTUBE-202/test_mytube_202.py -v
```

## Expected output

```
PASSED test_mytube_202.py::TestGetCommentsEndpoint::test_status_code_is_200
PASSED test_mytube_202.py::TestGetCommentsEndpoint::test_returns_exactly_100_items
PASSED test_mytube_202.py::TestGetCommentsEndpoint::test_items_ordered_newest_first
PASSED test_mytube_202.py::TestGetCommentsEndpoint::test_each_item_has_author_username
PASSED test_mytube_202.py::TestGetCommentsEndpoint::test_each_item_has_author_avatar_url_key
```

## Skip behaviour

When `FIREBASE_PROJECT_ID` is not set the entire test module is skipped with an
informational message (the API server cannot initialise the Firebase verifier without it).
