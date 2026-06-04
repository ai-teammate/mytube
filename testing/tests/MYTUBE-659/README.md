# MYTUBE-659 — Hero Section Headline: displays 'MYTUBE: corp video portal'

## Objective

Verify that the homepage hero section `<h1>` headline correctly displays the updated
corporate portal text: **"MYTUBE: corp video portal"**.

## Test Steps

1. Navigate to the application homepage (`APP_URL` / `WEB_BASE_URL`).
2. Locate the H1 headline inside `section[aria-label='Hero']` via `HeroSectionComponent`.
3. Assert the headline text equals exactly `"MYTUBE: corp video portal"`.

## Expected Result

The `<h1>` element inside the hero section renders the text `"MYTUBE: corp video portal"`
with exact wording, capitalisation, and punctuation.

## Test Type

`web` — Playwright headless Chromium end-to-end test.

## Architecture

```
test_mytube_659.py
  └── HeroSectionComponent.get_hero_headline()
        └── selector: section[aria-label='Hero'] h1
```

## Environment Variables

| Variable              | Description                                              | Default                               |
|-----------------------|----------------------------------------------------------|---------------------------------------|
| `APP_URL`             | Base URL of the deployed web app (checked first)        | —                                     |
| `WEB_BASE_URL`        | Fallback base URL                                        | `https://ai-teammate.github.io/mytube` |
| `PLAYWRIGHT_HEADLESS` | Run browser headless (`true`/`false`)                   | `true`                                |
| `PLAYWRIGHT_SLOW_MO`  | Slow-motion delay in ms                                  | `0`                                   |

## Running the Test

```bash
# From repo root:
pytest testing/tests/MYTUBE-659/test_mytube_659.py -v
```
