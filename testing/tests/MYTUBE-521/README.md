# MYTUBE-521 — Dashboard Client-Side Playlist Filtering

## Objective

Verify that selecting a playlist chip on the Dashboard filters the video grid client-side (no page reload), and that clicking the "All" chip restores the full list of videos.

## Test Steps

1. Navigate to `/dashboard/` with 3 mocked videos and 1 mocked playlist.
2. Click the playlist chip **"My Test Playlist"** — grid should show only the 2 videos in that playlist.
3. Click the **"All"** chip — grid should restore all 3 videos.

## Architecture

- **Fake Firebase auth**: `add_init_script` intercepts `onAuthStateChanged` to inject a fake authenticated user — no real credentials required.
- **Route interception**: Playwright mocks all relevant API endpoints:
  - `GET **/api/me/videos` → 3 deterministic videos (Video Alpha, Video Beta, Video Gamma)
  - `GET **/api/me/playlists` → 1 playlist (containing Video Alpha and Video Beta)
  - `GET **/api/playlists/<id>` → playlist detail with 2 videos
- **Page Object**: `DashboardPage` encapsulates all UI interactions.
- **No hardcoded URLs**: `WebConfig` provides the base URL from environment.

## Files

| File | Description |
|------|-------------|
| `test_mytube_521.py` | Main test file with 3 tests |
| `config.yaml` | Test metadata (type, framework, platform) |
| `README.md` | This file |

## How to Run Locally

```bash
# From the repository root
cd /path/to/mytube

# Install dependencies
pip install -r testing/requirements.txt
playwright install chromium

# Run the tests
pytest testing/tests/MYTUBE-521/test_mytube_521.py -v
```

Set the `WEB_BASE_URL` environment variable to point to your deployed instance, or the default from `WebConfig` will be used.
