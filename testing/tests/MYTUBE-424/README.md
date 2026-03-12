# MYTUBE-424 — LogoIcon Component: SVG Attributes

## Test Scope

Verifies that the `LogoIcon` React component (`web/src/components/icons/LogoIcon.tsx`) renders a valid SVG element with the expected structural attributes.

## Test Approach

The fixture HTML is generated at test-setup time by executing a small TypeScript script that calls `ReactDOMServer.renderToStaticMarkup(React.createElement(LogoIcon))`. This guarantees that the test always exercises the **current** component source — any regression in `LogoIcon.tsx` (e.g. a changed `viewBox` or `fill`) will be caught immediately.

The rendered SVG is embedded in a minimal HTML page served by a local `http.server.HTTPServer`. Playwright opens the page in a headless Chromium browser and verifies the DOM attributes via the `LogoIconPage` page object.

## Architecture

```
tests/MYTUBE-424/            ← this folder
  test_mytube_424.py         ← test cases (uses LogoIconPage only)
  config.yaml
  README.md

components/pages/logo_icon/  ← Page Object (Playwright interactions)
  logo_icon_page.py

core/config/
  web_config.py              ← headless flag, no hardcoded values
```

## Assertions

| # | Assertion | Expected value |
|---|-----------|----------------|
| 1 | `<svg>` element is present inside `#root` | count == 1 |
| 2 | `viewBox` attribute | `"0 0 44 44"` |
| 3 | `fill` attribute | `"currentColor"` |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PLAYWRIGHT_HEADLESS` | `true` | Run Chromium headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay (ms) |
