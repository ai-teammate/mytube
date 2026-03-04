# MYTUBE-198: Submit rating without authentication — 401 Unauthorized

## Purpose

Verifies that `POST /api/videos/:id/rating` is protected by the authentication
middleware. A request sent without an `Authorization` header must be rejected
with HTTP 401 before the handler body executes.

## How it works

The test starts the `testing/testserver/` Go binary, which re-implements the
identical `requireAuth` middleware logic as production without requiring Firebase
credentials or a database. A `POST /api/videos/<uuid>/rating` request is sent
with no `Authorization` header and the response is asserted to be HTTP 401.

## Dependencies

No external credentials required. Requires Go to be installed (to build the
testserver if the binary is not already present).

## Install dependencies

```bash
pip install pytest
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEST_SERVER_BINARY` | `testing/testserver/testserver` | Path to the pre-built testserver binary |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-198/test_mytube_198.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-198/test_mytube_198.py::TestSubmitRatingUnauthenticated::test_status_code_is_401 PASSED
testing/tests/MYTUBE-198/test_mytube_198.py::TestSubmitRatingUnauthenticated::test_response_body_is_valid_json PASSED
testing/tests/MYTUBE-198/test_mytube_198.py::TestSubmitRatingUnauthenticated::test_response_contains_error_key PASSED
testing/tests/MYTUBE-198/test_mytube_198.py::TestSubmitRatingUnauthenticated::test_error_message_is_non_empty PASSED
```
