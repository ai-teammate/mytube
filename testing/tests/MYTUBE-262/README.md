# MYTUBE-262: Delete video encounter server error — error notification shown

## Test Summary
This Playwright web UI test verifies that the MyTube dashboard properly handles backend failures during video deletion by displaying a clear error notification to the user.

## What It Tests
- **Precondition**: User is authenticated and viewing the `/dashboard`
- **Setup**: Mock the DELETE API to return a 500 Internal Server Error
- **Flow**:
  1. User clicks the "Delete" button next to a video
  2. User clicks "Confirm" in the confirmation prompt
  3. Backend returns 500 error (intercepted by Playwright route handler)
  4. Error notification is displayed to the user
  5. Video remains visible in the dashboard grid

## Test Type
- **Framework**: Playwright (sync API)
- **Platform**: Chromium (headless)
- **Type**: Web UI

## Dependencies
- `FIREBASE_TEST_EMAIL` — Email of Firebase test user (required)
- `FIREBASE_TEST_PASSWORD` — Password for Firebase test user (required)
- `WEB_BASE_URL` — Base URL of deployed web app (optional, defaults to https://ai-teammate.github.io/mytube)

## How to Run
```bash
cd /path/to/mytube
python -m pytest testing/tests/MYTUBE-262/ -v
```

With custom URL:
```bash
WEB_BASE_URL=http://localhost:3000 \
FIREBASE_TEST_EMAIL=test@example.com \
FIREBASE_TEST_PASSWORD=password123 \
python -m pytest testing/tests/MYTUBE-262/ -v
```

## Key Assertions
1. Dashboard loads and contains at least one video
2. Delete button is visible for non-processing videos
3. Confirmation dialog appears after clicking Delete
4. Route interception successfully aborts the DELETE request
5. Error notification is displayed (matches pattern: "Failed/Error/Oops/Something went wrong")
6. Video row count unchanged after failed deletion
7. Video remains visible by title in the dashboard

## Architecture Notes
- Uses `DashboardPage` for high-level dashboard interactions
- Uses `LoginPage` for authentication flow
- Uses Playwright's `page.route()` to intercept and abort DELETE requests
- No hardcoded URLs or credentials (uses `WebConfig`)
- No artificial waits; relies on Playwright's auto-wait
