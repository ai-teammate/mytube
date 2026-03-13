# MYTUBE-562 — Page scroll via mouse wheel

Regression guard for [MYTUBE-537]: verifies that `.shell` and `.page-wrap` in
`globals.css` use `overflow: clip` / `overflow-x: clip` and do **not** declare
`overflow: hidden`, preventing the implicit CSS scroll container that blocked
first-attempt mouse-wheel scrolling.

## Objective

Confirm that scrolling via mouse wheel or trackpad responds immediately on the
first attempt across all pages using the AppShell.

## Root Cause (MYTUBE-537)

`overflow: hidden` on `.shell` and `.page-wrap` creates implicit CSS scroll
containers (per CSS Overflow spec level 3) that silently consume wheel/touch
scroll events before they reach the document root. The fix changes both
properties to `overflow: clip`, which provides identical visual clipping without
becoming a scroll container.

## Modes

| Mode | When it runs | Tests |
|------|-------------|-------|
| Static CSS analysis | Always | 4 |
| Live Playwright scroll | When `APP_URL` is set | 1 |

### Static analysis (always runs)

Parses `web/src/app/globals.css` and asserts:

- `.shell` declares `overflow: clip` and does **not** declare `overflow: hidden`
- `.page-wrap` declares `overflow-x: clip` and does **not** declare `overflow-x: hidden`

### Live Playwright (requires `APP_URL`)

Navigates to the deployed homepage with a narrow viewport (1280×700) that
forces scrollable content, dispatches a single trusted wheel event via
`page.mouse.wheel(0, 300)`, and asserts `scrollY` increases — confirming the
page responds to the very first scroll attempt.

## Run

```bash
# Static analysis only (default)
pytest testing/tests/MYTUBE-562/test_mytube_562.py -v

# Live mode (requires a running app)
APP_URL=http://localhost:3000 pytest testing/tests/MYTUBE-562/test_mytube_562.py -v
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app | `https://ai-teammate.github.io/mytube` |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

## Files

| File | Purpose |
|------|---------|
| `test_mytube_562.py` | Test implementation |
| `config.yaml` | Test configuration (timeouts, browser, ports) |
| `__init__.py` | Package marker |
