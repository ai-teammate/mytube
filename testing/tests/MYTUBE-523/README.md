# MYTUBE-523: Reset Filters Functionality

## Purpose

Verify that the **"Reset filters"** ghost button on the dashboard correctly clears all active filters:

- The search input is cleared.
- The playlist chip filter resets to "All".
- The video grid shows all videos.

## Test Steps

1. Enter text into the search input.
2. Select a specific playlist chip.
3. Click the "Reset filters" ghost button in the toolbar.

## Expected Result

After clicking "Reset filters":
- Search input value is empty.
- The "All" playlist chip becomes active.
- The video grid displays all available videos.

## Approach

### Live Mode

When the authenticated CI user (`ci-test@mytube.test`) has at least one video on their dashboard, the test logs in, navigates to `/dashboard`, and exercises the real React components.

### Fixture Mode (CI fallback)

The CI test user currently has no uploaded videos. Because the dashboard toolbar (search input + Reset button) only renders when `videos.length > 0`, a **local HTTP fixture server** is used as a fallback.

The fixture serves a minimal HTML page (`_FIXTURE_HTML`) that replicates the filter UI — search input, Reset button, playlist chips, and video cards — using vanilla JS logic that matches the React implementation's filtering behaviour.

The test automatically selects live mode if the user has videos; otherwise fixture mode is used transparently.

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `WEB_BASE_URL` / `APP_URL` | Base URL of the deployed web app | `https://ai-teammate.github.io/mytube` |
| `FIREBASE_TEST_EMAIL` | CI test user email | *(required)* |
| `FIREBASE_TEST_PASSWORD` | CI test user password | *(required)* |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

## Files

| File | Description |
|---|---|
| `test_mytube_523.py` | Test implementation (5 test cases) |
| `config.yaml` | Test metadata and dependency declarations |
| `__init__.py` | Package marker |
