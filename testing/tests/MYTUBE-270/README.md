# MYTUBE-270: Category page with API failure — error message displayed to user

## Objective
Verify that the UI handles API communication failures gracefully on the category browse page.

## Test Coverage
This test verifies that when the `/api/videos?category_id=[ID]` endpoint returns a 500 Internal Server Error:
1. The category page still loads without crashing
2. A clear error notification/alert is visible to the user
3. The error message indicates that content could not be retrieved
4. The page does not show a broken layout or misleading content (e.g., showing video cards AND an error)

## Architecture
- **Type**: Web UI Test (Playwright)
- **Framework**: pytest + Playwright
- **Components Used**:
  - `CategoryPage` — Page Object for `/category/{id}/` interactions
  - `WebConfig` — Environment configuration
  - `APIConfig` — API base URL configuration
  - `CategoriesApiService` — Fetches valid category IDs from API

## Running the Test

```bash
cd /home/runner/work/mytube/mytube
pytest testing/tests/MYTUBE-270/test_mytube_270.py -v
```

### With specific environment variables
```bash
APP_URL="https://ai-teammate.github.io/mytube" \
API_BASE_URL="http://localhost:8081" \
PLAYWRIGHT_HEADLESS=true \
pytest testing/tests/MYTUBE-270/test_mytube_270.py -v
```

## Test Method

`test_category_page_displays_error_on_api_500`

**Steps**:
1. Set up Playwright route interception for `/api/videos**` to simulate a network failure
2. Navigate to `/category/{category_id}/`
3. Verify:
   - An error alert/notification is visible (has_error = True)
   - Error text is present and meaningful
   - Error text contains error-related keywords (error, failed, unable, etc.)
   - Page is not showing video cards alongside the error

## Expected Result
✅ Test passes when an error message is clearly displayed to the user.

## Failure Modes
The test will fail if:
- No error alert is visible when the API fails (missing error handling)
- Error text is empty or missing (incomplete error display)
- Error text does not indicate a failure (misleading message)
- Video cards are shown despite the API failure (inconsistent state)

## Notes
- The test uses a fallback category ID if no valid categories can be fetched from the API
- Playwright's `route.abort()` is used to simulate network/API failures deterministically
- The test is framework-independent; the CategoryPage object handles all Playwright details
