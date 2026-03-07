# MYTUBE-305 — User profile loading failure — 'Could not load profile' message is displayed and session is cleared

## What this test verifies

Confirms that when the user profile API returns a 500 Internal Server Error (simulating a
Firestore "Permission Denied" or server failure), the application:

- Displays the exact error message: _"Could not load profile. Please try again later."_
- Does **not** render the username `<h1>` heading, avatar, or video grid.
- Clears `sessionStorage.__spa_username` after the React component mounts (even when the API
  call fails).
- Produces no uncaught JavaScript errors.

Route interception is registered via Playwright's `page.route()` **before** navigation so that
the very first profile fetch is intercepted. All DOM/state assertions are performed through the
`UserProfilePage` page object.

## Prerequisites

| Requirement | Details |
|---|---|
| Python | 3.10+ |
| Playwright | `playwright` pip package with Chromium browser installed |
| Node / npm | Not required (app is pre-deployed to GitHub Pages) |

## Install dependencies

```bash
pip install -r testing/requirements.txt
playwright install chromium
```

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-305/test_mytube_305.py -v
```

Override environment variables as needed:

```bash
APP_URL=https://ai-teammate.github.io/mytube \
  FIREBASE_TEST_EMAIL=ci-test@mytube.test \
  pytest testing/tests/MYTUBE-305/test_mytube_305.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-305/test_mytube_305.py::TestProfileLoadingFailure::test_error_message_is_displayed PASSED
testing/tests/MYTUBE-305/test_mytube_305.py::TestProfileLoadingFailure::test_username_heading_not_rendered PASSED
testing/tests/MYTUBE-305/test_mytube_305.py::TestProfileLoadingFailure::test_avatar_not_rendered PASSED
testing/tests/MYTUBE-305/test_mytube_305.py::TestProfileLoadingFailure::test_video_grid_not_rendered PASSED
testing/tests/MYTUBE-305/test_mytube_305.py::TestProfileLoadingFailure::test_session_storage_cleared PASSED
testing/tests/MYTUBE-305/test_mytube_305.py::TestProfileLoadingFailure::test_no_uncaught_js_errors PASSED
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web application |
| `FIREBASE_TEST_EMAIL` | No | `ci-test@mytube.test` | Used to derive the CI test username (prefix before `@`) |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Run browser headless (`true`/`false`) |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in milliseconds for debugging |

## Notes

The test uses a module-scoped browser fixture and a single browser context per test run to
minimise overhead. All DOM assertions go through `UserProfilePage` (Page Object Model) — the raw
Playwright `Page` is never accessed directly from the test methods.
