# MYTUBE-276: Upload registration fails after 100% upload — redirection suppressed and error message displayed

## Test Case Overview

**Test ID**: MYTUBE-276

**Type**: Web UI Test (Playwright)

**Objective**: Verify that the application correctly handles server-side registration failures at the point of upload completion by preventing redirection and informing the user.

## Preconditions

- User is authenticated
- User is on the `/upload` page

## Test Steps

1. Complete the metadata form with valid information
2. Select a valid video file and initiate the upload
3. Wait for the progress bar to reach 100%
4. Simulate a 500 Internal Server Error for the subsequent API call that registers the completed upload
5. Observe the application behavior

## Expected Result

- The application remains on the upload page
- Redirection to the dashboard does NOT occur
- A clear error message is displayed to the user indicating the failure

## Technical Implementation

The test uses Playwright's route interception to mock the POST `/api/videos` endpoint, which is called after the file upload completes to register the video metadata. By returning a 500 status code, we simulate a server-side registration failure.

The test verifies:
- ✅ Error message is displayed to the user
- ✅ Page URL remains `/upload` (no redirect to `/dashboard`)
- ✅ User can see what went wrong

## Test Execution

Run the test with:
```bash
pytest testing/tests/MYTUBE-276/test_mytube_276.py -v
```

Environment variables required:
- `FIREBASE_TEST_EMAIL`: Firebase test user email
- `FIREBASE_TEST_PASSWORD`: Firebase test user password
- `WEB_BASE_URL`: Base URL of the deployed web app (optional, defaults to GitHub Pages)

## Architecture Notes

- **Page Objects**: Uses `UploadPage` and `LoginPage` from `testing/components/pages/`
- **Route Interception**: Mocks the registration API endpoint to return 500
- **No hardcoded values**: Environment configuration via `WebConfig`
- **Deterministic**: No sleeps; uses Playwright's built-in waits
