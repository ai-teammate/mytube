# MYTUBE-610 — Enter valid avatar URL: live image preview is displayed

## Objective

Verify that a live preview of the avatar image appears when a valid URL is entered
in the Avatar URL field on the Account Settings page (`/settings`).

## Dependencies

```
pip install -r testing/requirements.txt
playwright install chromium
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FIREBASE_TEST_EMAIL` | ✅ | — | CI test user email |
| `FIREBASE_TEST_PASSWORD` | ✅ | — | CI test user password |
| `APP_URL` / `WEB_BASE_URL` | ❌ | `https://ai-teammate.github.io/mytube` | Frontend URL |
| `PLAYWRIGHT_HEADLESS` | ❌ | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | ❌ | `0` | Slow-motion delay (ms) |

## Run the test

```bash
pytest testing/tests/MYTUBE-610/test_mytube_610.py -v
```

## Expected output when passing

```
PASSED testing/tests/MYTUBE-610/test_mytube_610.py::test_avatar_url_shows_live_preview
```
