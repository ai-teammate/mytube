# MYTUBE-367 — Auth Status Observer Failure During Active Session — Error Message Displayed

## Objective

Verify that when the Firebase authentication state observer (`onAuthStateChanged`) encounters
an error **after** the application has successfully initialised, the app displays a clear
error message (`"Authentication services are currently unavailable"`) rather than silently
treating the user as an unauthenticated guest.

## Preconditions

- The application is reachable at `APP_URL` / `WEB_BASE_URL`.
- Firebase auth is available at test start so the initial auth cycle resolves cleanly.
- For **Mode 1** (authenticated path): `FIREBASE_TEST_EMAIL` and `FIREBASE_TEST_PASSWORD`
  must be set to a valid CI test account.

## Test Steps

The test tries three escalating approaches to trigger the mid-session auth failure:

### Mode 1 — Authenticated (preferred, requires credentials)

1. Navigate to `/login/` and log in as the CI test user.
2. Wait for the authenticated dashboard to appear.
3. Block Firebase auth domains via Playwright route intercepts (simulating a mid-session
   network failure).
4. Wait `_HEARTBEAT_WAIT_MS` (135 s = 120 s interval + 10 s probe timeout + 5 s buffer)
   for the periodic heartbeat probe (introduced in MYTUBE-381/MYTUBE-399) to fire,
   time out, and set `authError=true` in React state.
5. Assert that a `role="alert"` element containing `"Authentication services are currently
   unavailable"` is visible.

### Mode 2 — Fake-session injection (no credentials, API key extractable)

1. Navigate to the home page (Firebase available → auth resolves to `null`).
2. Extract the Firebase API key from the page's bundled JavaScript.
3. Inject a fake authenticated user into `localStorage` with an expired token.
4. Block Firebase auth domains.
5. Reload the page; wait the full heartbeat window.
6. Assert the auth-error message is visible.

### Mode 3 — Hard-reload fallback (no credentials, no API key)

1. Navigate to the home page (Firebase available → auth resolves cleanly).
2. Block Firebase auth domains.
3. Perform a hard page reload while Firebase is blocked.
4. Assert the auth-error message is visible.

## Expected Result

The application displays `"Authentication services are currently unavailable"` in a
`role="alert"` element. The user is **not** silently transitioned to an unauthenticated
guest state without notification.

## Test Cases

| Test | Description |
|------|-------------|
| `test_auth_error_shown_after_firebase_blocked_mid_session` | Confirms the auth-error alert is visible after Firebase is blocked during an active session. |
| `test_no_silent_guest_fallback_when_auth_fails_mid_session` | Confirms the app does NOT silently show only a "Sign in" link when auth fails — an error message must accompany it. |

## Environment Variables

| Variable              | Required | Default                                  | Description                              |
|-----------------------|----------|------------------------------------------|------------------------------------------|
| `APP_URL` / `WEB_BASE_URL` | No  | `https://ai-teammate.github.io/mytube`   | Base URL of the deployed web app.        |
| `FIREBASE_TEST_EMAIL` | No       | —                                        | Test user email (enables Mode 1).        |
| `FIREBASE_TEST_PASSWORD` | No    | —                                        | Test user password (enables Mode 1).     |
| `PLAYWRIGHT_HEADLESS` | No       | `true`                                   | Run browser headless.                    |
| `PLAYWRIGHT_SLOW_MO`  | No       | `0`                                      | Slow-motion delay in ms.                 |

## Heartbeat Timing

The MYTUBE-381/MYTUBE-399 fix introduced a periodic heartbeat probe in `AuthContext.tsx`:

| Constant                  | Value      | Source                  |
|---------------------------|------------|-------------------------|
| `HEARTBEAT_INTERVAL_MS`   | 120 000 ms | `AuthContext.tsx`       |
| `HEARTBEAT_PROBE_TIMEOUT_MS` | 10 000 ms | `AuthContext.tsx`    |
| `_HEARTBEAT_WAIT_MS` (test) | 135 000 ms | interval + timeout + 5 s buffer |

The test **must** wait at least 135 seconds after blocking Firebase before asserting
the error is visible, to allow the probe to fire and detect the blocked network.

## Running the Tests Locally

```bash
# From the repository root:
cd /path/to/mytube

# Install dependencies (once):
pip install playwright pytest
playwright install chromium

# Run without credentials (Modes 2/3):
pytest testing/tests/MYTUBE-367/test_mytube_367.py -v

# Run with credentials (Mode 1, full heartbeat wait — takes ~4-5 minutes):
FIREBASE_TEST_EMAIL=ci-test@mytube.test \
FIREBASE_TEST_PASSWORD=<password> \
pytest testing/tests/MYTUBE-367/test_mytube_367.py -v
```

## Related Tickets

- **MYTUBE-381** / **MYTUBE-399** — Heartbeat probe fix that enables mid-session auth
  error detection (`AuthContext.tsx`).
- **MYTUBE-351** — Related: auth error shown on initial load when Firebase is unreachable.
