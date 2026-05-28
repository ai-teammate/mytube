# MYTUBE-656 — Delete avatar API failure: error displayed, avatar remains

## Objective

Verify that the UI handles backend errors gracefully during avatar removal.  
When `DELETE /api/me/avatar` returns a 500 error, an inline error message must
appear and the avatar state/preview must remain unchanged.

## Dependencies

```bash
pip install pytest playwright psycopg2-binary
playwright install chromium
```

Or from repo root:

```bash
pip install -r testing/requirements.txt
playwright install chromium
```

## Required environment variables

| Variable | Description |
|---|---|
| `FIREBASE_TEST_EMAIL` | Email of the test Firebase user |
| `FIREBASE_TEST_PASSWORD` | Password for the test Firebase user |
| `APP_URL` / `WEB_BASE_URL` | Base URL (default: `https://ai-teammate.github.io/mytube`) |
| `PLAYWRIGHT_HEADLESS` | `true` (default) or `false` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms (default: `0`) |

## Run command

```bash
pytest testing/tests/MYTUBE-656/test_mytube_656.py -v
```

## Expected output (passing)

```
PASSED testing/tests/MYTUBE-656/test_mytube_656.py::TestDeleteAvatarApiFailure::test_error_message_displayed_on_500
PASSED testing/tests/MYTUBE-656/test_mytube_656.py::TestDeleteAvatarApiFailure::test_avatar_state_unchanged_on_500
2 passed
```

If credentials are missing, all tests are skipped with a descriptive message.
