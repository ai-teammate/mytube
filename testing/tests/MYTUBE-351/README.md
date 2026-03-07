# MYTUBE-351: Firebase auth initialization error — error state displayed

## Objective

Verify that the application displays a visible error state when the Firebase SDK fails to resolve
authentication status (e.g. due to a network outage blocking Firebase auth domains).

## Preconditions

- The deployed web application is accessible at the URL defined by `WEB_BASE_URL`.
- Playwright with Chromium is installed in the test environment.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEB_BASE_URL` | ✅ Yes | Base URL of the deployed web app (e.g. `https://ai-teammate.github.io/mytube`). |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

1. **Block Firebase auth domains** — Playwright's `context.route()` intercepts and aborts all
   requests to `identitytoolkit.googleapis.com`, `securetoken.googleapis.com`,
   `*.firebaseapp.com`, and `firebase.googleapis.com`, simulating an SDK initialization failure.
2. **Navigate to the home page** — `GET /` is loaded in the blocked context.
3. **Verify loading state resolves** — The "Loading…" spinner must disappear within 15 seconds;
   the app must not remain permanently in a loading state.
4. **Verify auth error message is displayed** — At least one visible element with non-empty text
   matching auth-unavailability keywords must be present (e.g. `role="alert"` with text
   "Authentication services are currently unavailable").

## Expected Result

The application renders a clear, user-visible error message indicating that authentication
services are unavailable. It must **not** silently degrade to an unauthenticated session
(showing only a "Sign in" link without any explanation).

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_351.py` | Playwright test implementation |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
