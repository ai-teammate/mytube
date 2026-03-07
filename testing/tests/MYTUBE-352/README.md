# MYTUBE-352 — Access My Videos page while unauthenticated — user redirected to login

Verifies that the `/my-videos` page is protected by the client-side `RequireAuth`
route guard and that unauthenticated users are automatically redirected to `/login`.

## Objective

Ensure the 'My Videos' page requires authentication. Navigating to `/my-videos/`
without an active session must trigger a redirect to the login page.

## Preconditions

- User is **not** logged in (no active Firebase session in the browser).
- No cookies or stored authentication state in the browser context.

## Steps

1. Open a fresh browser context with no stored auth state.
2. Navigate directly to `{base_url}/my-videos/`.
3. Wait up to 15 s for the URL to change to contain `/login`.
4. Assert the login form (email input) is visible on the page.

## Expected Result

The client-side `RequireAuth` route guard detects the unauthenticated state and
redirects the user to `/login` (optionally with a `?next=…` query parameter).
The login form is rendered and visible.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web application |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser in headless mode |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms (useful for debugging) |

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Running the Test

From the repository root:

```bash
pytest testing/tests/MYTUBE-352/test_mytube_352.py -v
```

## Expected Output (passing)

```
PASSED TestMyVideosUnauthenticatedRedirect::test_unauthenticated_redirect_to_login
```
