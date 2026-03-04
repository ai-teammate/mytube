# MYTUBE-234 — View user profile: public playlists are displayed

Verifies that the user profile page (`/u/tester`) shows the user's public
playlists with title and video count, and that each playlist links to
`/pl/[id]`.

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed web app base URL |
| `API_BASE_URL` | `http://localhost:8081` | Backend API base URL (used to check for test data) |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Preconditions

User `tester` must have at least one public playlist in the deployed
environment. If no playlists are found the test is automatically skipped.

## Running the test

From the repository root:

```bash
cd /path/to/mytube
API_BASE_URL=https://mytube-api-80693608388.us-central1.run.app \
  pytest testing/tests/MYTUBE-234/test_mytube_234.py -v
```

## Expected output (passing)

```
PASSED test_playlists_tab_is_present
PASSED test_playlists_grid_has_items
PASSED test_each_playlist_has_non_empty_title
PASSED test_each_playlist_shows_video_count
PASSED test_each_playlist_links_to_playlist_page
```
