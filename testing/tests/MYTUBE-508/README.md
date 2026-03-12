# MYTUBE-508 — Form input focus states: focus ring and border color apply accent styles

## Objective

Ensure that form inputs, selects, and textareas on the upload page display the
correct focus ring and border color when focused. Specifically, verify that
`.formControl:focus` and `.selectControl:focus` apply the accent-themed
`box-shadow` and `border-color`, and that base styles (`background`,
`border-radius`) are correctly set.

## Test Type

`web` — dual-mode: static CSS analysis (always runs) + live Playwright browser
tests (when `APP_URL` / `WEB_BASE_URL` is set).

## Test Structure

### Part A — Static CSS Analysis (always runs)

Reads `web/src/app/upload/upload.module.css` and `web/src/app/globals.css`
directly from the repository and verifies:

1. `.formControl:focus` declares `box-shadow: 0 0 0 3px rgba(109, 64, 203, 0.1)`.
2. `.formControl:focus` declares `border-color: var(--accent-logo)`.
3. `.selectControl:focus` declares `box-shadow: 0 0 0 3px rgba(109, 64, 203, 0.1)`.
4. `.selectControl:focus` declares `border-color: var(--accent-logo)`.
5. `.formControl` base declares `background: var(--bg-page)`.
6. `.formControl` base declares `border-radius: 12px`.
7. `.selectControl` base declares `background: var(--bg-page)`.
8. `.selectControl` base declares `border-radius: 12px`.
9. `globals.css` `:root` block defines the `--accent-logo` CSS variable.
10. `globals.css` `:root` block defines the `--bg-page` CSS variable.

### Part B — Live Playwright Tests (requires `APP_URL` / `WEB_BASE_URL`)

Launches a Chromium browser, navigates to `/upload`, and uses
`window.getComputedStyle` to verify resolved computed values for:

1. Title input (`#title`) focused `box-shadow` contains `rgba(109, 64, 203, 0.1)`.
2. Title input focused `borderColor` resolves to `rgb(109, 64, 203)`.
3. Title input `borderRadius` equals `12px`.
4. Description textarea (`#description`) focused `box-shadow`.
5. Description textarea focused `borderColor`.
6. Category select (`#categoryId`) focused `box-shadow`.
7. Tags input (`#tags`) focused `box-shadow`.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` Python package (for Part B)
- Chromium installed (`playwright install chromium`)

## Environment Variables

| Variable       | Required for | Description                                           |
|----------------|--------------|-------------------------------------------------------|
| `APP_URL`      | Part B only  | Base URL of the deployed application (e.g. `https://myapp.example.com`). |
| `WEB_BASE_URL` | Part B only  | Alternative to `APP_URL` for the base URL.            |

If neither variable is set, Part B tests are automatically skipped.

## Running the Tests

```bash
# Part A only (no browser or credentials needed):
pytest testing/tests/MYTUBE-508/test_mytube_508.py -v

# Both parts (against deployed app):
APP_URL=https://myapp.example.com pytest testing/tests/MYTUBE-508/test_mytube_508.py -v
```

## Expected Output

```
# Without APP_URL (static analysis only):
PASSED  TestFormControlFocusStatic::test_formcontrol_focus_box_shadow
PASSED  TestFormControlFocusStatic::test_formcontrol_focus_border_color
PASSED  TestFormControlFocusStatic::test_selectcontrol_focus_box_shadow
PASSED  TestFormControlFocusStatic::test_selectcontrol_focus_border_color
PASSED  TestFormControlFocusStatic::test_formcontrol_base_background
PASSED  TestFormControlFocusStatic::test_formcontrol_base_border_radius
PASSED  TestFormControlFocusStatic::test_selectcontrol_base_background
PASSED  TestFormControlFocusStatic::test_selectcontrol_base_border_radius
PASSED  TestFormControlFocusStatic::test_globals_css_defines_accent_logo
PASSED  TestFormControlFocusStatic::test_globals_css_defines_bg_page
SKIPPED TestFormControlFocusLive::test_title_input_focus_box_shadow       [no APP_URL]
SKIPPED TestFormControlFocusLive::test_title_input_focus_border_color
SKIPPED TestFormControlFocusLive::test_title_input_base_border_radius
SKIPPED TestFormControlFocusLive::test_description_textarea_focus_box_shadow
SKIPPED TestFormControlFocusLive::test_description_textarea_focus_border_color
SKIPPED TestFormControlFocusLive::test_category_select_focus_box_shadow
SKIPPED TestFormControlFocusLive::test_tags_input_focus_box_shadow
```

With `APP_URL` set, the 7 skipped tests run as live browser assertions.
