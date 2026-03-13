# MYTUBE-565 — Page Scroll After Navigation: Scroll Remains Responsive After Route Changes

## Objective

Verify that the scrolling fix introduced in MYTUBE-537 (replacing `overflow: hidden`
with `overflow: clip` on `.shell` and `.page-wrap` in `globals.css`) persists
across client-side navigation within the AppShell, and that scroll is responsive
immediately on the Watch page without needing multiple attempts.

## Test Type

`e2e` — Dual-layer: static CSS analysis (Layer A) + live Playwright browser test (Layer B).

## Test Structure

### Layer A — Static CSS Analysis (always runs, no browser required)

Reads `web/src/app/globals.css` and verifies that the MYTUBE-537 fix is in place:

1. `.page-wrap` declares `overflow-x: clip` (not `overflow-x: hidden`).
2. `.shell` declares `overflow: clip` (not `overflow: hidden`).
3. `.page-wrap` does NOT use any form of `overflow: hidden`.
4. `.shell` does NOT use any form of `overflow: hidden`.

CSS parsing is handled by the `CSSOverflowPage` component
(`testing/components/pages/css_overflow_page/css_overflow_page.py`).

### Layer B — Live Browser E2E (requires deployed app)

1. Opens the homepage in Chromium (1280×800 desktop viewport).
2. Finds the first video card link (`a[href*='/v/']`) and **clicks** it to trigger
   a client-side SPA route change (not a full reload).
3. Waits for the Watch page URL pattern (`**/v/**`) to be confirmed.
4. Resets scroll to top, then calls `window.scrollBy(0, 300)` immediately.
5. Asserts `window.scrollY > 0` — the viewport moved on the first attempt.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` with Chromium installed (`playwright install chromium`)
- Deployed app accessible via `WEB_BASE_URL`

## Environment Variables

| Variable             | Required for | Description                                     |
|----------------------|--------------|-------------------------------------------------|
| `WEB_BASE_URL`       | Layer B      | Base URL of the deployed app (e.g. `https://…`) |
| `PLAYWRIGHT_HEADLESS`| Layer B      | Run headless (default: `true`)                  |
| `PLAYWRIGHT_SLOW_MO` | Layer B      | Slow-motion delay in ms (default: `0`)          |

## Running the Tests

```bash
# Layer A only (no credentials or browser needed):
pytest testing/tests/MYTUBE-565/test_mytube_565.py::TestCSSOverflowFix -v

# All tests (Layer A + Layer B):
WEB_BASE_URL=https://your-app.example.com \
  pytest testing/tests/MYTUBE-565/test_mytube_565.py -v
```

## Expected Output

```
PASSED  TestCSSOverflowFix::test_page_wrap_overflow_x_is_clip
PASSED  TestCSSOverflowFix::test_shell_overflow_is_clip
PASSED  TestCSSOverflowFix::test_page_wrap_no_overflow_hidden
PASSED  TestCSSOverflowFix::test_shell_no_overflow_hidden
PASSED  TestScrollAfterNavigation::test_scroll_responds_immediately_after_route_change
```
