# MYTUBE-585 — Mobile menu toggle accessibility: button includes required ARIA attributes

## Objective

Ensure the hamburger menu button is programmatically detectable by automated testing tools
and assistive technology on mobile viewports (≤640px). Specifically, the button must
have `aria-label`, `data-testid`, and a correctly toggling `aria-expanded` attribute.

## Preconditions

- Viewport width is set to 640px or less (375×812px iPhone-like mobile size).
- The deployed application is reachable at `APP_URL` / `WEB_BASE_URL`.

## Test Steps

1. Set viewport to mobile width (≤640px) and navigate to the homepage.
2. Locate the hamburger menu button in the SiteHeader via aria-label.
3. Verify the button has an `aria-label` containing 'menu', 'nav', or 'hamburger'.
4. Verify the button has a `data-testid` attribute for 'hamburger' or 'mobile-menu'.
5. Observe the initial value of `aria-expanded` (must be `'false'`).
6. Click the button to open the menu and re-verify `aria-expanded` is now `'true'`.

## Expected Result

The hamburger button:
- Is present and visible on mobile viewports (≤640px).
- Has an `aria-label` containing one of: 'menu', 'nav', 'hamburger'.
- Has a `data-testid` containing 'hamburger' or 'mobile-menu'.
- Has `aria-expanded="false"` initially (menu closed).
- Toggles `aria-expanded` to `"true"` after being clicked (menu opened).

## Test Structure

Uses the `SiteHeader` page object (`testing/components/pages/site_header/site_header.py`)
for locating the hamburger button. The test is skipped when the deployed app is unreachable.

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
pytest testing/tests/MYTUBE-585/test_mytube_585.py -v
```
