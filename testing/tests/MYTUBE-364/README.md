# MYTUBE-364: Fill form fields in upload and edit pages — input text is visible

## Objective

Verify that text entered into the multi-field upload form (Title and Description) is visible
to the user as it is typed, and that both fields retain their values simultaneously.

## Preconditions

- An authenticated Firebase test user is available (credentials supplied via environment variables).
- The deployed web application is accessible at the URL defined by `WEB_BASE_URL` / `APP_URL`.
- Playwright with Chromium is installed in the test environment.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `FIREBASE_TEST_EMAIL` | ✅ Yes | Email of the registered Firebase test user. |
| `FIREBASE_TEST_PASSWORD` | ✅ Yes | Password for the Firebase test user. |
| `WEB_BASE_URL` / `APP_URL` | No | Base URL of the deployed web app. Default: `https://ai-teammate.github.io/mytube`. |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

1. **Authenticate** — Log in with the Firebase test user via `LoginPage` and wait until
   the `/login` route is no longer active.
2. **Navigate to `/upload`** — Use `UploadPage.navigate()` to open the upload form.
3. **Locate the Title field** — Find `input[id="title"]` and wait for it to be visible.
4. **Fill the Title field** — Type `"My Test Video Title"` via `UploadPage.fill_title()`.
5. **Locate the Description field** — Find `textarea[id="description"]` and wait for it to be visible.
6. **Fill the Description field** — Type a multi-line description via `UploadPage.fill_description()`.
7. **Assert simultaneous retention** — Verify both fields are visible, enabled, and hold their
   respective values at the same time.

## Expected Result

- The Title input (`input[id="title"]`) is visible, enabled, and retains the typed value.
- The Description textarea (`textarea[id="description"]`) is visible, enabled, and retains
  the full multi-line typed value.
- Filling one field does not clear or overwrite the other — both fields hold their values simultaneously.

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_364.py` | Playwright test implementation (3 test cases) |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
