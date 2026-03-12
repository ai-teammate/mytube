# MYTUBE-501 — SiteHeader search input: pill shape and focus ring styling

## Purpose

Verify that the search input in the SiteHeader has been updated to match the
new template design:

- The input field has a pill shape (`rounded-l-full` → 9999 px border-radius on left corners).
- Upon focus, a ring appears using the purple `--accent-logo` accent color.

## Test Steps

1. Navigate to the homepage (`/`). The SiteHeader is rendered on every page.
2. Locate the search input (`input[type="search"]` inside `<header>`) via the
   `SiteHeader` page-object's `search_input_locator()` helper.
3. Read computed `border-top-left-radius` and `border-bottom-left-radius` via
   `window.getComputedStyle` and assert each is ≥ 500 px (Tailwind
   `rounded-l-full` → 9999 px; 500 px threshold is robust against sub-pixel
   rounding).
4. Click into the input to trigger the focus state.
5. Read computed `borderColor`, convert to hex, and assert it matches
   `#6d40cb` (light mode) or `#9370db` (dark mode) — the `--accent-logo` CSS
   variable applied by `focus:border-[color:var(--accent-logo)]` in
   `SiteHeader.tsx`.

## Expected Result

- `border-top-left-radius` and `border-bottom-left-radius` ≥ 500 px (pill shape).
- After focus, computed `borderColor` hex equals `#6d40cb` or `#9370db`.

## Test Architecture

### Component layer

`testing/components/pages/site_header/site_header.py` — `SiteHeader` page
object extended with `search_input_locator()`. All CSS selector strings live
inside this component; tests never contain raw locator strings.

### Config layer

`testing/core/config/web_config.py` — `WebConfig` centralises environment
variable access (base URL, headless flag, slow-mo).

### Test layer (`test_mytube_501.py`)

| Test | Covers |
|------|--------|
| `test_search_input_is_visible` | Steps 1–2: search form rendered in SiteHeader |
| `test_search_input_has_pill_shape` | Step 3: `rounded-l-full` pill shape |
| `test_search_input_focus_ring_is_purple` | Steps 4–5: purple `--accent-logo` border on focus |

Computed CSS values are read via `element.evaluate()` to avoid brittleness
from Tailwind class names that may change.

## How to Run

```bash
cd /path/to/repo
pytest testing/tests/MYTUBE-501/ -v
```

Set `APP_URL` environment variable to override the default target URL
(`https://ai-teammate.github.io/mytube/`).
