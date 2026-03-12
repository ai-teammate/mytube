# MYTUBE-460 — Auth Form Input Styling: Inputs Consume Correct Design Tokens and Focus States

## Objective

Verify that the email and password fields on the `/login` page use the redesigned
input styles consistent with the upload-card design tokens:

- `background-color` resolves to `var(--bg-page)` (either light `#f8f9fa` or dark `#0f0f11`)
- `border-radius` is `12px`
- On focus, a purple focus ring (`box-shadow`) is applied using `rgba(109, 64, 203, 0.25)`

## Test Type

`ui` — Playwright browser automation reading computed CSS properties and triggering focus events.

## Test Structure

### Step 1 — Navigate to `/login`

Opens the login page via `LoginPage` component and waits for the form to render.

### Step 2 — Background colour and border-radius

Reads `background-color` and `border-radius` computed styles for both `input[id="email"]`
and `input[id="password"]`, asserting they match the expected design token values.

### Step 3 — Purple focus ring on email input

Focuses the email input via JavaScript (`focus()` + `FocusEvent` dispatch) and checks
that the inline `box-shadow` style contains the purple colour `rgba(109, 64, 203, ...)`.

### Step 4 — Purple focus ring on password input

Same as Step 3 but for the password input.

## Tests

| Test | Description |
|------|-------------|
| `test_email_input_background_uses_bg_page_token` | Email input background matches `--bg-page` token |
| `test_password_input_background_uses_bg_page_token` | Password input background matches `--bg-page` token |
| `test_email_input_border_radius_is_12px` | Email input `border-radius` is `12px` |
| `test_password_input_border_radius_is_12px` | Password input `border-radius` is `12px` |
| `test_email_input_shows_purple_focus_ring_on_focus` | Email input gains purple `box-shadow` on focus |
| `test_password_input_shows_purple_focus_ring_on_focus` | Password input gains purple `box-shadow` on focus |

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (with Chromium browser installed)
- A running instance of the web app accessible via `WebConfig.login_url()`

## Running the Tests

```bash
pytest testing/tests/MYTUBE-460/test_mytube_460.py -v
```

## Expected Result

All 6 tests pass, confirming that auth form inputs use the correct design tokens
and apply a purple focus ring on focus.
