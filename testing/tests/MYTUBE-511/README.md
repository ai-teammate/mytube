# MYTUBE-511 — Custom select chevron: SVG data URI is used for dropdown icon

## Test Case Overview

**Test ID**: MYTUBE-511

**Type**: Web UI Test (Playwright)

**Objective**: Verify the category select input on the upload page uses the custom branded chevron (SVG data URI via CSS `background-image`) instead of the browser default dropdown arrow.

## Preconditions

- User is authenticated (or credentials are provided via environment variables)
- The upload page (`/upload`) is accessible

## Test Steps

1. Navigate to the `/upload` page (log in first if credentials are configured).
2. Locate the category selection dropdown (`select[id="categoryId"]`).
3. Inspect the computed CSS properties for the select element.

## Expected Result

- `select[id="categoryId"]` is present and visible on `/upload`.
- The `background-image` CSS property contains `data:image/svg+xml` — a custom branded SVG chevron is applied.
- The `appearance` CSS property is `none` — the browser default dropdown arrow is suppressed.

## Technical Implementation

- Uses `UploadPage.is_category_select_visible()` to verify element presence.
- Uses `UploadPage.get_category_select_computed_styles()` to retrieve computed CSS via `window.getComputedStyle`.
- No private page-object internals are accessed directly — all logic is encapsulated in `UploadPage`.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (with Chromium browser installed)

## Environment Variables

| Variable        | Required | Description                          |
|-----------------|----------|--------------------------------------|
| `WEB_BASE_URL`  | Yes      | Base URL of the application          |
| `TEST_EMAIL`    | No       | Login email (if auth required)       |
| `TEST_PASSWORD` | No       | Login password (if auth required)    |

## Running the Tests

```bash
pytest testing/tests/MYTUBE-511/test_mytube_511.py -v
```

## Expected Output

```
PASSED  test_category_select_is_present
PASSED  test_category_select_has_svg_data_uri_background_image
PASSED  test_category_select_hides_browser_default_chevron
```
