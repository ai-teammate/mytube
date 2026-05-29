# MYTUBE-652 — Click Remove avatar button: avatar removed and UI updated

## Objective

Verify that clicking the 'Remove avatar' button sends a DELETE request to the backend
and upon success clears `form.avatarUrl` so that the image preview disappears.

## Test Type

`web` — Playwright (Chromium headless) end-to-end UI test.

## Test Structure

Six ordered tests run in a single shared module-scoped browser session:

1. **test_precondition_existing_avatar_visible** — Settings page loads with the pre-existing
   avatar URL in the Avatar URL field and preview visible (precondition verification).
2. **test_remove_avatar_button_is_visible** — The 'Remove avatar' button is visible when an
   avatar is set.
3. **test_click_remove_avatar_sends_delete_request** — Clicking 'Remove avatar' dispatches a
   DELETE /api/me/avatar request (verified via route interceptor flag).
4. **test_avatar_url_input_cleared_after_remove** — After removal the Avatar URL input is empty.
5. **test_avatar_preview_disappears_after_remove** — The `<img>` inside AvatarPreview is gone.
6. **test_remove_avatar_button_disappears_after_remove** — The button itself disappears.

## Dependencies

- `playwright` — install with `pip install playwright && playwright install chromium`

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the web app |
| `FIREBASE_TEST_EMAIL` | **Yes** | — | Email of the test Firebase user |
| `FIREBASE_TEST_PASSWORD` | **Yes** | — | Password for the test Firebase user |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Set to `false` for a headed browser |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms |

## How to Install Dependencies

```bash
pip install -r testing/requirements.txt
playwright install chromium
```

## Run Command

```bash
pytest testing/tests/MYTUBE-652/test_mytube_652.py -v
```

## Expected Output (Pass)

```
testing/tests/MYTUBE-652/test_mytube_652.py::TestRemoveAvatarButton::test_precondition_existing_avatar_visible PASSED
testing/tests/MYTUBE-652/test_mytube_652.py::TestRemoveAvatarButton::test_remove_avatar_button_is_visible PASSED
testing/tests/MYTUBE-652/test_mytube_652.py::TestRemoveAvatarButton::test_click_remove_avatar_sends_delete_request PASSED
testing/tests/MYTUBE-652/test_mytube_652.py::TestRemoveAvatarButton::test_avatar_url_input_cleared_after_remove PASSED
testing/tests/MYTUBE-652/test_mytube_652.py::TestRemoveAvatarButton::test_avatar_preview_disappears_after_remove PASSED
testing/tests/MYTUBE-652/test_mytube_652.py::TestRemoveAvatarButton::test_remove_avatar_button_disappears_after_remove PASSED
6 passed in Xs
```
