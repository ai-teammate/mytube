# MYTUBE-463 — Auth switch link: interaction and color match branding

## Objective

Verify that the auth-switch links on both the Login and Register pages have the
correct brand color (`--accent-logo`) and display underline decoration on hover.

## Test Type

`web` — Playwright (Chromium) end-to-end UI test.

## Test Structure

### Login page — "Create one" link (→ /register)

1. **Color check** — navigates to `/login/`, waits for the switch link, then
   reads its `computed color` via the browser and compares it against the
   live-resolved value of `--accent-logo`.
2. **Hover check** — hovers the switch link and asserts that `textDecorationLine`
   is `underline` after a short CSS-transition settle period.

### Register page — "Sign in" link (→ /login)

Same two checks mirrored for the `/register/` page.

## Architecture

- Selectors and CSS inspection helpers are encapsulated in `LoginPage` and
  `RegisterPage` page objects (`testing/components/pages/`).
- `WebConfig` centralises all URL and environment variable access.
- Playwright sync API with `pytest` module-scoped browser fixture.
- No hardcoded URLs or credentials.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (with Chromium browser installed)

Install dependencies:

```bash
pip install pytest playwright
playwright install chromium
```

## Environment Variables

| Variable            | Required | Default                                   | Description                          |
|---------------------|----------|-------------------------------------------|--------------------------------------|
| `APP_URL`           | No       | `https://ai-teammate.github.io/mytube`    | Base URL of the deployed web app.    |
| `WEB_BASE_URL`      | No       | `https://ai-teammate.github.io/mytube`    | Alias for `APP_URL`.                 |
| `PLAYWRIGHT_HEADLESS` | No     | `true`                                    | Run browser headless.                |
| `PLAYWRIGHT_SLOW_MO`  | No     | `0`                                       | Slow-motion delay in ms.             |

## Running the Tests

```bash
# From repository root:
pytest testing/tests/MYTUBE-463/test_mytube_463.py -v

# Against a custom deployment:
APP_URL=http://localhost:3000 pytest testing/tests/MYTUBE-463/test_mytube_463.py -v
```

## Expected Output

```
PASSED  TestAuthSwitchLink::test_login_switch_link_color
PASSED  TestAuthSwitchLink::test_login_switch_link_hover_underline
PASSED  TestAuthSwitchLink::test_register_switch_link_color
PASSED  TestAuthSwitchLink::test_register_switch_link_hover_underline
```
