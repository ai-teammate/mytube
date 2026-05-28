# MYTUBE-654 — Remove avatar button visibility — button hidden when no avatar exists

## Objective

Verify that the "Remove avatar" button only appears when the user actually has an avatar
to remove (i.e. `avatarUrl` is non-empty), and is hidden when `avatarUrl` is empty.

## Test Steps

1. Clear the avatar (if one exists) so `avatarUrl` is empty.
2. Observe the interface — the "Remove avatar" button must **NOT** be visible.
3. Upload a new avatar / fill in a valid `avatarUrl`.
4. Observe the interface again — the "Remove avatar" button must be visible.

## Scenarios Covered

| # | Scenario | Description |
|---|----------|-------------|
| A | No avatar | `GET /api/me` mocked with `avatar_url: ""` — button must be absent/hidden. |
| B | Avatar present | `GET /api/me` mocked with a valid `avatar_url` — button must be visible. |
| C | Reactive toggle | Start with empty `avatarUrl` (button hidden), fill the Avatar URL input, confirm button appears without a page reload. |

## Expected Result

The "Remove avatar" button is hidden when `avatarUrl` is empty and becomes visible only
when a valid `avatarUrl` is present. The UI reacts immediately to input changes
(React `onChange → setForm → re-render` pipeline).

## Architecture

- `SettingsPage` (`testing/components/pages/settings_page/settings_page.py`) exposes
  `is_remove_avatar_button_visible()` and `is_remove_avatar_button_hidden()`.
- `GET /api/me` is mocked per scenario via Playwright's `page.route()` — no real network calls.
- `WebConfig` (`testing/core/config/web_config.py`) centralises all URLs and credentials.
- Module-scoped credential skip guard prevents misleading failures when secrets are absent.

## Environment Variables

| Variable               | Description                                                                  |
|------------------------|------------------------------------------------------------------------------|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app. Default: `https://ai-teammate.github.io/mytube` |
| `FIREBASE_TEST_EMAIL`  | Test user email (required — test skips when absent).                         |
| `FIREBASE_TEST_PASSWORD` | Test user password (required — test skips when absent).                    |
| `PLAYWRIGHT_HEADLESS`  | Run browser headless. Default: `true`.                                       |
| `PLAYWRIGHT_SLOW_MO`   | Slow-motion delay in ms for debugging. Default: `0`.                         |

## Running

```bash
# From the repository root:
pytest testing/tests/MYTUBE-654/test_mytube_654.py -v
```
