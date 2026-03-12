# MYTUBE-534 — Hero Visual Panel Thumbnail Fallback

## Description

Tests that the hero section visual panel correctly falls back to a runtime
video thumbnail (`recentVideos[0]?.thumbnailUrl`) when the static default image
(`image_9.png`) is absent, instead of showing a broken image or an empty
container.

## Ticket Reference

- **Jira**: MYTUBE-534
- **PR**: https://github.com/ai-teammate/mytube/pull/500

## Preconditions

- The deployed app (`https://ai-teammate.github.io/mytube`) is accessible.
- The homepage has at least one active video with a non-null `thumbnailUrl`.

When preconditions are not met the live test auto-skips (no false failures).
The fixture test always runs regardless of app availability.

## Test Modes

### Fixture mode (`test_fixture_visual_canvas_shows_img_not_placeholder`)

Always runs. Starts a local HTTP server that serves a minimal HTML page
replicating the expected post-fallback state:

- `<img alt="Video preview">` is visible in the visual canvas.
- `data-testid="canvas-placeholder"` is absent.
- `img.src` is non-empty.

### Live mode (`test_live_visual_panel_thumbnail_fallback`)

Navigates to the deployed homepage, waits for video data to load, then asserts:

- The visual canvas (`[class*='visualCanvas']`) is rendered.
- `<img alt="Video preview">` is visible with a non-empty `src`.
- `data-testid="canvas-placeholder"` is not visible.

Skipped automatically if the app is unreachable or no active videos are found.

## How to Run

```bash
# From the repository root
pytest testing/tests/MYTUBE-534/test_mytube_534.py -v
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed app base URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Architecture

- `WebConfig` (`testing/core/config/web_config.py`) — centralises env var access.
- `VisualPanelPage` (`testing/components/pages/visual_panel_page/`) — encapsulates
  all panel selectors (`visual_canvas`, `thumbnail_image`, `placeholder`).
- Playwright sync API with pytest module-scoped fixtures.
