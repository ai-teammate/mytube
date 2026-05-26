# MYTUBE-633 — Upload valid avatar image — URL updated and success message shown

## Objective

Verify that selecting a valid JPEG/PNG file and clicking "Upload" in the Account Settings
page correctly:

1. Disables the Upload button before a file is selected.
2. Enables the Upload button once a valid file is chosen.
3. Triggers a `POST /api/me/avatar` request with `multipart/form-data`.
4. On success, displays the "Avatar uploaded successfully." notification.
5. Populates the "Avatar URL" text field with the URL returned by the API.
6. Updates the avatar preview image to show the new URL.

## Test Type

`ui` — Playwright end-to-end browser test with route interception.

## Test Structure

Five focused test functions, each asserting a single observable state:

| Test | Assertion |
|------|-----------|
| `test_upload_button_disabled_before_file_selected` | Upload button is disabled on page load |
| `test_upload_button_enabled_after_file_selected` | Upload button becomes enabled after file chosen |
| `test_upload_shows_success_message` | Success message shown after clicking Upload |
| `test_avatar_url_field_populated_with_returned_url` | Avatar URL field populated with API-returned URL |
| `test_avatar_preview_visible_after_upload` | Avatar preview `<img>` src updated and container visible |

Route interception isolates the test from live Firebase and Google Cloud Storage:

- `GET /api/me` → stable empty-avatar profile
- `POST /api/me/avatar` → mocked 200 with `{ avatar_url: "https://cdn.test.example.com/..." }`
- CDN image URL → served as a valid 1×1 GIF (prevents `onError` in `AvatarPreview`)

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (`pip install playwright && playwright install chromium`)
- Valid Firebase test account credentials

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_URL` / `WEB_BASE_URL` | Yes | Base URL of the deployed web app (default: `https://ai-teammate.github.io/mytube`) |
| `FIREBASE_TEST_EMAIL` | Yes | Test user email address |
| `FIREBASE_TEST_PASSWORD` | Yes | Test user password |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless (default: `true`) |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms (default: `0`) |

## Running the Tests

```bash
# From the repo root:
pytest testing/tests/MYTUBE-633/test_mytube_633.py -v
```

## Expected Output

```
PASSED  test_upload_button_disabled_before_file_selected
PASSED  test_upload_button_enabled_after_file_selected
PASSED  test_upload_shows_success_message
PASSED  test_avatar_url_field_populated_with_returned_url
PASSED  test_avatar_preview_visible_after_upload
```

All 5 tests should pass in approximately 3 seconds when the app is reachable and
valid Firebase credentials are supplied.
