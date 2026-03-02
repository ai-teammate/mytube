# MYTUBE-146 — Load public video watch page: Video.js player initializes and HLS stream plays

## What this test verifies

Navigates to `/v/<id>` for a video with `status='ready'` and asserts:

1. The `[data-vjs-player]` container is visible in the DOM.
2. A `<video class="video-js">` element is present.
3. Video.js has fully initialised (`vjs-paused` or `vjs-playing` class applied).
4. The `.vjs-control-bar` is visible.
5. A network request for the HLS manifest (`.m3u8`) is fired.
6. The "Video not found." error message is absent.
7. The video title `<h1>` is non-empty.

## Prerequisites

- Python 3.9+
- `pytest` and `playwright` installed (see below)
- The web app must be running and reachable at `WEB_BASE_URL`
- The backend API must be reachable at `API_BASE_URL`
- At least one video with `status='ready'` and a valid `hls_manifest_url` must exist

## Install dependencies

```bash
pip install pytest playwright
playwright install chromium
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app |
| `API_BASE_URL` | No | `http://localhost:8080` | Base URL of the backend API |
| `MYTUBE_146_VIDEO_ID` | No | *(auto-discovered)* | UUID of a video with status='ready'. If set, skips API discovery. |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Set to `false` to run browser with UI |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms |

## Run the test

From the repository root:

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-146/test_mytube_146.py -v
```

With environment overrides:

```bash
APP_URL=https://ai-teammate.github.io/mytube \
API_BASE_URL=https://api.example.com \
MYTUBE_146_VIDEO_ID=<uuid-of-ready-video> \
pytest testing/tests/MYTUBE-146/test_mytube_146.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-146/test_mytube_146.py::TestVideoWatchPagePlayerInit::test_player_container_visible PASSED
testing/tests/MYTUBE-146/test_mytube_146.py::TestVideoWatchPagePlayerInit::test_video_element_present PASSED
testing/tests/MYTUBE-146/test_mytube_146.py::TestVideoWatchPagePlayerInit::test_player_initialised PASSED
testing/tests/MYTUBE-146/test_mytube_146.py::TestVideoWatchPagePlayerInit::test_control_bar_visible PASSED
testing/tests/MYTUBE-146/test_mytube_146.py::TestVideoWatchPagePlayerInit::test_hls_manifest_requested PASSED
testing/tests/MYTUBE-146/test_mytube_146.py::TestVideoWatchPagePlayerInit::test_video_not_found_message_absent PASSED
testing/tests/MYTUBE-146/test_mytube_146.py::TestVideoWatchPagePlayerInit::test_video_title_displayed PASSED

7 passed in X.XXs
```
