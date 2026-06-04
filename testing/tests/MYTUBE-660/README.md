# MYTUBE-660 — SiteHeader positioning text: 'corp video portal'

## Objective

Verify that the `SiteHeader` component reflects the corporate positioning text so
that the header renders both the **MYTUBE** wordmark and the **"corp video portal"**
subtitle. The combined header text must satisfy the ticket expectation of
`"MYTUBE: corp video portal"`.

## Test Type

`web` — dual-mode: static source analysis + live Playwright UI.

## Test Steps

### Part A — Static analysis (always runs)

1. Assert `web/src/components/SiteHeader.tsx` exists in the repository.
2. Assert the string `"MYTUBE"` is present in the source as the primary wordmark.
3. Assert the string `"Corp Video Portal"` is present as the subtitle text.
4. Assert the subtitle appears after the branded logo `<Link>` with `aria-label="MYTUBE"`,
   confirming nesting (index-ordering heuristic).
5. Assert the Tailwind `uppercase` class is applied within 200 characters before
   the subtitle text (ensures the visual all-caps render of "CORP VIDEO PORTAL").

### Part B — Live Playwright UI (runs when the app is reachable)

1. Navigate to the homepage (`APP_URL/`).
2. Assert the MYTUBE wordmark span is visible inside the `<header>` element via
   `HeaderPage.is_wordmark_visible()`.
3. Assert the subtitle `"Corp Video Portal"` is visible inside the header via
   `HeaderPage.is_subtitle_visible()`.
4. Assert the logo link's `aria-label` contains `"MYTUBE"` via
   `HeaderPage.get_logo_aria_label()`.
5. Assert the combined `<header>` text content includes both `"mytube"` and
   `"corp video portal"` (case-insensitive) via `HeaderPage.get_header_text()`.

## Expected Result

- `SiteHeader.tsx` source contains `"MYTUBE"` and `"Corp Video Portal"` with the
  `uppercase` Tailwind class applied to the subtitle.
- On the live app, the `<header>` element renders both the MYTUBE wordmark and the
  subtitle, and the logo link has an accessible label containing `"MYTUBE"`.

## Architecture

- `HeaderPage` (`testing/components/pages/header_page/header_page.py`) is the page
  object for the site header. All Playwright interactions go through its methods;
  no raw `Page` calls appear in the test file.
- `WebConfig` (`testing/core/config/web_config.py`) centralises env var access.
- No hardcoded URLs or credentials.

## Environment Variables

| Variable              | Description                                                     |
|-----------------------|-----------------------------------------------------------------|
| `APP_URL`             | Base URL of the deployed web app. Default: `https://ai-teammate.github.io/mytube` |
| `WEB_BASE_URL`        | Alias for `APP_URL`.                                            |
| `PLAYWRIGHT_HEADLESS` | Run browser headless. Default: `true`.                         |
| `PLAYWRIGHT_SLOW_MO`  | Slow-motion delay in ms for debugging. Default: `0`.           |

## Running

```bash
# From the repository root:
pytest testing/tests/MYTUBE-660/test_mytube_660.py -v
```
