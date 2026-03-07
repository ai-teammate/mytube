# MYTUBE-264: Rating update API returns 500 error — UI reverts star selection and displays message

## Objective
Verify that the UI handles API failures gracefully when a user attempts to rate a video, preventing incorrect visual states.

## Preconditions
- User is authenticated (FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD)
- User is on the video watch page

## Test Steps
1. Mock the API POST request to `/api/videos/:id/rating` to return a 500 Internal Server Error status
2. Click on a star to change the rating

## Expected Results
- The UI displays an error notification (e.g., "Failed to update rating")
- The star icons revert to their previous selection state

## Test Coverage
The test includes four assertions:

1. **Error Message Displayed**: Verifies that an error alert appears when the rating API returns 500
2. **Star State Reverted**: Confirms that the clicked star reverts to unpressed after the API error
3. **Other Stars Unaffected**: Ensures that only the clicked star is affected, other stars maintain their state
4. **Rating Summary Unchanged**: Validates that the rating summary text does not change after the error

## Architecture
- **Framework**: Playwright (sync API)
- **Page Objects**: WatchPage, LoginPage
- **Services**: SearchService (for video discovery), WebConfig (env config)
- **Route Interception**: Playwright route.fulfill() to mock API responses
  - GET `/api/videos/*/rating`: Returns mock success (4.0 / 5, 8 ratings)
  - POST `/api/videos/*/rating`: Returns 500 error
