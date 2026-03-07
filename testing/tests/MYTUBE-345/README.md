# MYTUBE-345 — Navigate header using keyboard: focus moves correctly through links

## Objective

Verify that the App Shell navigation (`SiteHeader`) is fully accessible via keyboard controls. A user who relies on the Tab key must be able to navigate through all interactive header elements in the correct logical order, with a visible focus indicator on each element.

## Test Approach

Uses Playwright with Chromium in a desktop viewport (1280 × 720) so that the desktop primary navigation (`nav[aria-label="Primary navigation"]`) is rendered and visible.

For a guest (unauthenticated) user, the expected focus order within `SiteHeader` is:

| Tab # | Element |
|-------|---------|
| 1 | Logo link — `<a>` with text "mytube" |
| 2 | Search input — `input[type="search"]` |
| 3 | Search submit button — `button[type="submit"]` |
| 4 | Home nav link — first `<a>` inside `nav[aria-label="Primary navigation"]` |

The test:
- Presses Tab from the document body and tracks every element that receives focus inside `<header>`, up to a safety limit of 30 tabs.
- Asserts the four expected elements appear in the correct order.
- For each element, asserts that `:focus-visible` is `true`.
- For elements that do not suppress the native outline, asserts the computed `outline-width` is non-zero.

## Page Object

`SiteHeaderKeyboardPage` (and the `FocusedElementInfo` dataclass) live in:

```
testing/components/pages/site_header/site_header_keyboard_page.py
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app | `https://ai-teammate.github.io/mytube` |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

## Running the Test

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-345/test_mytube_345.py -v
```
