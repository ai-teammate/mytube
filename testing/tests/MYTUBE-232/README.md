# MYTUBE-232 — Playlist Auto-Advance Test

Verifies that when a video finishes on the playlist page (`/pl/:id`), the player
automatically advances to the next video in the queue.

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` or `WEB_BASE_URL` | No | `https://ai-teammate.github.io/mytube` | Deployed frontend URL |
| `API_BASE_URL` | No | `http://localhost:8080` | Backend API URL for live playlist discovery |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Run browser headless (`false` for local debug) |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms |

When `API_BASE_URL` is set and a suitable playlist is found, the test runs in **live
mode** against the real deployed data.  Otherwise it runs in **mock mode** using
Playwright request interception to serve a fake 2-video playlist.

## How to run

```bash
cd /path/to/repo

# Mock mode (no API needed)
pytest testing/tests/MYTUBE-232/test_mytube_232.py -v

# Live mode (requires deployed API with tester playlists)
API_BASE_URL=https://mytube-api-80693608388.us-central1.run.app \
  pytest testing/tests/MYTUBE-232/test_mytube_232.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-232/test_mytube_232.py::TestPlaylistAutoAdvance::test_playlist_page_loads_with_queue PASSED
testing/tests/MYTUBE-232/test_mytube_232.py::TestPlaylistAutoAdvance::test_first_video_is_initially_current PASSED
testing/tests/MYTUBE-232/test_mytube_232.py::TestPlaylistAutoAdvance::test_now_playing_shows_first_video PASSED
testing/tests/MYTUBE-232/test_mytube_232.py::TestPlaylistAutoAdvance::test_player_auto_advances_to_next_video_on_end PASSED
testing/tests/MYTUBE-232/test_mytube_232.py::TestPlaylistAutoAdvance::test_end_of_playlist_shown_after_all_videos PASSED
```

## Test modes

### Mock mode (default)

API calls to the backend are intercepted by Playwright's request routing.
A fake 2-video playlist is returned with `hls_manifest_url: null` for each
video.  This causes the `PlaylistVideoPlayerWrapper` to render the
"Video not available." overlay with a "Skip" button.  Clicking "Skip" calls
`onEnded()` directly — the same `handleVideoEnded()` function triggered by the
native video `ended` event — exercising the full auto-advance state machine.

### Live mode

A real playlist belonging to the `tester` user is discovered via the API.
The `ended` event is dispatched programmatically to the `<video>` element to
simulate the user watching through to the end.
