# MYTUBE-281: Navigate to watch page via homepage card — basePath is preserved and player UI initializes

## Test Overview

This test suite verifies that client-side navigation from the MyTube homepage to a video watch page correctly preserves the application's basePath (e.g. `/mytube` on GitHub Pages) and that the Video.js player UI components are fully initialised after navigation.

## Test Cases

### 1. test_url_contains_base_path
**Status**: ✅ Expected to PASS

**Objective**: Verify that the URL after clicking a homepage card title contains the basePath and matches the pattern `<basePath>/v/<uuid>`.

**Steps**:
1. Navigate to the application homepage
2. Assert at least one video card is visible
3. Click the title link of the first video card
4. Assert the resulting URL contains the basePath and `/v/<uuid>` pattern

### 2. test_vjs_player_container_present
**Status**: Depends on watch page route correctness

**Objective**: Verify that the `[data-vjs-player]` container is present in the DOM after navigation.

### 3. test_vjs_control_bar_visible
**Status**: Depends on Video.js initialisation

**Objective**: Verify that `.vjs-control-bar` is visible once the player initialises.

### 4. test_vjs_big_play_button_visible
**Status**: Depends on Video.js initialisation

**Objective**: Verify that `.vjs-big-play-button` is visible (player ready, paused state).

### 5. test_video_title_in_h1
**Status**: Depends on watch page data loading

**Objective**: Verify that an `<h1>` element is present and its text matches the title that was clicked on the homepage.

### 6. test_homepage_grid_not_rendered
**Status**: ✅ Expected to PASS

**Objective**: Verify that the homepage discovery grid sections are no longer rendered after client-side navigation to the watch page.

## Architecture Notes

- **Framework**: Playwright (sync API)
- **Page Objects Used**: `HomePage`, `WatchPage`
- **Fixture scope**: `module` — single browser session shared across all tests
- **Environment Variables**:
  - `WEB_BASE_URL`: Base URL of the deployed web application (default: `https://ai-teammate.github.io/mytube`)
  - `PLAYWRIGHT_HEADLESS`: Run browser in headless mode (default: `true`)
  - `PLAYWRIGHT_SLOW_MO`: Slow-motion delay in ms (default: `0`)

## Test Execution

```bash
cd /path/to/mytube
WEB_BASE_URL="https://ai-teammate.github.io/mytube" \
python -m pytest testing/tests/MYTUBE-281/test_mytube_281.py -v
```

## Known Issues

The watch page at `/mytube/v/<uuid>` currently renders a Next.js 404 page instead of the video player. This causes `test_vjs_player_container_present`, `test_vjs_control_bar_visible`, `test_vjs_big_play_button_visible`, and `test_video_title_in_h1` to fail. The test correctly detects this application-level bug — the fix must be applied to the watch page route in the web application, not to the test.
