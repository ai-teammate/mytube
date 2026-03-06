# MYTUBE-246: Video.js Player Error on Unreachable HLS Manifest

## Test Objective

Verify that the Video.js player correctly identifies and reports a network failure when the HLS manifest cannot be retrieved from the CDN. The player must display a visible error overlay to prevent silent failure when the manifest URL is unreachable.

**Specification Reference**: MYTUBE-246

## What This Test Validates

The test automates the following scenario:
1. User navigates to a video watch page
2. The video has an unreachable HLS manifest URL (simulates CDN failure)
3. The Video.js player attempts to initialize and load the media
4. The player displays a visible error alert indicating the media could not be loaded
5. The user receives clear feedback about the failure (not silent failure)

## Dependencies

Install required packages:
```bash
pip install pytest playwright
```

## Environment Variables

- **`APP_URL`** / **`WEB_BASE_URL`**: Base URL of the deployed web application
  - Default: `https://ai-teammate.github.io/mytube`
  - Example: `export WEB_BASE_URL=https://your-domain.com/mytube`

- **`PLAYWRIGHT_HEADLESS`**: Run browser headless (default: `true`)
  - Set to `false` for debugging: `export PLAYWRIGHT_HEADLESS=false`

- **`PLAYWRIGHT_SLOW_MO`**: Slow-motion delay in milliseconds (default: `0`)
  - Useful for debugging: `export PLAYWRIGHT_SLOW_MO=1000`

## Test Setup & Architecture

### Test Infrastructure

- **Framework**: Playwright (sync API with pytest)
- **Browser**: Chromium (headless by default)
- **Page Object Pattern**: Uses `WatchPage` component from `testing/components/pages/watch_page/`
- **API Mocking**: Playwright route interception (no external servers required)
- **Test URL**: Static placeholder watch page at `/v/_/` (pre-generated in static export)

### Test Flow

1. **Setup**: Browser, page context, and route mocking configured
2. **Navigation**: Navigate to `/v/_/` (placeholder watch page)
3. **API Mock**: Intercept video detail API calls and return mock video with unreachable manifest
4. **Player Initialization Wait**: Wait up to 20 seconds for player to initialize
5. **Assertions**: Verify player container, initialization, and error display
6. **Cleanup**: Unregister route handlers

### Mocked Data

The test mocks the API response with:
- Video ID: `_` (placeholder)
- Manifest URL: `https://storage.googleapis.com/non-existent-bucket-12345/manifest.m3u8`
- Status: `ready`
- Other fields: Standard video metadata

## How to Run

### Run All Tests in This Folder

```bash
cd testing
python -m pytest tests/MYTUBE-246/ -v
```

### Run Single Test

```bash
cd testing
python -m pytest tests/MYTUBE-246/test_mytube_246.py::TestUnreachableHLSManifest::test_video_player_displays_error_on_unreachable_manifest -v
```

### Run with Debugging

```bash
# Run in non-headless mode (see browser)
export PLAYWRIGHT_HEADLESS=false
# Add slow-motion for visual inspection
export PLAYWRIGHT_SLOW_MO=1000
cd testing
python -m pytest tests/MYTUBE-246/test_mytube_246.py -v
```

## Expected Output

### Current Status (PASS)

The feature is fully implemented and the test passes:

```
testing/tests/MYTUBE-246/test_mytube_246.py::TestUnreachableHLSManifest::test_video_player_displays_error_on_unreachable_manifest PASSED [100%]
```

## Test Assertions & Step Verification

The test verifies:
1. ✅ Player container is visible (`[data-vjs-player]` element)
2. ✅ Video.js player initializes (checks for `vjs-paused` or `vjs-playing` CSS class on video element)
3. ✅ Error alert is displayed (`[role='alert']` element)
4. ✅ Error message contains meaningful context (mentions error, failed, or network)

## Components Used

- **`WatchPage`** (`testing/components/pages/watch_page/watch_page.py`): Page object encapsulating watch page UI interactions and assertions
  - `navigate_to_video(base_url, video_id)`: Navigate to watch page
  - `wait_for_metadata(timeout)`: Wait for metadata to load
  - `is_player_container_visible()`: Check if player is rendered
  - `is_player_initialised()`: Check if Video.js player initialized
  - `is_error_displayed()`: Check if error alert is visible
  - `get_error_message()`: Retrieve error alert text

## Troubleshooting

### Test times out waiting for player initialization
- Verify you're running against the correct URL
- Check browser console for JavaScript errors

### Player container not visible
- Verify the watch page is loading correctly
- Check that `[data-vjs-player]` element exists in the DOM
- Ensure CSS is loaded and player element is not hidden

### Mock API not being intercepted
- Verify route patterns match the actual API calls
- Check browser network tab to see actual request URLs
- Ensure routes are registered before page navigation

## Related Issues

- **Feature Issue**: Implementation of error handling in VideoPlayer.tsx
- **Spec Reference**: MYTUBE-246 test case specification
- **PR**: #205 (this test automation PR)
