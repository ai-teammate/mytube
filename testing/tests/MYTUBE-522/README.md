# MYTUBE-522 — Dashboard video grid layout: responsive grid configuration

## Objective

Verify that the CSS grid configuration for the redesigned video dashboard is correct.  
The video grid container below the toolbar must use:

- `grid-template-columns: repeat(auto-fill, minmax(220px, 1fr))`
- `gap: 16px`

## Test Approach

### Fixture mode (tests 1–3)

A local HTTP server serves a minimal HTML page that embeds the **actual**
`web/src/app/dashboard/_content.module.css` file loaded from disk at import
time. This ensures the fixture stays in sync with the real application CSS —
if a developer removes or changes the grid rule, tests 1–3 will fail
alongside test 4.

Playwright checks:

1. The `[data-testid="video-grid"]` element is present below the toolbar.
2. The authored `grid-template-columns` value on `.videoGrid` contains
   `auto-fill` and `220px`.
3. The computed `gap` on `.videoGrid` is `16px`.

### Live mode (test 4)

Playwright navigates to the deployed dashboard URL
(`https://ai-teammate.github.io/mytube/dashboard/`) and scans all loaded
`document.styleSheets` for the CSS rule. This works regardless of
authentication state because Next.js bundles CSS before `RequireAuth`
redirects the user.

## Component Layer

All locators and stylesheet-inspection logic are encapsulated in
`DashboardPage` (`testing/components/pages/dashboard_page/dashboard_page.py`):

| Method | Used by |
|---|---|
| `is_video_grid_present()` | test 1 |
| `wait_for_video_grid_visible()` | test 1 |
| `is_toolbar_present()` | test 1 |
| `get_video_grid_styles()` | tests 2–3 |
| `get_live_grid_rule()` | test 4 |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Files

| File | Purpose |
|---|---|
| `test_mytube_522.py` | Test implementation |
| `config.yaml` | Test metadata (type, framework, platform) |
| `README.md` | This file |
