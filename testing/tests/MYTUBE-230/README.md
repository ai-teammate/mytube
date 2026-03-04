# MYTUBE-230 — View public playlist page: videos displayed sequentially by position

## What this test does

Verifies that the public playlist page (`/pl/:id`) renders video items in ascending position order, and that the page loads without authentication.

The test uses Playwright route interception to inject a deterministic mock API response containing three videos at positions 1, 2, and 3. No database access or Firebase credentials are required.

## Dependencies

```
playwright>=1.40.0
pytest>=7.0.0
```

## Install

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed frontend base URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Set to `false` to see the browser |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms for debugging |

## Run

From the repository root:

```bash
cd /path/to/mytube
pytest testing/tests/MYTUBE-230/test_mytube_230.py -v
```

Or with a custom frontend URL:

```bash
APP_URL=http://localhost:3000 pytest testing/tests/MYTUBE-230/test_mytube_230.py -v
```

## Expected output when passing

```
testing/tests/MYTUBE-230/test_mytube_230.py::TestPublicPlaylistPageLoads::test_page_loads_without_authentication PASSED
testing/tests/MYTUBE-230/test_mytube_230.py::TestPublicPlaylistPageLoads::test_queue_panel_is_visible PASSED
testing/tests/MYTUBE-230/test_mytube_230.py::TestPublicPlaylistPageLoads::test_page_title_matches_playlist_title PASSED
testing/tests/MYTUBE-230/test_mytube_230.py::TestPlaylistVideoOrdering::test_queue_has_correct_number_of_items PASSED
testing/tests/MYTUBE-230/test_mytube_230.py::TestPlaylistVideoOrdering::test_videos_displayed_in_ascending_position_order PASSED
testing/tests/MYTUBE-230/test_mytube_230.py::TestPlaylistVideoOrdering::test_first_position_video_is_first_in_queue PASSED
testing/tests/MYTUBE-230/test_mytube_230.py::TestPlaylistVideoOrdering::test_last_position_video_is_last_in_queue PASSED
testing/tests/MYTUBE-230/test_mytube_230.py::TestPlaylistVideoOrdering::test_first_queue_item_is_marked_as_currently_playing PASSED

8 passed in <time>s
```

## Architecture

- **Page Object**: `testing/components/pages/playlist_page/playlist_page.py`
- **Config**: `testing/core/config/web_config.py`
- **Framework**: Playwright (sync API, Chromium)
- **API mock**: Playwright route interception (`page.route()`)
