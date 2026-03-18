# MYTUBE-596 — Interact with Choose File button: button is clickable and opens file picker

## Objective

Verify that the newly styled Choose File button on the `/upload` page remains functional
and correctly triggers the system file selection dialog. After selecting a file, the
filename hint in the UI must update accordingly.

## Test Structure

### Layer A — Static CSS analysis (always runs)

Reads `upload.module.css` from the web source tree via `UploadCSSModule` and verifies:

1. The `::file-selector-button` pseudo-element rule exists inside the stylesheet.
2. The rule declares a `background` property (ensures button is visible in dark mode).
3. The rule declares a `color` property (ensures button text is readable).

This layer confirms the MYTUBE-591 fix (`::file-selector-button` styling) is present
without requiring a running application.

### Layer B — Live browser interaction (runs when the app is reachable)

Uses Playwright (Chromium, headless) to:

1. Register a temporary user account (self-contained — no pre-existing credentials needed).
2. Navigate to `/upload`.
3. Assert the upload form (file input) is visible.
4. Intercept the OS file picker dialog via `page.expect_file_chooser()`.
5. Set a minimal valid MP4 fixture file (generated inline, ~1 KB).
6. Assert the filename hint `<p>` element is rendered in the UI after file selection,
   confirming the React `onChange` handler fired and updated UI state.

Layer B is automatically skipped (not failed) when the app is unreachable.

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed app |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## How to Run

```bash
# From repo root
pytest testing/tests/MYTUBE-596/test_mytube_596.py -v
```

## Related

- **Bug**: MYTUBE-591 — Upload page Choose File button not visible (fixed via `::file-selector-button` CSS)
- **Components**: `UploadCSSModule`, `UploadPage`, `RegisterPage`
- **Framework**: Playwright (Python), pytest
