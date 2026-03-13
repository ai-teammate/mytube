# MYTUBE-563 — Page scroll via touch swipe — content moves immediately on the first swipe

## Objective

Verify that touch-based scrolling on mobile devices responds immediately on the
first swipe gesture, with no silent failure or need for multiple attempts.

## Linked Bug

MYTUBE-537 — Root cause: `overflow: hidden` on `.shell` and `.page-wrap` in
`globals.css` creates implicit CSS scroll containers that silently consume
touch/wheel scroll events before they reach the document root.

Fix applied: `overflow: clip` on `.shell` and `overflow-x: clip` on `.page-wrap`.

## Approach

Three-layer test strategy:

| Layer | Type | What is verified |
|-------|------|-----------------|
| A — CSS source | Static analysis | `globals.css` contains `overflow: clip` on `.shell` and `overflow-x: clip` on `.page-wrap`; neither uses the broken `overflow: hidden` value. |
| B — Fixture browser | Playwright / mobile emulation | A self-contained HTML page replicates the `.page-wrap`/`.shell` layout. A mobile Chromium context (375×812, `has_touch=True`) asserts: (1) computed `overflow` on `.shell` is `clip`; (2) a pure touch-event swipe results in `window.scrollY > 0`, confirming events propagate to the document root. |
| C — Live browser | Playwright / deployed app | Navigates to the deployed homepage. Asserts computed `overflow` on `.shell` is `clip` and the document is scrollable after a swipe gesture. |

## Steps

1. Navigate to any page using the AppShell (e.g., Homepage).
2. Perform a single vertical swipe gesture on the screen.

## Expected Result

The page content scrolls immediately in sync with the touch movement.

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_URL` / `WEB_BASE_URL` | Yes | Base URL of the deployed web app. Default: `https://ai-teammate.github.io/mytube` |
| `PLAYWRIGHT_HEADLESS` | No | Run headless (default: `true`). |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms (default: `0`). |

## Running the Tests

```bash
# Against the deployed GitHub Pages app (default):
pytest testing/tests/MYTUBE-563/test_mytube_563.py -v

# Against a local dev server:
WEB_BASE_URL=http://localhost:3000 pytest testing/tests/MYTUBE-563/test_mytube_563.py -v
```

## Expected Output

```
PASSED  TestCSSSourceOverflowClip::test_shell_has_overflow_clip_not_hidden
PASSED  TestCSSSourceOverflowClip::test_page_wrap_has_overflow_x_clip_not_hidden
PASSED  TestTouchScrollFixture::test_fixture_shell_computed_overflow_is_clip
PASSED  TestTouchScrollFixture::test_fixture_touch_swipe_scrolls_page
PASSED  TestTouchScrollLive::test_live_shell_computed_overflow_is_clip
PASSED  TestTouchScrollLive::test_live_touch_swipe_scrolls_document
```
