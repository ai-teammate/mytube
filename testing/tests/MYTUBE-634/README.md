# MYTUBE-634 — Avatar upload in progress: button disabled and shows spinner

## Objective

Verify that the UI provides visual feedback and prevents double-submission during
the avatar upload process. When the user clicks "Upload", the button must immediately
become disabled and display "Uploading…" until the request completes.

## Test Strategy

Three complementary layers:

### 1. Source Analysis (always runs)

Inspects `web/src/app/settings/page.tsx` statically to confirm:

- `setUploading(true)` is called before the `fetch()` in `handleAvatarUpload`
- `setUploading(false)` is called in the `finally` block (unconditional reset)
- The button carries `disabled={uploading || !uploadFile}`
- The button label uses `{uploading ? "Uploading…" : "Upload"}` ternary

### 2. Playwright Fixture Mode (always runs)

Spins up a local HTTP server that serves a self-contained HTML page mirroring
the Upload button behaviour from `settings/page.tsx` with a simulated 2-second
network delay. No authentication or deployed app required.

Asserts:
1. Button is initially disabled (no file selected)
2. Button becomes enabled after attaching a valid PNG file
3. Button is `disabled` immediately upon click (while upload is in flight)
4. Button label shows `"Uploading…"` while in flight
5. Button is re-enabled with label `"Upload"` after the simulated upload completes

### 3. Live Mode (requires credentials)

Against the deployed app at `https://ai-teammate.github.io/mytube`.

- Logs in with CI credentials and navigates to `/settings`
- Intercepts `POST /api/me/avatar` via Playwright route intercept with a 3-second
  delay to make the in-flight state reliably observable
- Uses `SettingsPage` page-object methods for all file selection, button interaction,
  and state assertions

Asserts:
1. Button becomes `disabled` immediately after clicking Upload
2. Button shows `"Uploading…"` while the intercepted request is pending

## Environment Variables

| Variable                | Description                                      | Default                              |
|-------------------------|--------------------------------------------------|--------------------------------------|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app              | `https://ai-teammate.github.io/mytube` |
| `FIREBASE_TEST_EMAIL`   | CI test user email (required for live mode)      | —                                    |
| `FIREBASE_TEST_PASSWORD`| CI test user password (required for live mode)   | —                                    |
| `PLAYWRIGHT_HEADLESS`   | Run browser headless                             | `true`                               |
| `PLAYWRIGHT_SLOW_MO`    | Slow-motion delay in milliseconds                | `0`                                  |

## How to Run

From the repository root:

```bash
# All tests (source analysis + fixture + live if credentials present)
pytest testing/tests/MYTUBE-634/test_mytube_634.py -v

# Source analysis and fixture only (no credentials needed)
pytest testing/tests/MYTUBE-634/test_mytube_634.py -v -k "not Live"

# Live mode only
FIREBASE_TEST_EMAIL=... FIREBASE_TEST_PASSWORD=... \
  pytest testing/tests/MYTUBE-634/test_mytube_634.py -v -k "Live"
```

## Components Used

- `testing/components/pages/settings_page/settings_page.py` — `SettingsPage` page object
  (avatar upload methods: `select_avatar_file`, `click_upload_button`,
  `wait_for_upload_button_enabled`, `wait_for_upload_in_flight`,
  `is_upload_button_disabled`, `wait_for_uploading_text`, `is_uploading_text_visible`)
- `testing/components/pages/login_page/login_page.py` — `LoginPage` page object
- `testing/core/config/web_config.py` — `WebConfig` (base URL, credentials, headless flag)
