# MYTUBE-363 — View buttons across site: labels are visible and legible

## Objective

Ensure all UI buttons have visible labels with sufficient WCAG AA contrast across
the homepage, `/login`, and `/upload` pages of the MyTube application.

## Steps

1. Navigate to the homepage and inspect the header Search submit button.
2. Navigate to `/login` and inspect the "Sign In" button.
3. Navigate to `/upload` (authenticated) and inspect the "Upload video" button.

## Expected Result

All button labels are visible; text-to-background contrast ≥ 4.5:1 (WCAG AA minimum
for normal text). No labels are invisible due to CSS token mismatches.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed web app base URL |
| `FIREBASE_TEST_EMAIL` | _(none)_ | Test account email (required for step 3) |
| `FIREBASE_TEST_PASSWORD` | _(none)_ | Test account password (required for step 3) |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms for debugging |

> **Note:** If `FIREBASE_TEST_EMAIL` or `FIREBASE_TEST_PASSWORD` are absent,
> the upload step (step 3) is automatically skipped rather than failed.

## How to Run

From the repository root:

```bash
pytest testing/tests/MYTUBE-363/ -v
```

With explicit credentials:

```bash
FIREBASE_TEST_EMAIL=test@example.com \
FIREBASE_TEST_PASSWORD=secret \
  pytest testing/tests/MYTUBE-363/ -v
```

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Expected Output (passing)

```
PASSED test_step1_search_button_is_visible
PASSED test_step1_search_button_has_label
PASSED test_step1_search_button_contrast_passes_wcag_aa
PASSED test_step2_sign_in_button_is_visible
PASSED test_step2_sign_in_button_has_label
PASSED test_step2_sign_in_button_contrast_passes_wcag_aa
PASSED test_step3_upload_button_is_visible
PASSED test_step3_upload_button_has_label
PASSED test_step3_upload_button_contrast_passes_wcag_aa
```

## Notes

- Tests within this file have a known ordering dependency: the unauthenticated
  `page` fixture is module-scoped and navigates to the homepage (step 1) before
  `/login` (step 2). Run with default pytest ordering to avoid state bleed.
- Contrast ratios are computed via an off-screen Canvas JS snippet that
  normalises oklch, hsl, hex, and rgb colour tokens before computing WCAG
  relative luminance.
