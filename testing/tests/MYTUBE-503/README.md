# MYTUBE-503: SiteHeader utility area — theme toggle button dimensions and icons

## Objective

Ensure the theme toggle button in the SiteHeader utility area matches the specified
circular dimensions (40×40 px) and displays the correct icon for each theme state
(MoonIcon in light mode, SunIcon in dark mode), and that clicking the button swaps
the icon correctly.

## Preconditions

- The deployed web application is accessible at the URL defined by `WEB_BASE_URL` or `APP_URL`.
- Playwright with Chromium is installed in the test environment.
- The SiteHeader with the theme toggle button must be rendered on the homepage.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEB_BASE_URL` / `APP_URL` | ✅ Yes | Base URL of the deployed web app (e.g. `https://ai-teammate.github.io/mytube`). |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

1. **Navigate to the homepage** — load `GET /` and wait for `networkidle`.
2. **Locate the theme toggle button** — find `header button[aria-label^='Switch to']`.
3. **Inspect button dimensions** — assert width = 40 px and height = 40 px (±1 px tolerance).
4. **Inspect button shape** — assert `border-radius >= width/2` (circular/`rounded-full`).
5. **Verify MoonIcon in light mode** — assert SVG path `M21 12.79…` is present.
6. **Verify SunIcon in dark mode** — assert SVG `cx="12" cy="12"` + rays is present.
7. **Toggle from light → dark** — click button, assert SunIcon appears.
8. **Toggle from dark → light** — click button, assert MoonIcon appears.

## Expected Result

- The theme toggle button is a circle with dimensions **40×40 pixels**.
- In **light mode** the button displays a **MoonIcon** (crescent moon SVG path).
- In **dark mode** the button displays a **SunIcon** (circle + rays SVG).
- After each toggle click, the icon swaps to the opposite icon.

## How to Run Locally

```bash
# From the repository root
export WEB_BASE_URL=https://ai-teammate.github.io/mytube
cd testing
pytest tests/MYTUBE-503/test_mytube_503.py -v
```

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_503.py` | Playwright test implementation |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
