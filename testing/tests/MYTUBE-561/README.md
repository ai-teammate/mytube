# MYTUBE-561 — Header transition at 768px breakpoint: layout adjusts without stacking errors

## Objective

Verify that the SiteHeader layout transitions correctly at the 768px viewport
breakpoint. At 800px, 768px, and 760px the header must render all flex children
in a single row with no horizontal overflow — confirming the MYTUBE-536
responsive fix is deployed and effective.

## Test Type

`ui` — dual-mode: static CSS class analysis + live Playwright viewport checks.

## Test Structure

### Part A — Static CSS Analysis (always runs)

Reads `web/src/components/SiteHeader.tsx` and `web/src/app/globals.css` to assert:

1. `px-4 sm:px-10` responsive padding is present on `<header>`.
2. `gap-3 sm:gap-6` responsive gap is present on `<header>`.
3. `min-h-[56px] sm:min-h-[88px]` responsive min-height is present on `<header>`.
4. `min-w-0` is present on the search `<form>` and/or `<input>`.
5. `overflow: hidden` (or `overflow-x: hidden`) is applied in the `.shell {}` rule
   in `globals.css`.

### Part B — Live Playwright Checks (requires reachable `APP_URL`)

Launches Chromium at three viewport widths and uses the `SiteHeader` page object
(`testing/components/pages/site_header/site_header.py`) to collect header layout
metrics, asserting:

- `overflowPx <= 0` — no horizontal overflow.
- `rowCount == 1` — all flex children remain in a single row (no wrapping/stacking).

Viewports tested: **800px**, **768px**, **760px**.

Live tests are automatically skipped when the deployed app is unreachable.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (`pip install playwright && playwright install chromium`)
- Repository checkout (for static analysis tests)

## Environment Variables

| Variable            | Required for | Description                                                     |
|---------------------|--------------|-----------------------------------------------------------------|
| `APP_URL`           | Live tests   | Base URL of the deployed web app.                              |
| `WEB_BASE_URL`      | Live tests   | Alias for `APP_URL`.                                            |
| `PLAYWRIGHT_HEADLESS` | Live tests | Run browser headless. Default: `true`.                         |
| `PLAYWRIGHT_SLOW_MO`  | Live tests | Slow-motion delay in ms for debugging. Default: `0`.           |

Default `APP_URL`: `https://ai-teammate.github.io/mytube`

## Running

```bash
# From the repository root:
pytest testing/tests/MYTUBE-561/test_mytube_561.py -v
```
