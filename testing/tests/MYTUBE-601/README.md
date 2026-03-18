# MYTUBE-601 — Dashboard status badges: colors adapt correctly to dark theme tokens

Regression guard for [MYTUBE-593]: verifies that all four status badge classes in
`DashboardVideoCard.module.css` use CSS design tokens instead of hardcoded hex values,
and that the computed dark-mode colours match the expected token values from `globals.css`.

## Objective

Confirm that status badges (`.statusReady`, `.statusProcessing`, `.statusPending`,
`.statusFailed`) in `DashboardVideoCard` render with correct colours in dark theme by
using CSS custom property tokens (`var(--status-*-bg)` / `var(--status-*-fg)`) rather
than hardcoded light-theme hex values.

## Root Cause (MYTUBE-593)

`DashboardVideoCard.module.css` used hardcoded light-theme hex values for badge
background and foreground colours. In dark mode these values did not respond to the
theme switch, making badges unreadable:

| Class | Old background | Old color |
|-------|---------------|-----------|
| `.statusReady` | `#dcfce7` | `#166534` |
| `.statusProcessing` | `#fef9c3` | `#854d0e` |
| `.statusPending` | `#f3f4f6` | `#374151` |
| `.statusFailed` | `#fee2e2` | `#991b1b` |

The fix replaced all values with CSS design tokens:

| Class | New background | New color |
|-------|---------------|-----------|
| `.statusReady` | `var(--status-ready-bg)` | `var(--status-ready-fg)` |
| `.statusProcessing` | `var(--status-processing-bg)` | `var(--status-processing-fg)` |
| `.statusPending` | `var(--status-pending-bg)` | `var(--status-pending-fg)` |
| `.statusFailed` | `var(--status-failed-bg)` | `var(--status-failed-fg)` |

## Modes

| Mode | When it runs | Tests |
|------|-------------|-------|
| Static CSS analysis | Always | 20 |
| Playwright dark-theme fixture | Always | 8 |

### Static analysis (20 tests — always runs)

Parses `web/src/components/DashboardVideoCard.module.css` and asserts:

- Each of the four badge rule blocks (`.statusReady`, `.statusProcessing`,
  `.statusPending`, `.statusFailed`) exists.
- Each rule uses `var(--status-*-bg)` for `background` and `var(--status-*-fg)` for `color`.
- None of the eight forbidden hardcoded hex values appear in any badge rule.

### Playwright fixture mode (8 tests — always runs)

Builds a self-contained HTML page embedding `globals.css` and `DashboardVideoCard.module.css`
with `data-theme="dark"` set on `<body>`. Uses `page.set_content()` — no external server
needed. Asserts computed `background-color` and `color` for each badge element match
the expected dark-mode resolved values.

## Expected dark-mode resolved values

| Badge | `background-color` | `color` |
|-------|--------------------|---------|
| `.statusReady` | `rgb(20, 83, 45)` | `rgb(134, 239, 172)` |
| `.statusProcessing` | `rgb(113, 63, 18)` | `rgb(253, 230, 138)` |
| `.statusPending` | `rgb(55, 65, 81)` | `rgb(209, 213, 219)` |
| `.statusFailed` | `rgb(127, 29, 29)` | `rgb(252, 165, 165)` |

## Run

```bash
# All tests (static + Playwright fixture)
pytest testing/tests/MYTUBE-601/test_mytube_601.py -v
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

## Files

| File | Purpose |
|------|---------|
| `test_mytube_601.py` | Test implementation (static CSS + Playwright fixture) |
| `conftest.py` | Re-exports shared `browser` fixture from framework layer |
| `config.yaml` | Test configuration (timeouts, browser, metadata) |
| `__init__.py` | Package marker |
