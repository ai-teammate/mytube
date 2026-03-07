# MYTUBE-199 — Retrieve video rating metadata

Automated test for: **Retrieve video rating metadata — average, count, and personal rating returned**

## What is tested

- `GET /api/videos/:id/rating` returns `average`, `count`, and `my_rating`.
- For an **authenticated user** (valid Firebase Bearer token): `my_rating` reflects the user's previously submitted rating.
- For an **unauthenticated guest** (no token): `my_rating` is `null`.

## Dependencies

- Go API binary (built automatically if absent)
- PostgreSQL test database
- `FIREBASE_TEST_TOKEN` — required for the authenticated path; generated at CI runtime

## Install dependencies

```bash
pip install pytest psycopg2-binary
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_USER` | `testuser` | DB username |
| `DB_PASSWORD` | `testpass` | DB password |
| `DB_NAME` | `mytube_test` | DB name |
| `SSL_MODE` | `disable` | SSL mode |
| `FIREBASE_PROJECT_ID` | `ai-native-478811` | Firebase project for token verification |
| `FIREBASE_TEST_TOKEN` | _(none)_ | Firebase ID token for CI test user — authenticated tests skip if absent |
| `FIREBASE_TEST_UID` | `ci-test-user-001` | Firebase UID of the CI test user |
| `API_BINARY` | `api/mytube-api` | Path to pre-built Go binary |

## Run

```bash
cd /path/to/mytube
pytest testing/tests/MYTUBE-199/test_mytube_199.py -v
```

## Generate FIREBASE_TEST_TOKEN locally

```bash
RESP=$(curl -s -X POST \
  "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=$FIREBASE_API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$FIREBASE_TEST_EMAIL\",\"password\":\"$FIREBASE_TEST_PASSWORD\",\"returnSecureToken\":true}")
export FIREBASE_TEST_TOKEN=$(echo $RESP | jq -r .idToken)
```

## Expected output (passing)

```
testing/tests/MYTUBE-199/test_mytube_199.py::TestGuestRatingResponse::test_returns_200 PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestGuestRatingResponse::test_response_is_valid_json PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestGuestRatingResponse::test_response_has_required_fields PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestGuestRatingResponse::test_rating_count_is_correct PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestGuestRatingResponse::test_average_rating_is_correct PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestGuestRatingResponse::test_my_rating_is_null_for_guest PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestAuthenticatedRatingResponse::test_returns_200 PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestAuthenticatedRatingResponse::test_response_is_valid_json PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestAuthenticatedRatingResponse::test_rating_count_is_correct PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestAuthenticatedRatingResponse::test_average_rating_is_correct PASSED
testing/tests/MYTUBE-199/test_mytube_199.py::TestAuthenticatedRatingResponse::test_my_rating_matches_user_previous_rating PASSED
```
