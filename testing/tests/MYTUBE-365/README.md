# MYTUBE-365: Interact with inputs in mobile viewport — visibility and focus states are correct

## Objective

Verify that text visibility and contrast are maintained on mobile devices and during element
focus. Specifically, the focus state must not change text or background color in a way that
makes content invisible.

## Preconditions

- The deployed web application is accessible at the URL defined by `WEB_BASE_URL`.
- Playwright with Chromium is installed in the test environment.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEB_BASE_URL` | ✅ Yes | Base URL of the deployed web app (e.g. `https://ai-teammate.github.io/mytube`). |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

1. **Open the site at 375 px mobile viewport** — Navigate to the home page with a 375 × 812 px
   viewport (iPhone SE) and a mobile user-agent string. Assert the search input
   (`aria-label="Search query"`) is visible.
2. **Open the search bar / focus on input** — Click the search input to focus it, then type
   sample text (`"hello world"`) to trigger any `:focus` CSS rules.
3. **Type text into the focused input** — After typing, read computed `color` and
   `backgroundColor` via `getComputedStyle`. Assert the text-color alpha is > 0 (not
   transparent) and the WCAG contrast ratio between text and background exceeds 3.0:1.
4. **Compare pre- and post-focus colors** — Blur the input, capture pre-focus computed styles,
   then re-focus and re-capture. Assert that the `:focus` rule does not zero out the text
   alpha or create a contrast ratio ≤ 3.0:1.

## Expected Result

- The search input is present and visible at 375 px mobile width.
- Text typed into the focused input remains visible (contrast ratio > 3.0:1; text alpha > 0).
- The focus state (`focus:outline-none focus:border-blue-500`) does not alter text or background
  color in a way that makes typed content invisible.

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_365.py` | Playwright test implementation |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
