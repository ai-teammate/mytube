# MYTUBE-368 — Auth Failure Error Message on Protected Route

Verifies that when Firebase authentication fails, navigating to a protected route
(`/upload`) displays an error message ("Authentication services are currently
unavailable") in the SiteHeader rather than silently redirecting to the home page
or rendering a "Sign in" link.

## How it works

Because the Firebase JS SDK (v9 modular) does **not** invoke `onAuthStateChanged`'s
error callback when network-level requests are blocked (it silently returns
`user = null` instead), the test simulates auth failure by injecting `authError = true`
directly into the React `AuthContext` state using Playwright's `page.evaluate()` and
React's internal fiber hook-dispatch mechanism.

1. A `FIREBASE_DELAY_INIT_SCRIPT` (borrowed from `RequireAuthComponent`) delays
   Firebase's IndexedDB resolution, keeping the app in `loading = true` while the
   injection window is open.
2. The test navigates to `/upload`, waits for the loading spinner (confirming
   React hydration), then dispatches `authError = true` onto the `authError`
   `useState` hook inside `AuthProvider`.
3. After Firebase resolves normally (`user = null`, `loading = false`), the final
   AuthContext state is `{user: null, loading: false, authError: true}`.
4. `RequireAuth` redirects to `/login` (expected — user is unauthenticated).
5. On `/login`, `SiteHeader` renders `<span role="alert">Authentication services
   are currently unavailable</span>` instead of the "Sign in" link.

## Dependencies

```
playwright >= 1.40.0
pytest >= 7.0.0
```

Install with:
```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the deployed app |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay (ms) for debugging |

## Run the test

From the repository root:

```bash
cd /path/to/repo
pip install playwright pytest
playwright install chromium

# Run against the deployed GitHub Pages app (default):
pytest testing/tests/MYTUBE-368/test_mytube_368.py -v

# Run against a local dev server:
APP_URL=http://localhost:3000 pytest testing/tests/MYTUBE-368/test_mytube_368.py -v

# Run with visible browser for debugging:
PLAYWRIGHT_HEADLESS=false pytest testing/tests/MYTUBE-368/test_mytube_368.py -v -s
```

## Expected output (all passing)

```
PASSED  TestProtectedRouteAuthFailureError::test_loading_state_resolves_after_firebase_failure
PASSED  TestProtectedRouteAuthFailureError::test_auth_error_message_displayed_on_protected_route
PASSED  TestProtectedRouteAuthFailureError::test_no_redirect_to_home_page
PASSED  TestProtectedRouteAuthFailureError::test_no_sign_in_link_visible
```
