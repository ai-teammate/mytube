# MYTUBE-469 — Theme hook toggle: toggleTheme updates document body attribute safely

## Purpose

Verify the functionality of the `useTheme` hook and its ability to update the
DOM attribute safely for SSR.  Specifically:

- `toggleTheme` switches `data-theme` on `document.body` between `light` and `dark`.
- The change is applied inside `useEffect` (client-only), ensuring SSR safety.
- The initial theme is read from `localStorage` on mount.

## Test Steps

1. Trigger `toggleTheme` via JavaScript — observe `data-theme` switches from
   `light` → `dark` on `document.body`.
2. Trigger `toggleTheme` again — observe `data-theme` switches back `dark` → `light`.
3. Verify that the `ThemeContext.tsx` source applies `document.body.setAttribute`
   only inside a `useEffect` callback (SSR-safe pattern confirmed statically).
4. Verify that the initial theme is read from `localStorage` using the `"theme"` key.

## Expected Result

- `data-theme` toggles correctly between `"light"` and `"dark"`.
- `document.body.setAttribute("data-theme", ...)` is never called outside `useEffect`.
- `localStorage.getItem("theme")` is called on mount.

## Test Architecture

### Layer A — Playwright fixture test (always runs, no deployed app required)

A self-contained HTML fixture that replicates the `useTheme` toggle logic
(without React) is loaded in the browser.  The fixture includes:

- A "Toggle" button that calls `toggleTheme()`.
- Inline JS that mirrors the `ThemeContext.tsx` behaviour: reads `localStorage`,
  sets `data-theme` on `document.body`, and persists to `localStorage` on toggle.

This lets Playwright verify the attribute changes without requiring a live
Next.js server.

### Layer B — Source code static analysis (always runs, no browser required)

Parses `web/src/context/ThemeContext.tsx` to confirm:

1. `document.body.setAttribute` is called only inside `useEffect`.
2. `localStorage.getItem` is called inside `useEffect` (mount-time SSR guard).
3. `toggleTheme` is wrapped in `useCallback`.

## How to Run

```bash
# From repository root
cd testing
pytest tests/MYTUBE-469/ -v

# Against live app
APP_URL=https://ai-teammate.github.io/mytube pytest tests/MYTUBE-469/ -v
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed app base URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Framework

- **Runner**: pytest
- **Browser automation**: Playwright (Chromium)
- **Config**: `config.yaml`
