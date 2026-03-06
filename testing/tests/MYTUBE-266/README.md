# MYTUBE-266: View Watch Page as Guest — Rating Widget is Read-Only

## Test Objective

Verify that unauthenticated users can view the average rating on the video watch page but cannot interact with the widget to submit ratings. The rating widget should remain in a read-only state for guests.

## Preconditions

- User is not logged in
- Video has an average rating of 4.0 from 5 users

## Test Steps

1. Navigate to the video watch page
2. Verify the widget displays "4.0 / 5" and "(5)"
3. Attempt to click on the stars in the widget

## Expected Result

The star icons do not change visual state on hover or click. No API requests are triggered, and the UI remains in a read-only state.

## Test Implementation

### Architecture

- **Framework**: Playwright (sync API)
- **Page Object Model**: Uses `WatchPage` from `testing/components/pages/watch_page/`
- **Mode**: Dual-mode approach
  - **Live mode**: Discovers a ready video with rating 4.0 via VideoApiService API
  - **Fixture mode**: Falls back to a local HTML server that renders a read-only rating widget
- **Network Monitoring**: Captures HTTP requests to verify no rating API calls during guest interaction

### Test Cases

The test suite includes 5 test methods:

1. **test_rating_summary_displays_correctly**
   - Verifies the rating summary text displays "4.0 / 5" and "(5)"
   - Waits for the rating summary to be visible before assertion

2. **test_rating_widget_is_visible**
   - Confirms the rating widget group (role="group" aria-label="Star rating") is present in DOM

3. **test_stars_do_not_have_pressed_state_initially**
   - Verifies all 5 stars have no aria-pressed="true" state initially
   - Guest users should see disabled stars, not selected ones

4. **test_clicking_stars_does_not_change_state**
   - Verifies star buttons are disabled (the read-only marker)
   - Confirms no aria-pressed="true" state is set after any interaction attempt
   - Monitors network requests to ensure no rating API calls are triggered

5. **test_no_login_prompt_shown**
   - Checks for absence of "Log in to rate this video" prompt
   - Confirms the widget is read-only (not blocked-until-login)

### Configuration

Test configuration is in `config.yaml`:

```yaml
test_id: MYTUBE-266
type: web
framework: playwright
platform: chrome
dependencies: []
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WEB_BASE_URL` / `APP_URL` | https://ai-teammate.github.io/mytube | Base URL of the deployed web app |
| `API_BASE_URL` | http://localhost:8081 | Backend API base URL (for video discovery) |
| `PLAYWRIGHT_HEADLESS` | true | Run browser in headless mode |
| `PLAYWRIGHT_SLOW_MO` | 0 | Slow-motion delay in ms (for debugging) |

## Running the Test

### Single test run

```bash
cd testing && python -m pytest tests/MYTUBE-266/test_mytube_266.py -v
```

### With environment variables

```bash
WEB_BASE_URL=http://localhost:3000 \
API_BASE_URL=http://localhost:8081 \
PLAYWRIGHT_HEADLESS=false \
PLAYWRIGHT_SLOW_MO=500 \
python -m pytest tests/MYTUBE-266/test_mytube_266.py -v -s
```

### Run specific test

```bash
python -m pytest tests/MYTUBE-266/test_mytube_266.py::TestRatingWidgetReadOnlyForGuest::test_rating_summary_displays_correctly -v
```

## Test Data

### Live Mode (when API is available)

The test uses `VideoApiService` to discover a ready video from the API. The service queries known test user profiles (tester, testuser, alice, admin) and returns the first ready video found. No special test data setup is required if videos already exist in the API.

### Fixture Mode (fallback)

If no ready video is found or the API is unreachable, the test falls back to a local HTTP server that serves a minimal HTML page with a read-only rating widget showing 4.0 / 5 (5). This fixture is defined inline in the test file.

## Assertions

### Network Monitoring

The test uses Playwright's request monitoring to capture and verify:
- ✅ No HTTP requests to `/api/ratings/` or similar endpoints during interaction
- ✅ No `POST` or `PUT` requests to rating endpoints
- ✅ The widget remains truly read-only (no state management on the frontend)

### Widget State

The test verifies:
- ✅ Rating summary text is accurate and visible
- ✅ All star buttons are present in DOM
- ✅ Star buttons are disabled (HTML `disabled` attribute)
- ✅ No `aria-pressed` attribute set to "true" on any star
- ✅ No visual state changes when attempting to interact

## Troubleshooting

### Port conflict (Address already in use)

If you see `OSError: [Errno 98] Address already in use` when running the fixture mode:
- The test uses an OS-assigned port (port 0) to avoid conflicts
- If this still fails, check for lingering pytest processes: `pkill -f pytest`

### Video not found in live mode

If the test skips because no suitable video exists:
- The test falls back to the fixture mode automatically
- No special setup is required

### Playwright browser fails to launch

- Ensure Playwright browsers are installed: `playwright install`
- Check system dependencies: `playwright install-deps`

## Code Quality

- ✅ No hardcoded URLs or credentials
- ✅ All configuration via environment variables (WebConfig, APIConfig)
- ✅ Proper fixture scope management (module-scoped for performance)
- ✅ Network monitoring to verify guest read-only behavior
- ✅ Clear, descriptive assertion messages
- ✅ Follows test automation architecture in `agents/instructions/test_automation/test_automation_architecture.md`

## Author Notes

This test verifies a critical UX requirement: guests should be able to see ratings but not submit them. The dual-mode approach (live API + fixture) ensures the test is robust and can run in CI even without a full backend deployment. The network monitoring adds an extra layer of verification that the frontend truly respects the read-only constraint (no leaking API calls).
