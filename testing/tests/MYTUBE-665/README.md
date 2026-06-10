# MYTUBE-665 — Navigation from other pages to Home: avatar remains applied

## Objective

Verify that the avatar component in `SiteHeader` does not lose its state or fail
to load when the user navigates **back to the Home page** from another section of
the application (e.g. Account Settings).

Related bug: [MYTUBE-663 — Avatar is not applied on the home page](Done — fix deployed).

## Test Type

`web` — end-to-end Playwright test running against the deployed web app.

## Tests

| # | Test | Description |
|---|------|-------------|
| 1 | `test_avatar_remains_visible_after_navigating_to_home` | Login → Settings → click logo → Home; assert avatar visible at every step. |
| 2 | `test_avatar_visible_after_navigating_from_home_logo_click` | Login → Home → Settings → click logo → Home (round-trip); assert avatar visible throughout. |

## How It Works

- Firebase authentication is performed with CI test credentials.
- `GET /api/me` is intercepted and mocked to return a test profile with an empty
  `avatar_url`, which causes `SiteHeader` to render the placeholder
  `<span class="rounded-full">` (initials circle).
- `SiteHeader.avatar_wait()` waits for that span before each assertion.
- Both tests use `try/finally` to ensure the browser context is closed on failure.
- No `time.sleep` calls — all waits use explicit Playwright `wait_for_url` /
  `wait_for_selector` mechanisms.

## Preconditions

- The deployed web app at `APP_URL` must be reachable.
- Valid Firebase test credentials must be available via environment variables (see
  below).
- Python 3.10+, `pytest`, and `playwright` (with Chromium) must be installed.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app. |
| `FIREBASE_TEST_EMAIL` | **Yes** | — | Test user e-mail address. Tests are skipped when absent. |
| `FIREBASE_TEST_PASSWORD` | **Yes** | — | Test user password. Tests are skipped when absent. |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Set to `false` to open a visible browser window. |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms (useful for debugging). |

## Running the Tests Locally

```bash
# Install dependencies (from repo root):
pip install pytest playwright
playwright install chromium

# Run with credentials:
FIREBASE_TEST_EMAIL=user@example.com \
FIREBASE_TEST_PASSWORD=secret \
pytest testing/tests/MYTUBE-665/test_mytube_665.py -v
```

## Expected Output

```
PASSED  TestAvatarPersistsOnHomeNavigation::test_avatar_remains_visible_after_navigating_to_home
PASSED  TestAvatarPersistsOnHomeNavigation::test_avatar_visible_after_navigating_from_home_logo_click
```

When `FIREBASE_TEST_EMAIL` or `FIREBASE_TEST_PASSWORD` is not set, both tests
are skipped with an explanatory message.
