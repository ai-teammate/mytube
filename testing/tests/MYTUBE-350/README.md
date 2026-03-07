# MYTUBE-350 — Auth status resolving: loading indicator displayed

## Objective

Verify that the application displays a loading indicator while the Firebase
authentication status is being resolved, and that protected content is not
rendered prematurely.

## Prerequisites

| Requirement | Details |
|---|---|
| Chromium / Playwright | Installed via `pip install playwright && playwright install chromium` |
| `APP_URL` or `WEB_BASE_URL` | Base URL of the deployed app (default: `https://ai-teammate.github.io/mytube`) |
| `PLAYWRIGHT_HEADLESS` | Run browser in headless mode (default: `true`) |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms for debugging (default: `0`) |

## Preconditions

An artificial delay is introduced to Firebase's authentication initialization.
The test uses `context.add_init_script()` to inject a JavaScript snippet that
wraps `IDBFactory.prototype.open` and delays the IndexedDB `success` callback
by **3 000 ms**. Firebase uses IndexedDB to read its cached auth state; by
delaying the callback, `loading` stays `true` for a window that Playwright can
reliably assert against.

## Test Steps

1. Inject the IDB delay init script before navigating to a protected route.
2. Navigate to the protected route (e.g. `/upload/` or `/dashboard/`) with
   `wait_until="commit"` — Playwright returns as soon as the response is
   committed, before React hydration and before the delayed IDB success fires.
3. Assert the `.animate-spin` spinner is **visible**.
4. Assert the `"Loading…"` paragraph is **visible**.
5. Assert that the protected page content (e.g. "Upload video" form title) is
   **not** visible while the loading state is active.
6. Wait for the auth state to resolve (IDB delay expires → Firebase fires the
   callback → `loading` becomes `false` → unauthenticated user is redirected
   to `/login/?next=<path>`).
7. Assert the spinner is **hidden** after auth resolves.

## Expected Result

- The `.animate-spin` spinner element is visible immediately after navigation
  commit while `loading === true`.
- The `"Loading…"` paragraph is visible alongside the spinner.
- Protected content (e.g. the upload form heading) is **not** rendered while
  the loading guard is active — no premature content flicker.
- After the IDB delay expires and Firebase resolves the unauthenticated state,
  the spinner disappears and the user is redirected to `/login/`.

## Test Cases

| # | Test | Route | Assertion |
|---|---|---|---|
| 1 | `test_loading_spinner_visible_while_auth_pending` | `/upload/` | Spinner and "Loading…" text visible; spinner gone after redirect |
| 2 | `test_no_protected_content_shown_while_auth_pending` | `/upload/` | "Upload video" form title hidden while spinner is shown |
| 3 | `test_loading_indicator_on_dashboard_route` | `/dashboard/` | Spinner and "Loading…" text visible; spinner gone after redirect |

## Test Approach — IDB delay mechanism

`RequireAuth` (`web/src/components/RequireAuth.tsx`) calls
`onAuthStateChanged` from Firebase and keeps `loading === true` until the first
callback fires.  Firebase reads its cached auth state from IndexedDB; by
patching `IDBFactory.prototype.open` in the page's JS context we can delay
the `success` event (and the `onsuccess` property setter) by an arbitrary
number of milliseconds, extending the `loading === true` window to be reliably
detectable.

The init script is defined in `RequireAuthComponent.FIREBASE_DELAY_INIT_SCRIPT`
(see `testing/components/pages/require_auth_component/require_auth_component.py`)
and reused by all test cases — the mechanism only needs to be maintained in
one place.

## Component layer

All selectors and assertion methods are encapsulated in `RequireAuthComponent`
under `testing/components/pages/require_auth_component/`. The test file calls
only high-level methods such as `assert_loading_spinner_visible()`,
`assert_loading_text_visible()`, `assert_spinner_hidden()`, and
`assert_upload_form_title_hidden()`.

## Install dependencies

```bash
pip install pytest playwright
playwright install chromium
# or via requirements.txt:
pip install -r testing/requirements.txt
```

## Run the tests

From the repository root:

```bash
pytest testing/tests/MYTUBE-350/ -v
```

With a custom base URL:

```bash
APP_URL=https://ai-teammate.github.io/mytube pytest testing/tests/MYTUBE-350/ -v
```

## Expected output when passing

```
testing/tests/MYTUBE-350/test_mytube_350.py::TestAuthLoadingIndicator::test_loading_spinner_visible_while_auth_pending PASSED
testing/tests/MYTUBE-350/test_mytube_350.py::TestAuthLoadingIndicator::test_no_protected_content_shown_while_auth_pending PASSED
testing/tests/MYTUBE-350/test_mytube_350.py::TestAuthLoadingIndicator::test_loading_indicator_on_dashboard_route PASSED
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web application |
| `WEB_BASE_URL` | No | _(falls back to APP_URL)_ | Alternative env var for the base URL |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Set to `false` to run with a visible browser |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms (useful for debugging) |
