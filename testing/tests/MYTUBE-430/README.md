# MYTUBE-430 — Inspect global CSS: light theme design tokens are correctly defined

## Objective

Verify that all required light-theme CSS design tokens are present with the correct
values in `web/src/app/globals.css`.

## Test Type

`css` — static stylesheet analysis (no browser required).

## Test Structure

The test reads `web/src/app/globals.css` directly via
`testing/components/pages/css_globals_page/css_globals_page.py` and parses the
`:root` block with a regex. It asserts the exact values of the five required tokens:

| Token | Expected value |
|---|---|
| `--bg-page` | `#f8f9fa` |
| `--bg-content` | `#ffffff` |
| `--text-primary` | `#222222` |
| `--accent-cta` | `#62c235` |
| `--shadow-main` | `0 8px 24px rgba(0,0,0,0.06)` |

Dark-theme overrides (`body[data-theme="dark"]`) are intentionally excluded — only
the default `:root` values are checked.

## Prerequisites

- Python 3.9+
- `pytest` — `pip install pytest`

No browser, no external services, and no environment variables are required.

## Running the Test

From the repository root:

```bash
pytest testing/tests/MYTUBE-430/test_mytube_430.py -v
```

## Expected Output

```
PASSED  TestLightThemeDesignTokens::test_bg_page_token
PASSED  TestLightThemeDesignTokens::test_bg_content_token
PASSED  TestLightThemeDesignTokens::test_text_primary_token
PASSED  TestLightThemeDesignTokens::test_accent_cta_token
PASSED  TestLightThemeDesignTokens::test_shadow_main_token
```
