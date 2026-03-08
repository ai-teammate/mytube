MYTUBE-395

Test purpose
------------
Verify that when a browser holds an expired Firebase session token and all Firebase auth/token network endpoints are unreachable (network blocked or service outage), the application displays an authentication error message instead of silently falling back to an unauthenticated guest state.

Preconditions
-------------
- The deployed application is reachable via WEB_BASE_URL (default: https://ai-teammate.github.io/mytube).
- Playwright environment with Chromium is available.

How the test works
------------------
1. The test discovers the Firebase API key used by the deployed app by inspecting network requests and page scripts.
2. It creates a fresh Playwright context and injects a structurally valid but expired Firebase user object into localStorage under the key `firebase:authUser:<API_KEY>:[DEFAULT]` before any application scripts run.
3. The test blocks requests to Firebase auth and token endpoints (securetoken.googleapis.com, identitytoolkit.googleapis.com, and any configured authDomain) using Playwright routing so the SDK cannot refresh the expired token.
4. The test speeds up the AuthContext heartbeat interval so the probe runs immediately and the app has time within the test window to detect the refresh failure.
5. The test asserts that the site header displays an authentication-error alert (role="alert") and that the "Sign in" navigation link is not visible without an accompanying error (no silent guest fallback).

Running locally / CI
--------------------
- Ensure environment variables are set: WEB_BASE_URL (or APP_URL) points to the deployed app.
- From the repository root run the Playwright/pytest suite relevant to this project (project conventions may provide a wrapper script). Example:

pytest -q testing/tests/MYTUBE-395 -k MYTUBE-395

Notes and rationale
-------------------
- The test uses explicit host-aware route patterns and a defensive predicate-based route to reliably block Firebase endpoints in Playwright.
- The route handler uses `route.abort('aborted')` (with fallbacks) to simulate a network outage; this uses Playwright-supported error codes to avoid runtime exceptions.
- The heartbeat interval override is used only to accelerate the probe in tests and does not modify application code.
