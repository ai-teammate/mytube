# MYTUBE-514: Video metadata and tags — meta line styling and pill components

## Objective

Verify the styling of the metadata line (category, views, date) and ensure tags
are rendered as pills matching the VideoCard component style.

## Preconditions

- The web source tree is present (for static analysis mode).
- Optionally, the deployed web application is accessible at `WEB_BASE_URL` or `APP_URL`
  for live Playwright validation.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEB_BASE_URL` / `APP_URL` | No | Base URL of the deployed web app. Enables live Playwright tests. |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

### Static Mode (always runs)

1. Read `WatchPageClient.module.css` from the web source tree.
2. Assert `.metaLine` has `font-size: 14px`.
3. Assert `.metaLine` has `color: var(--text-secondary)`.
4. Assert `.tagPill` has `border-radius: 999px`.
5. Assert `.tagPill` has `background: var(--accent-pill-bg)`.
6. Assert `.tagPill` has `color: var(--text-pill)`.
7. Read `VideoCard.module.css` and assert `.tagPill` tokens match WatchPageClient.

### Live Mode (when `APP_URL`/`WEB_BASE_URL` is set)

1. Discover a ready video URL from the API.
2. Navigate to the watch page.
3. Assert the meta-line element has computed `font-size: 14px`.
4. Assert tag pill elements are rendered with `border-radius >= 50px`.

## Expected Result

- `.metaLine` uses `font-size: 14px` and `color: var(--text-secondary)`.
- `.tagPill` is fully rounded (`border-radius: 999px`) and uses the correct design tokens.
- WatchPage `.tagPill` tokens match the VideoCard component exactly.

## How to Run Locally

```bash
# From the repository root
pytest testing/tests/MYTUBE-514/test_mytube_514.py -v
```

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_514.py` | Dual-mode test implementation (static + live Playwright) |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
