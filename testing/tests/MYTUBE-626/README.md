# MYTUBE-626: Upload unsupported file type — API returns 400 Bad Request

## Objective

Verify that `POST /api/me/avatar` rejects file types other than `image/jpeg`
and `image/png` with HTTP 400 Bad Request and an appropriate error message
indicating that the MIME type is not supported.

## Preconditions

- User is authenticated (valid Firebase ID token required).
- Go API binary is available (built from `api/` or supplied via `API_BINARY`).
- Database is accessible with the configured credentials.

## Steps

1. Start the Go API server locally with valid DB and Firebase credentials.
2. Seed the test user so authentication succeeds.
3. Send `POST /api/me/avatar` with a multipart form containing a file whose
   `Content-Type` is `image/gif` (an unsupported type).
4. Assert the response is HTTP 400.
5. Assert the JSON error body contains a message about the unsupported type.
6. Repeat with `application/pdf` to confirm the rule applies broadly.

## Expected Result

- HTTP 400 Bad Request for both `image/gif` and `application/pdf`.
- JSON body: `{"error": "unsupported file type; accepted types: jpeg, png"}`

## Architecture Notes

- `ApiProcessService` starts/stops the Go API binary; all HTTP calls go through it.
- Multipart form data is encoded manually using raw bytes and uuid boundaries.
- Direct psycopg2 SQL is used for idempotent test-user seeding.
- No hardcoded waits; `ApiProcessService.wait_for_ready()` polls `/health`.

## Environment Variables

| Variable | Description |
|---|---|
| `FIREBASE_TEST_TOKEN` | Firebase ID token for the test user (required) |
| `FIREBASE_PROJECT_ID` | Firebase project ID for the verifier (required) |
| `FIREBASE_TEST_UID` | `firebase_uid` of the test user (default: `ci-test-user-001`) |
| `API_BINARY` | Path to pre-built Go binary (default: `<repo_root>/api/mytube-api`) |
| `DB_HOST` | Database host |
| `DB_PORT` | Database port |
| `DB_USER` | Database user |
| `DB_PASSWORD` | Database password |
| `DB_NAME` | Database name |
| `SSL_MODE` | SSL mode for DB connection |

## Running the Tests

```bash
pytest testing/tests/MYTUBE-626/test_mytube_626.py -v
```
