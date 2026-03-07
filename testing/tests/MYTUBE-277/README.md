# MYTUBE-277: Session expires during upload completion — user redirected to login page

## Test Overview

This test suite verifies that the MyTube application enforces session validation during and after video upload, ensuring that users with expired sessions are redirected to the login page instead of the dashboard.

## Test Cases

### 1. test_session_expires_during_upload_completion_redirects_to_login (INTEGRATION)
**Status**: ✅ PASSED

**Objective**: Verify that when a user's session expires during upload completion, the application redirects them to the login page instead of the dashboard.

**Preconditions**:
- User is authenticated and on the /upload page
- Firebase credentials are available via environment variables
- Web application is deployed and accessible

**Steps**:
1. Sign in a test user and navigate to /upload page
2. Register Playwright route intercepts for `POST /api/videos` (fake GCS URL) and the fake GCS `PUT` request
3. Fill and submit the upload form
4. Inside the fake GCS PUT handler — before fulfilling with HTTP 200 — expire the Firebase in-memory token via React fiber introspection and register a `securetoken.googleapis.com` block
5. After the XHR completes, the frontend calls `getIdToken()`: Firebase detects the expired token, attempts a refresh, the refresh is blocked, and `getIdToken()` returns `null`
6. Verify the browser redirects to `/login` instead of `/dashboard`

**Approach**: The test uses three complementary techniques to reliably simulate session expiry without a live GCS backend:
1. **Route interception for `POST /api/videos`** — returns a fake `{ video_id, upload_url }` so no real backend is needed.
2. **React fiber introspection** — sets `stsTokenManager.expirationTime` to 10 minutes in the past, forcing the Firebase SDK to refresh the token on the next `getIdToken()` call.
3. **`securetoken.googleapis.com` interception** — returns HTTP 400 `TOKEN_EXPIRED` to block the forced refresh, causing `getIdToken()` to return `null` and triggering the `/login` redirect.

### 2. test_upload_page_redirects_unauthenticated_users_to_login (SMOKE TEST)
**Status**: ✅ PASSED

**Objective**: Verify that the /upload page enforces authentication by redirecting unauthenticated users to the login page.

**Preconditions**:
- Web application is deployed and accessible

**Steps**:
1. Create a new browser context without any authentication cookies
2. Navigate directly to the /upload page
3. Verify that the page redirects to /login

**Result**: ✅ PASSED
The unauthenticated user was correctly redirected to the login page, confirming that the application enforces authentication on the protected /upload route.

## Architecture Notes

- **Framework**: Playwright (sync API)
- **Page Objects Used**: UploadPage, LoginPage
- **Isolated Testing**: Each test creates a fresh browser context to ensure test isolation
- **Route Interception**: `POST /api/videos` and the fake GCS `PUT` are intercepted so the test runs without a live backend or GCS service
- **Environment Variables**:
  - `WEB_BASE_URL`: Base URL of the deployed web application (default: https://ai-teammate.github.io/mytube)
  - `FIREBASE_TEST_EMAIL`: Test user email
  - `FIREBASE_TEST_PASSWORD`: Test user password
  - `PLAYWRIGHT_HEADLESS`: Run browser in headless mode (default: true)

## Test Execution

```bash
cd testing
WEB_BASE_URL="https://ai-teammate.github.io/mytube" \
FIREBASE_TEST_EMAIL="ci-test@mytube.test" \
FIREBASE_TEST_PASSWORD="6U1RUffqHXY47pr7ge3V" \
python -m pytest tests/MYTUBE-277/test_mytube_277.py -v
```

## Expected Behavior

The application's upload page (`web/src/app/upload/page.tsx`) implements the following security checks:

1. **Entry-point redirect**: Unauthenticated users are redirected from /upload to /login via a useEffect hook
2. **Upload initiation**: Token is retrieved via `getIdToken()` before initiating upload
3. **Session validation on redirect**: After upload completes, the app calls `router.replace('/dashboard?uploaded=${videoId}')`, which should trigger another auth check that redirects to /login if the session has expired

## Known Issues

None. Both tests pass. The integration test is fully self-contained thanks to Playwright route interception and does not require a live GCS backend.
