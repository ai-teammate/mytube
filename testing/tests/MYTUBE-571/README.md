# MYTUBE-571 — Lazy-load transitions: smooth 0.2s fade-in transition applied to appearing components

## Objective

Verify that lazily loaded VideoCard thumbnail images appear with a smooth CSS opacity
fade-in animation (0 → 1 over 0.2s with an ease function) rather than appearing
instantly.

## Test Type

`ui` — live Playwright (Chromium) test.

## Test Structure

Single test class `TestMytube571LazyLoadFadeTransition` with one end-to-end scenario:

1. **Navigate to the homepage** using the `HomePage` component.
2. **CSS fade-in rule present in stylesheets** — `VideoCardComponent.find_fade_css_rule()`
   asserts the rule from `VideoCard.module.css` is present in the deployed bundle.
3. **VideoCard images have the correct transition** — `VideoCardComponent.get_images_with_opacity_transition()`
   asserts `transitionProperty: opacity`, `transitionDuration: 0.2s`, and
   `transitionTimingFunction: ease` on all `#video-grid img` elements.
4. **Initial opacity is 0** — images not yet loaded have `opacity: 0`, confirming they
   are hidden before the fade-in.
5. **Post-load opacity is 1** — images that have loaded have `opacity: 1` after the
   `onLoad` callback fires.
6. **Scroll consistency** — after scrolling 600 px, newly visible VideoCard images
   retain the same `opacity 0.2s ease` transition.

## Implementation Confirmed

```css
/* web/src/components/VideoCard.module.css */
.thumb img        { opacity: 0; transition: opacity 0.2s; }
.thumb img.loaded { opacity: 1; }
```

The `VideoCard` component adds the `loaded` class via an `onLoad` callback, triggering
the 0 → 1 opacity fade.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (`pip install playwright && playwright install chromium`)
- Repository checkout

## Environment Variables

| Variable              | Required | Description                                              |
|-----------------------|----------|----------------------------------------------------------|
| `APP_URL`             | No       | Base URL of the deployed app (default: GitHub Pages URL) |
| `WEB_BASE_URL`        | No       | Alias for `APP_URL`                                      |
| `PLAYWRIGHT_HEADLESS` | No       | Run browser headless. Default: `true`                    |
| `PLAYWRIGHT_SLOW_MO`  | No       | Slow-motion delay in ms for debugging. Default: `0`      |

Default `APP_URL`: `https://ai-teammate.github.io/mytube`

## Running

```bash
# From the repository root:
pytest testing/tests/MYTUBE-571/test_mytube_571.py -v
```
