# MYTUBE-283: Refresh dynamic video watch page — player re-initializes and 404 error is avoided

## Test Overview

This test suite verifies that performing a browser refresh on a dynamic video route (`/v/[id]`) does not trigger a Next.js 404 error and that the Video.js player re-initializes successfully after the reload.

## Test Cases

### 1. test_initial_navigation_loads_player
**Status**: ⚠️ Expected to FAIL (environmental — all ready videos have `hls_manifest_url: null`)

**Objective**: Verify that direct navigation to `/v/<uuid>` renders the `[data-vjs-player]` container.

**Steps**:
1. Discover a ready video via `VideoApiService` or `TEST_VIDEO_ID` env var
2. Navigate directly to `/v/<uuid>`
3. Assert `[data-vjs-player]` container is visible in the DOM

### 2. test_initial_title_displayed
**Status**: ✅ Expected to PASS

**Objective**: Verify that the video `<h1>` title is rendered after initial navigation.

**Steps**:
1. After initial navigation (depends on `initial_load_result` fixture)
2. Assert an `<h1>` element is visible and contains non-empty text

### 3. test_no_nextjs_404_after_refresh
**Status**: ✅ Expected to PASS

**Objective**: Verify that performing `page.reload()` (equivalent to Ctrl+R / Cmd+R) does NOT render the Next.js default 404 page ("This page could not be found.").

**Steps**:
1. After initial navigation, call `page.reload(wait_until="domcontentloaded")`
2. Wait for the page to settle
3. Assert the text "This page could not be found." is absent from the page body

### 4. test_player_container_present_after_refresh
**Status**: ⚠️ Expected to FAIL (environmental — `hls_manifest_url: null` prevents player mount)

**Objective**: Verify that `[data-vjs-player]` is present in the DOM after the browser refresh.

**Steps**:
1. After `page.reload()` (depends on `after_refresh_result` fixture)
2. Assert `[data-vjs-player]` container is visible

### 5. test_video_element_present_after_refresh
**Status**: ⚠️ Expected to FAIL (environmental — `hls_manifest_url: null` prevents player mount)

**Objective**: Verify that a `<video>` element is present inside `[data-vjs-player]` after refresh.

**Steps**:
1. After `page.reload()`
2. Assert a `<video>` element (`.video-js` or `.vjs-tech`) is present within the player container

### 6. test_title_still_displayed_after_refresh
**Status**: ✅ Expected to PASS

**Objective**: Verify that the video title is still visible after the browser refresh.

**Steps**:
1. After `page.reload()`
2. Assert an `<h1>` element is visible and contains non-empty text

## Architecture Notes

- **Framework**: Playwright (sync API)
- **Page Objects Used**: `WatchPage`
- **Services Used**: `VideoApiService`
- **Fixture scope**: `module` — single browser session shared across all tests
- **Environment Variables**:
  - `WEB_BASE_URL` / `APP_URL`: Base URL of the deployed web application (default: `https://ai-teammate.github.io/mytube`)
  - `API_BASE_URL`: Base URL of the backend API for video discovery (default: `http://localhost:8081`)
  - `TEST_VIDEO_ID`: Override video ID — skips API discovery and uses this ID directly
  - `PLAYWRIGHT_HEADLESS`: Run browser in headless mode (default: `true`)
  - `PLAYWRIGHT_SLOW_MO`: Slow-motion delay in ms (default: `0`)

## Test Execution

```bash
cd /path/to/mytube
WEB_BASE_URL="https://ai-teammate.github.io/mytube" \
API_BASE_URL="https://your-api-base-url" \
python -m pytest testing/tests/MYTUBE-283/test_mytube_283.py -v
```

## Known Issues

All 5 "ready" videos in the current environment have `hls_manifest_url: null`, which causes the watch page to display "Video not available yet." instead of mounting the Video.js player. This means `test_initial_navigation_loads_player`, `test_player_container_present_after_refresh`, and `test_video_element_present_after_refresh` will fail until videos with a valid HLS manifest are available. The 404-avoidance test (`test_no_nextjs_404_after_refresh`) and title tests pass, confirming that static-host routing and metadata loading work correctly.
