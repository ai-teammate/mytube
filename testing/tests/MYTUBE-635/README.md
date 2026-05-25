# MYTUBE-635 — Client-side validation: unsupported file type — immediate error displayed

## Objective

Verify that the Account Settings page prevents selecting or uploading invalid
avatar file formats **without** making a network request.  When the user selects
a file whose MIME type is not `image/jpeg` or `image/png`, an error message must
appear immediately (on selection, before any Upload button click) and no POST
request must be dispatched to `/api/me/avatar`.

---

## Test approach

### Part A — Static analysis (always runs)

Reads `web/src/app/settings/page.tsx` and asserts:

1. The file exists at the expected path.
2. The `ALLOWED_AVATAR_TYPES` constant lists exactly `image/jpeg` and `image/png`.
3. `handleFileChange` contains the guard `ALLOWED_AVATAR_TYPES.includes(file.type)`.
4. The exact error message text `"Only JPEG and PNG files are allowed."` is present.
5. The error paragraph has `role="alert"` for accessibility.
6. No `fetch(` call appears inside `handleFileChange` — confirming no network
   request is issued during type validation.

Part A runs unconditionally (no credentials required).

### Part B — Live Playwright UI tests (require credentials)

Launches a Chromium browser, logs in via `LoginPage`, navigates to `/settings`
via `SettingsPage`, then:

1. Selects a `.gif` file (`image/gif`) and asserts:
   - The `role="alert"` error appears immediately with the correct text.
   - No POST to `/api/me/avatar` was dispatched.
2. Selects a `.pdf` file (`application/pdf`) and asserts the same two conditions.
3. Re-navigates to a fresh settings page, confirms no alert before selection,
   selects a `.bmp` file, and asserts the error appears *before* the Upload
   button is clicked.
4. Asserts the Upload button remains disabled after an invalid file is selected.

Part B is skipped when `FIREBASE_TEST_EMAIL` or `FIREBASE_TEST_PASSWORD` is absent.

---

## Preconditions

- A deployed instance of the MyTube web application is accessible at `APP_URL`.
- A valid Firebase test account exists (email + password).

---

## Environment variables

| Variable | Description | Default |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app | `https://ai-teammate.github.io/mytube` |
| `FIREBASE_TEST_EMAIL` | Email of the Firebase test user | *(required for Part B)* |
| `FIREBASE_TEST_PASSWORD` | Password of the Firebase test user | *(required for Part B)* |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

---

## Files

| File | Purpose |
|---|---|
| `test_mytube_635.py` | Test implementation (Part A + Part B) |
| `config.yaml` | Test configuration (framework: playwright, platform: chromium) |
| `README.md` | This file |

---

## Architecture

- **`WebConfig`** (`testing/core/config/web_config.py`) — centralises env var access.
- **`LoginPage`** (`testing/components/pages/login_page/`) — handles authentication.
- **`SettingsPage`** (`testing/components/pages/settings_page/`) — encapsulates all
  file input interactions (`set_avatar_file`, `get_upload_error_text`,
  `is_upload_error_visible`, `is_upload_button_disabled`).
- No hardcoded URLs, credentials, or selectors in test code.
