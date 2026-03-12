# MYTUBE-431 — Apply dark theme attribute: dark theme overrides are active

## Purpose

Verify that the dark theme CSS variables correctly override light theme values when the `data-theme="dark"` attribute is applied to the `<body>` element.

## Test Steps

1. Open the application and inspect the `body` element.
2. Read initial (light-theme) CSS variable values for `--bg-page` and `--text-primary` — they should match the `:root` defaults.
3. Add `data-theme="dark"` to the `<body>` tag via JavaScript.
4. Verify `--bg-page` and `--text-primary` now reflect dark theme palette values.
5. Confirm `getComputedStyle(body).backgroundColor` resolves to the RGB equivalent of `#0f0f11`.

## Expected Values

| Variable | Light Theme | Dark Theme |
|---|---|---|
| `--bg-page` | `#f8f9fa` | `#0f0f11` |
| `--text-primary` | `#222222` | `#f0f0f0` |
| `body.backgroundColor` | — | `rgb(15, 15, 17)` |

## Test Architecture

This suite uses a **dual-mode** strategy:

- **Live Mode** (primary): When `APP_URL` or `WEB_BASE_URL` is set, the test navigates to the real deployed application.
- **Fixture Mode** (fallback): When no URL is available (e.g. offline CI), a self-contained HTML fixture replicating the relevant `:root` and `body[data-theme="dark"]` CSS rules is loaded inline.

Each test is self-contained and can run in isolation or in any order.

## How to Run

```bash
# From repository root
cd testing
pytest tests/MYTUBE-431/ -v

# Run a single test
pytest tests/MYTUBE-431/ -k test_dark_theme_body_background_updates -v

# Against live app
APP_URL=https://ai-teammate.github.io/mytube pytest tests/MYTUBE-431/ -v
```

## Framework

- **Runner**: pytest
- **Browser automation**: Playwright (Chromium)
- **Config**: `config.yaml`
