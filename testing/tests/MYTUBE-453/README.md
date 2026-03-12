# MYTUBE-453: Hero CTA Browse Library — smooth scroll to video grid

## Objective

Verify that clicking the "Browse Library" ghost button in the hero section triggers a smooth
scroll that moves the viewport to the video grid (content area) of the homepage.

## Preconditions

- The deployed web application is accessible at the URL defined by `WEB_BASE_URL` or `APP_URL`.
- Playwright with Chromium is installed in the test environment.
- The hero section with the "Browse Library" CTA must be rendered on the homepage.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEB_BASE_URL` / `APP_URL` | ✅ Yes | Base URL of the deployed web app (e.g. `https://ai-teammate.github.io/mytube`). |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

1. **Navigate to the homepage** — load `GET /` and wait for `networkidle`.
2. **Assert "Browse Library" button is present** — the hero section CTA must be visible.
3. **Scroll back to the top** — establish a clean `scrollY = 0` baseline.
4. **Click "Browse Library"** — trigger the smooth-scroll behaviour.
5. **Wait for scroll animation** — allow 1 500 ms for the animation to complete.
6. **Assert scrollY increased** — the page must have scrolled downward.
7. **Assert video grid section is near the viewport top** — the target section's bounding-box
   top must fall within 1.5 × viewport height of the current viewport top.

## Expected Result

After clicking "Browse Library", the page scrolls down and the video grid section
(`section[aria-labelledby='recently-uploaded-heading']` or `most-viewed-heading`) is
positioned at or near the top of the visible viewport.

## How to Run Locally

```bash
# From the repository root
export WEB_BASE_URL=https://ai-teammate.github.io/mytube
cd testing
pytest tests/MYTUBE-453/test_mytube_453.py -v
```

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_453.py` | Playwright test implementation |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
