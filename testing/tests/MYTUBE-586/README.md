# MYTUBE-586 — Mobile menu state management: menu closes automatically on viewport expansion

## Objective

Verify that the mobile navigation menu (hamburger menu) is automatically dismissed when the
viewport is resized from mobile (375px) to desktop width (1024px). The desktop primary
navigation (Home, My Videos) should become visible after the resize.

## Test Type

`e2e` — live Playwright end-to-end test against the deployed web app.

## Test Steps

1. Navigate to the homepage at a mobile viewport (375×812px).
2. Click the hamburger menu icon to open the mobile navigation panel.
3. Resize the viewport to desktop width (1024px).
4. Assert the mobile nav panel is no longer visible.
5. Assert the desktop primary navigation (Home, My Videos) is visible.

## Expected Result

The `SiteHeader.tsx` resize event handler calls `setMobileNavOpen(false)` when
`window.innerWidth >= 640`, automatically dismissing the mobile nav. The desktop
`nav[aria-label='Primary navigation']` with Home and My Videos links becomes visible.

## Architecture

- `WebConfig` (`testing/core/config/web_config.py`) centralises env var access — no hardcoded URLs.
- `SiteHeader` (`testing/components/pages/site_header/site_header.py`) encapsulates all selectors
  and DOM interactions (hamburger click, mobile/desktop nav visibility checks).
- Module-scoped pytest fixtures manage the browser lifecycle.
- No raw Playwright locators in the test file.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (`pip install playwright && playwright install chromium`)

## Environment Variables

| Variable              | Description                                                 |
|-----------------------|-------------------------------------------------------------|
| `APP_URL`             | Base URL of the deployed web app.                          |
| `WEB_BASE_URL`        | Alias for `APP_URL`.                                        |
| `PLAYWRIGHT_HEADLESS` | Run browser headless. Default: `true`.                     |
| `PLAYWRIGHT_SLOW_MO`  | Slow-motion delay in ms for debugging. Default: `0`.       |

Default `APP_URL`: `https://ai-teammate.github.io/mytube`

## Running

```bash
# From the repository root:
pytest testing/tests/MYTUBE-586/test_mytube_586.py -v
```
