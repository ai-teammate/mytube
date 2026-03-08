# MYTUBE-351: Firebase auth initialization error — error state displayed

## Objective

Verify that the application displays a visible error state when the Firebase SDK fails to resolve
authentication status (e.g. due to a Firebase initialization failure).

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

1. **Inject Firebase failure simulation** — `context.add_init_script` injects a script before any
   page scripts run. The script intercepts `Object.defineProperty` to detect when webpack module
   9997 exports `hg` (`onAuthStateChanged`) and replaces the getter with a factory that returns a
   fake `onAuthStateChanged` that always calls the error callback after 100 ms, directly triggering
   `authError = true` in `AuthContext`.
2. **Navigate to the home page** — `GET /` is loaded in the intercepted context.
3. **Verify loading state resolves** — The "Loading…" spinner must disappear within 15 seconds;
   the app must not remain permanently in a loading state.
4. **Verify auth error message is displayed** — At least one visible element with non-empty text
   matching auth-unavailability keywords must be present (e.g. `role="alert"` with text
   "Authentication services are currently unavailable").

## Expected Result

The application renders a clear, user-visible error message indicating that authentication
services are unavailable. It must **not** silently degrade to an unauthenticated session
(showing only a "Sign in" link without any explanation).

## Why not network blocking?

Previous runs used `context.route()` to abort requests to Firebase auth domains. That approach
failed three times because for unauthenticated users with no cached session the Firebase SDK
resolves `onAuthStateChanged` with `null` **synchronously from `localStorage`/IndexedDB** without
making any network calls, so the error callback was never triggered and `authError` remained
`false`. The webpack module interception approach correctly triggers the auth error path.

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_351.py` | Playwright test implementation |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
