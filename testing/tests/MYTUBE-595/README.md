# MYTUBE-595 — Choose File Button Styling Consistent Across Browsers

## Objective

Verify that the `::file-selector-button` pseudo-element styling introduced by the MYTUBE-591 fix is correctly applied in `upload.module.css`, ensuring the Choose File button is visible and consistently styled across Chromium and Firefox in both light and dark themes.

## Test Layers

### Layer A — Static CSS Analysis (always runs; no browser required)

Inspects `upload.module.css` and `globals.css` directly via `UploadCSSModule`:

| Test | What it checks |
|------|---------------|
| `test_upload_css_file_exists` | `upload.module.css` exists on disk |
| `test_file_selector_button_rule_exists` | `.fileInput::file-selector-button` rule is present |
| `test_file_selector_button_has_background` | Rule declares a `background` property |
| `test_file_selector_button_uses_accent_cta` | Background uses `var(--accent-cta)` design token |
| `test_file_selector_button_has_text_cta_color` | Rule declares `color: var(--text-cta)` |
| `test_file_selector_button_hover_rule_exists` | `::file-selector-button:hover` rule is present |
| `test_file_selector_button_hover_has_opacity` | Hover rule includes `opacity` for visual feedback |
| `test_globals_css_defines_accent_cta_light` | `--accent-cta` is defined in the light theme in `globals.css` |
| `test_globals_css_defines_accent_cta_dark` | `--accent-cta` is defined in the dark theme in `globals.css` |

### Layer B — Browser Rendering Tests (Chromium and Firefox)

Navigates to the live `/upload` page via Playwright and verifies:

- The file input element is visible on screen (light theme).
- The `::file-selector-button` pseudo-element has a non-transparent `backgroundColor` (light theme).
- The button remains visible after forcing `body[data-theme="dark"]` (dark theme).

> **Note**: Layer B skips automatically when `FIREBASE_TEST_EMAIL` / `FIREBASE_TEST_PASSWORD` are not set, because the `/upload` page requires authentication.

## Required Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app | `https://ai-teammate.github.io/mytube` |
| `FIREBASE_TEST_EMAIL` | Test account email for authentication | — (Layer B skips if absent) |
| `FIREBASE_TEST_PASSWORD` | Test account password for authentication | — (Layer B skips if absent) |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

## How to Run

```bash
# From the repo root — run all tests (Layer A + Layer B)
pytest testing/tests/MYTUBE-595/test_mytube_595.py -v

# Layer A only (no browser, no credentials needed)
pytest testing/tests/MYTUBE-595/test_mytube_595.py -v -k "TestFileSelectorButtonCSS"

# Layer B only (requires APP_URL + auth credentials)
pytest testing/tests/MYTUBE-595/test_mytube_595.py -v -k "TestFileSelectorButtonBrowser"
```

## Architecture

- **`UploadCSSModule`** (`testing/components/pages/upload_page/upload_css_module.py`) — encapsulates CSS file parsing and rule inspection.
- **`UploadPage`** (`testing/components/pages/upload_page/upload_page.py`) — wraps browser navigation and element visibility checks.
- **`WebConfig`** (`testing/core/config/web_config.py`) — centralises environment variable access.
