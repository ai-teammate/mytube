# MYTUBE-602 — Dashboard edit modal and tables: backgrounds respect dark theme tokens

## Objective

Verify that the edit-video modal (`.modalCard`) and the playlist management table
(`.playlistTable`) backgrounds correctly switch to dark-theme CSS design tokens
instead of hardcoded white Tailwind classes.

## Preconditions

- Dark theme is enabled (`body[data-theme="dark"]`).
- The MYTUBE-593 fix has been merged (hardcoded `bg-white rounded-2xl` replaced
  with `var(--bg-content)` in `_content.module.css`).

## Steps

1. Navigate to the Dashboard.
2. Open the Edit Video modal.
3. Switch to the Playlists tab to view the management table.

## Expected Result

- The modal (`.modalCard`) and table (`.playlistTable`) backgrounds use design
  tokens (`var(--bg-content)` / `var(--bg-card)`).
- No hardcoded `bg-white` or `bg-gray-50` Tailwind classes appear on these elements.
- In dark mode, both elements render with background `rgb(26, 26, 31)` (`#1a1a1f`),
  distinct from the page background `rgb(15, 15, 17)` (`#0f0f11`).

## Test Strategy

### Layer A — Static CSS Analysis (12 tests, always runs)

Parses `_content.module.css` and `_content.tsx` directly from the repository:

- Verifies `.modalCard` background uses `var(--bg-content)` or `var(--bg-card)`.
- Verifies `.playlistTable` background uses `var(--bg-content)` or `var(--bg-card)`.
- Verifies neither element has a hardcoded white value (`#fff`, `#ffffff`, `white`).
- Verifies `_content.tsx` contains no `className="... bg-white ..."` attributes.
- Verifies `_content.tsx` contains no `className="... bg-gray-50 ..."` attributes.
- Verifies `globals.css` defines `--bg-content: #1a1a1f` in `body[data-theme="dark"]`.

### Layer B — HTML Fixture / Computed Styles (9 tests, always runs)

Renders a self-contained HTML page embedding the real CSS files via Playwright
with `data-theme="dark"` set on `<body>`. Uses `getComputedStyle()` to:

- Assert `body` background resolves to `rgb(15, 15, 17)` (dark theme active).
- Assert `#modal-card` background resolves to `rgb(26, 26, 31)` (not white).
- Assert `#playlist-table` background resolves to `rgb(26, 26, 31)` (not white).
- Assert both elements are visually distinct from the page background (contrast).

## Linked Bugs

- **MYTUBE-593** (Done): Dashboard My Videos and Playlists look broken in dark theme.
  The fix replaced hardcoded `bg-white rounded-2xl` classes on both the edit-video
  modal and the playlist table with CSS module classes using `var(--bg-content)`.

## How to Run

```bash
pytest testing/tests/MYTUBE-602/test_mytube_602.py -v
```

No environment variables are required — all tests run against static files and
a Playwright HTML fixture with no live server needed.

## Architecture

- `DarkThemeFixturePage` component (`testing/components/pages/dark_theme_fixture_page/`)
  encapsulates all Playwright browser interactions.
- CSS utility functions (`testing/core/utils/css_analysis.py`) handle static
  file parsing and fixture HTML generation.
- Tests depend only on component interfaces, not on Playwright directly.
