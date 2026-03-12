# MYTUBE-494: Hero 'Browse Library' button accessibility — focus and activation via keyboard triggers smooth scroll

## Objective

Verify that the "Browse Library" button in the hero section is keyboard-accessible:
it can be reached via the Tab key, displays a visible focus indicator (`:focus-visible`),
and pressing Enter while it is focused triggers a smooth scroll animation that positions
the viewport at the top of the video grid section.

## Preconditions

- The deployed web application is accessible at the URL defined by `WEB_BASE_URL` or `APP_URL`.
- Playwright with Chromium is installed in the test environment.
- The "Browse Library" CTA button must be rendered in the hero section (MYTUBE-470 fix applied).

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEB_BASE_URL` / `APP_URL` | ✅ Yes | Base URL of the deployed web app (e.g. `https://ai-teammate.github.io/mytube`). |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

1. **Navigate to the homepage** — load `GET /` and wait for `networkidle`.
2. **Assert "Browse Library" button is present** — the hero section CTA must be visible (pre-condition).
3. **Scroll back to the top** — establish a clean `scrollY = 0` baseline and reset focus to document body.
4. **Tab to "Browse Library"** — press Tab repeatedly (up to 40 times) until the button receives focus.
5. **Verify `:focus-visible` state** — assert the focused element matches the `:focus-visible` CSS pseudo-class.
6. **Press Enter** — activate the button via keyboard.
7. **Wait for scroll animation** — allow 1 500 ms for the smooth-scroll animation to complete.
8. **Assert scrollY increased** — the page must have scrolled downward.
9. **Assert video grid section is near the viewport** — the section's bounding-box top must fall within 1.5 × viewport height.

## Expected Result

The "Browse Library" button is reachable via Tab navigation and displays a visible focus indicator.
Pressing Enter triggers a smooth scroll so that the video grid section
(`section[aria-labelledby='recently-uploaded-heading']` or `most-viewed-heading`) is
positioned at or near the top of the visible viewport.

## Linked Bug

- **MYTUBE-470** — Hero section missing 'Browse Library' CTA button — smooth scroll to video grid not functional. *(Fixed)*

## How to Run Locally

```bash
# From the repository root
export WEB_BASE_URL=https://ai-teammate.github.io/mytube
cd testing
pytest tests/MYTUBE-494/test_mytube_494.py -v
```

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_494.py` | Playwright test implementation |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
| `README.md` | This file — test case documentation |
