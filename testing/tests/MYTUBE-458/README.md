# MYTUBE-458 — Auth page branding: LogoIcon and wordmark style are consistent

## Objective

Verify that the branded `LogoIcon` SVG and the "MYTUBE" wordmark are correctly
rendered inside the auth card on the `/login` page, with the right dimensions
and the correct brand colour.

## Test Type

`web` — Playwright end-to-end test against the deployed static site.

## Preconditions

- The web application is deployed and accessible at the URL configured via
  `WEB_BASE_URL` (default: `https://ai-teammate.github.io/mytube/`).
- `HEADLESS` env var controls browser headless mode (default: `true`).

## Steps

| # | Action | Expected Result |
|---|--------|-----------------|
| 1 | Navigate to `/login` | Page loads; auth form (email input) is visible |
| 2 | Locate the `<svg>` inside `.auth-card` | At least one `<svg>` element is present |
| 3 | Read the SVG's computed width | Value equals **48 px** |
| 4 | Read the SVG's computed height | Value equals **48 px** |
| 5 | Locate the wordmark `<span>` with text "MYTUBE" | At least one matching element found |
| 6 | Compare wordmark computed color with `--accent-logo` | Both resolve to the same browser RGB value |

## Expected Result

- `LogoIcon` SVG renders at **48 × 48 px** inside `.auth-card`.
- "MYTUBE" wordmark `<span>` is present and its computed `color` matches the
  resolved value of `var(--accent-logo)` from `:root`.

## Architecture Notes

- All Playwright locator and `evaluate` calls are encapsulated inside
  `LoginPage` (`testing/components/pages/login_page/login_page.py`).
- The test only calls high-level `LoginPage` methods (`get_logo_svg_count`,
  `get_logo_svg_width`, `get_logo_svg_height`, `get_wordmark_count`,
  `get_wordmark_computed_color`, `resolve_css_variable`,
  `resolve_css_variable_to_rgb`).
- `WebConfig` centralises environment-variable access.

## Environment Variables

| Variable      | Required | Default                                    | Description                  |
|---------------|----------|--------------------------------------------|------------------------------|
| `WEB_BASE_URL` | Yes      | `https://ai-teammate.github.io/mytube/`   | Base URL of deployed app     |
| `HEADLESS`    | No       | `true`                                     | Run browser headless         |
| `SLOW_MO`     | No       | `0`                                        | Slow-motion delay in ms      |

## Running the Test Locally

```bash
# Install dependencies (from repo root)
pip install playwright pytest
playwright install chromium

# Run with default deployed URL
pytest testing/tests/MYTUBE-458/test_mytube_458.py -v

# Run against a local dev server
WEB_BASE_URL=http://localhost:3000/ pytest testing/tests/MYTUBE-458/test_mytube_458.py -v
```

## Expected Output

```
PASSED  TestAuthPageBranding::test_logo_icon_svg_is_present
PASSED  TestAuthPageBranding::test_logo_icon_width_is_48px
PASSED  TestAuthPageBranding::test_logo_icon_height_is_48px
PASSED  TestAuthPageBranding::test_wordmark_text_is_present
PASSED  TestAuthPageBranding::test_wordmark_color_matches_accent_logo
```
