# MYTUBE-120: Public profile accessibility

Verifies that `GET /api/users/:username` is accessible without an Authorization header (no Firebase Auth token required), returns HTTP 200, and delivers the expected profile structure.

## Prerequisites

- Go toolchain (to build the API binary, or pre-built at `api/mytube-api`)
- Python 3.11+
- PostgreSQL 15+ running and accessible

## Install dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `testuser` | PostgreSQL user |
| `DB_PASSWORD` | `testpass` | PostgreSQL password |
| `DB_NAME` | `mytube_test` | PostgreSQL database name |
| `SSL_MODE` | `disable` | PostgreSQL SSL mode |
| `API_BINARY` | `api/mytube-api` | Path to the pre-built Go binary |
| `FIREBASE_PROJECT_ID` | `test-project` | Firebase project ID (needed for server startup) |

## Run the test

```bash
python3 -m pytest testing/tests/MYTUBE-120/test_mytube_120.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-120/test_mytube_120.py::TestPublicProfileAccessibility::test_status_code_is_200 PASSED
testing/tests/MYTUBE-120/test_mytube_120.py::TestPublicProfileAccessibility::test_response_body_is_valid_json PASSED
testing/tests/MYTUBE-120/test_mytube_120.py::TestPublicProfileAccessibility::test_response_contains_username_field PASSED
testing/tests/MYTUBE-120/test_mytube_120.py::TestPublicProfileAccessibility::test_response_username_matches_requested_username PASSED
testing/tests/MYTUBE-120/test_mytube_120.py::TestPublicProfileAccessibility::test_response_contains_videos_field PASSED
testing/tests/MYTUBE-120/test_mytube_120.py::TestPublicProfileAccessibility::test_videos_field_is_a_list PASSED
testing/tests/MYTUBE-120/test_mytube_120.py::TestPublicProfileAccessibility::test_no_authorization_header_was_sent PASSED
7 passed
```
