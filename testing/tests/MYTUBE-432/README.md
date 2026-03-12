# MYTUBE-432

Test: Verify font stack — Inter font is imported and applied to the document

## Objective

Ensure that the Inter font family is successfully imported and set as the primary
font for the application.

## Steps

1. Open the application and inspect the `<html>` or `<body>` element.
2. Check the `font-family` property in the Computed styles tab.
3. Open the Network tab and filter by "Font" to check for Inter font files or
   the Google Fonts CSS import.

## Expected Result

- `font-family` is correctly set to `"Inter", "Roboto", "Open Sans", sans-serif`.
- The Inter font (weights 400–800) is successfully loaded from the external or local source.

## Test Cases

| # | Test | Description |
|---|------|-------------|
| 1 | `test_font_inter_css_variable_is_set` | Verifies `--font-inter` CSS variable is set on `<html>` element |
| 2 | `test_body_font_family_contains_fallback_fonts` | Verifies computed `font-family` on `<body>` contains "Roboto" and "Open Sans" fallbacks |
| 3 | `test_inter_font_declared_for_all_required_weights` | Verifies Inter `@font-face` rules declared for all required weights (400, 500, 600, 700, 800) |

## How to Run Locally

1. Install Python dependencies (from repository root):

```bash
python3 -m pip install -r testing/requirements.txt
```

2. Install Playwright browsers:

```bash
playwright install chromium
```

3. Run the test:

```bash
pytest testing/tests/MYTUBE-432/test_mytube_432.py -q
```

## Environment Variables

- `APP_URL` or `WEB_BASE_URL`: Base URL of the web app (default: `https://ai-teammate.github.io/mytube`)
- `PLAYWRIGHT_HEADLESS`: Set to `false` to run in headed mode (default: `true`)
- `PLAYWRIGHT_SLOW_MO`: Milliseconds to slow down Playwright operations (default: `0`)
