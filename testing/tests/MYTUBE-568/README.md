# MYTUBE-568: Video player container — fixed 16:9 aspect ratio prevents layout jump

## Objective

Verify that the video player container uses a fixed 16:9 aspect ratio to eliminate
Cumulative Layout Shift (CLS) when the Video.js player mounts asynchronously.

## Preconditions

- The deployed web application is accessible at the URL defined by `WEB_BASE_URL` or `APP_URL`.
- Playwright with Chromium is installed in the test environment.
- The `WatchPageClient.module.css` source file is present in the repository.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEB_BASE_URL` / `APP_URL` | No | Base URL of the deployed web app. Default: `https://ai-teammate.github.io/mytube`. |
| `API_BASE_URL` | No | Backend API base URL for video discovery. Default: `http://localhost:8081`. |
| `TEST_VIDEO_ID` | No | Override video ID for live Playwright tests. Skips API discovery when set. |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

1. **Navigate to a video watch page** — load `/v/:id` and wait for DOM content loaded.
2. **Observe the player container during loading** — measure container height before Video.js mounts.
3. **Inspect CSS properties** — assert `aspect-ratio: 16/9`, `width: 100%`, and `overflow: hidden` on `.player` in `WatchPageClient.module.css`.
4. **Monitor for layout jump** — verify the container height does not change by more than 5 px after Video.js initialises.

## Expected Result

The `.player` container declares `aspect-ratio: 16 / 9` (or `padding-top: 56.25%` as fallback).
No layout jump (CLS) occurs when the async Video.js player content resolves.

## How to Run Locally

```bash
# From the repository root
export WEB_BASE_URL=https://ai-teammate.github.io/mytube
pytest testing/tests/MYTUBE-568/test_mytube_568.py -v
```

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_568.py` | Dual-mode test: static CSS analysis + live Playwright aspect-ratio verification |
| `config.yaml` | Test metadata (framework, platform, dependencies) |

## Architecture

- Static CSS analysis (always runs, no browser required): reads `WatchPageClient.module.css` directly.
- Live Playwright tests (skipped when app is unreachable): use `WatchPage` page object and `VideoApiService` for video discovery.
