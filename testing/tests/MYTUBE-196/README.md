# MYTUBE-196: Access dashboard while unauthenticated — user redirected to login

## What this test verifies

When an unauthenticated user navigates directly to `/dashboard`, the application:
1. Does **not** allow access to the dashboard.
2. Automatically redirects to `/login`.
3. Renders the email/password sign-in form on the redirected page.

## Dependencies

| Dependency | Notes |
|---|---|
| `playwright` | `pip install playwright && playwright install chromium` |
| `pytest` | `pip install pytest` |
| Deployed web app | Must be running and accessible at `WEB_BASE_URL` |

No Firebase credentials are required — this test verifies the unauthenticated path only.

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `WEB_BASE_URL` / `APP_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the web app |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Set to `false` to watch the browser |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms for debugging |

## How to run

```bash
# From the repository root
pip install pytest playwright
playwright install chromium

# Run the test
pytest testing/tests/MYTUBE-196/test_mytube_196.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-196/test_mytube_196.py::TestUnauthenticatedDashboardRedirect::test_redirected_away_from_dashboard PASSED
testing/tests/MYTUBE-196/test_mytube_196.py::TestUnauthenticatedDashboardRedirect::test_redirected_to_login_url PASSED
testing/tests/MYTUBE-196/test_mytube_196.py::TestUnauthenticatedDashboardRedirect::test_login_form_is_visible PASSED
```
