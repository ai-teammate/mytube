# MYTUBE-229: Update playlist title as non-owner — 403 Forbidden returned

Verifies that `PUT /api/playlists/:id` returns HTTP 403 Forbidden when the
authenticated user is not the playlist owner, and that the playlist title
remains unchanged.

## Test layers

| Layer | Requires | What runs |
|-------|----------|-----------|
| A — Go unit | nothing | `TestPlaylistByIDHandler_PUT_Forbidden_Returns403` in `api/internal/handler/` |
| B — HTTP integration | `FIREBASE_TEST_TOKEN` + DB + API binary | Full end-to-end against a local API server |

## Install dependencies

```bash
pip install psycopg2-binary pytest
```

## Environment variables

| Variable | Required for | Description |
|----------|-------------|-------------|
| `FIREBASE_TEST_TOKEN` | Layer B | Valid Firebase ID token for CI test user (User B) |
| `FIREBASE_TEST_UID` | Layer B | Firebase UID of the CI test user (default: `ci-test-user-001`) |
| `FIREBASE_PROJECT_ID` | Layer B | Firebase project (default: `ai-native-478811`) |
| `DB_HOST` | Layer B | PostgreSQL host |
| `DB_PORT` | Layer B | PostgreSQL port (default: `5432`) |
| `DB_USER` | Layer B | PostgreSQL user |
| `DB_PASSWORD` | Layer B | PostgreSQL password |
| `DB_NAME` | Layer B | PostgreSQL database name |
| `API_BINARY` | Layer B | Path to compiled Go binary (default: `<repo>/api/mytube-api`) |

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-229/test_mytube_229.py -v
```

## Expected output (when all credentials are present)

```
testing/tests/MYTUBE-229/test_mytube_229.py::TestPlaylistOwnershipGoUnit::test_put_forbidden_returns_403 PASSED
testing/tests/MYTUBE-229/test_mytube_229.py::TestUpdatePlaylistAsNonOwner::test_non_owner_put_returns_403 PASSED
testing/tests/MYTUBE-229/test_mytube_229.py::TestUpdatePlaylistAsNonOwner::test_response_body_is_json PASSED
testing/tests/MYTUBE-229/test_mytube_229.py::TestUpdatePlaylistAsNonOwner::test_response_contains_error_message PASSED
testing/tests/MYTUBE-229/test_mytube_229.py::TestUpdatePlaylistAsNonOwner::test_playlist_title_unchanged_after_403 PASSED
```

Layer A always runs; Layer B is skipped gracefully when credentials are absent.
