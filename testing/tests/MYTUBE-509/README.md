# MYTUBE-509 — Progress bar redesign styling: green gradient and rounded track

## Objective

Verify the upload progress bar matches the redesign specification:
- `.progressShell` has a semi-transparent grey track (`rgba(127,127,127,0.18)`), height `10px`, and `border-radius: 999px`.
- `.progressFill` uses a `linear-gradient` from `var(--accent-cta)` to `var(--accent-cta-end)` with `height: 100%`.
- Both CSS variables (`--accent-cta`, `--accent-cta-end`) are defined in `globals.css`.

## Test Type

`frontend` — Static source code analysis (no browser required).

## Test Structure

Reads `web/src/app/upload/upload.module.css` via the `UploadCSSModule` component
and `web/src/app/globals.css` via the `CSSGlobalsPage` component to assert that
all redesign CSS properties are correctly in place.

| Step | What is asserted |
|------|-----------------|
| 1 | `upload.module.css` exists at the expected path |
| 2 | `.progressShell` background is `rgba(127,127,127,0.18)` |
| 3 | `.progressShell` height is `10px` |
| 4 | `.progressShell` border-radius is `999px` |
| 5 | `.progressFill` uses `linear-gradient` |
| 6 | `.progressFill` gradient references `var(--accent-cta)` |
| 7 | `.progressFill` gradient references `var(--accent-cta-end)` |
| 8 | `.progressFill` height is `100%` |
| 9 | `globals.css` :root defines `--accent-cta` |
| 10 | `globals.css` :root defines `--accent-cta-end` |

## Environment Variables

None — this test reads static source files only.

## Prerequisites

- Python 3.10+
- `pytest`

## Running Locally

```bash
pytest testing/tests/MYTUBE-509/test_mytube_509.py -v
```

## Expected Output (when feature is implemented)

```
PASSED  TestProgressBarCSSModule::test_upload_css_exists
PASSED  TestProgressBarCSSModule::test_progress_shell_background
PASSED  TestProgressBarCSSModule::test_progress_shell_height
PASSED  TestProgressBarCSSModule::test_progress_shell_border_radius
PASSED  TestProgressBarCSSModule::test_progress_fill_uses_gradient
PASSED  TestProgressBarCSSModule::test_progress_fill_gradient_uses_accent_cta
PASSED  TestProgressBarCSSModule::test_progress_fill_gradient_uses_accent_cta_end
PASSED  TestProgressBarCSSModule::test_progress_fill_height_full
PASSED  TestProgressBarCSSModule::test_globals_css_defines_accent_cta
PASSED  TestProgressBarCSSModule::test_globals_css_defines_accent_cta_end
```
