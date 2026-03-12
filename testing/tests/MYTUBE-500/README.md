# MYTUBE-500 — SiteHeader login button: pill shape and branded styling applied

## Objective

Verify the redesigned login button in the site header replaces the previous plain
link style with a branded, pill-shaped button that uses the application's CSS
custom properties for colour and typography.

## Test Type

`web` — Playwright (Chromium) functional UI test against the deployed application.

## Preconditions

- User is **not** authenticated (no active session).
- Application is deployed and accessible at the URL configured by `WEB_BASE_URL`.

## Steps

1. Open the application home page and locate the login button in the header
   utility area (`header a[href*='/login/']`).
2. Inspect the computed CSS styles of the button element.

## Expected Result

| Property              | Expected Value                       |
|-----------------------|--------------------------------------|
| Visibility            | Button is present and visible        |
| `borderTopLeftRadius` | Non-zero (pill shape / `rounded-full`) |
| `borderColor`         | `rgb(161, 137, 219)` (`--accent-login-border`) |
| `color`               | `rgb(109, 64, 203)` (`--accent-logo`) |
| `fontWeight`          | `600` (semibold)                     |

## Test Cases

| # | Test                                                          | Description                                      |
|---|---------------------------------------------------------------|--------------------------------------------------|
| 1 | `test_login_button_is_visible`                                | Button is present and visible in the header      |
| 2 | `test_login_button_has_pill_shape`                            | `borderTopLeftRadius` is non-zero                |
| 3 | `test_login_button_border_color_uses_accent_login_border`     | `borderColor` == `rgb(161, 137, 219)`            |
| 4 | `test_login_button_color_uses_accent_logo`                    | `color` == `rgb(109, 64, 203)`                   |
| 5 | `test_login_button_font_weight_is_semibold`                   | `fontWeight` == `600`                            |

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (with Chromium browser installed)

## Environment Variables

| Variable       | Required | Description                       |
|----------------|----------|-----------------------------------|
| `WEB_BASE_URL` | Yes      | Base URL of the deployed app      |

## Running the Tests

```bash
pytest testing/tests/MYTUBE-500/test_mytube_500.py -v
```
