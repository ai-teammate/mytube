# MYTUBE-577 — Logo scaling across breakpoints: aspect ratio is maintained without distortion

## Objective

Ensure the logo renders correctly without stretching or distortion when the viewport size changes across desktop, tablet, and mobile breakpoints.

## Test Steps

1. Load the application on a desktop browser (1280px viewport).
2. Toggle the viewport to tablet (768px) and mobile (375px) widths.
3. Observe the rendered dimensions and aspect ratio of the logo SVG in the SiteHeader at each breakpoint.

## Expected Result

The logo maintains its original 1:1 aspect ratio and visual clarity at all breakpoints — no stretching or squashing. The logo remains visible with positive dimensions at every viewport width.

## Test Structure

### Part A — Static Source Analysis (always runs — no browser required)

1. **`LogoIcon.tsx` has a square `viewBox`** — e.g. `viewBox="0 0 40 40"`, guaranteeing an intrinsic 1:1 aspect ratio before CSS is applied.
2. **`SiteHeader.tsx` applies equal width and height Tailwind classes** to `LogoIcon` — e.g. `w-11 h-11`.
3. **Logo `<Link>` has `shrink-0`** — prevents the flex container from compressing the logo at narrow viewports.

### Part B — Live Playwright Assertions (skipped when app is unreachable)

Runs at three breakpoints (desktop 1280px, tablet 768px, mobile 375px):

4. Logo SVG bounding box aspect ratio ≈ 1:1 (tolerance ±5%) at desktop.
5. Logo SVG bounding box aspect ratio ≈ 1:1 at tablet.
6. Logo SVG bounding box aspect ratio ≈ 1:1 at mobile.
7. Logo is visible with positive dimensions at all three breakpoints.

## Prerequisites

- Python 3.10+
- `playwright` Python package with Chromium installed (`playwright install chromium`)
- `pytest`

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headlessly |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## How to Run

```bash
# From repo root
pytest testing/tests/MYTUBE-577/test_mytube_577.py -v
```
