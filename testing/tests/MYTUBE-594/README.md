# MYTUBE-594 — Upload video in dark theme: Choose File button is clearly visible and styled

## Objective

Verify that the native Choose File button (`::file-selector-button` pseudo-element) on the
upload page is clearly visible and correctly styled using design tokens when the dark theme
is active.

## Test Type

`static+fixture` — dual-mode: static CSS analysis (no browser) + Playwright computed-style
checks against a self-contained HTML fixture.

## Test Steps

1. (Static) Verify `::file-selector-button` rule exists in `upload.module.css`.
2. (Static) Verify the rule uses `var(--accent-cta)` for background.
3. (Static) Verify the rule uses `var(--text-cta)` for color.
4. (Static) Verify `globals.css` dark theme defines `--accent-cta: #62c235`.
5. (Playwright) Render a dark-theme HTML fixture embedding the real CSS files.
6. (Playwright) Assert card background resolves to `rgb(36, 36, 40)` (`--bg-card` dark value).
7. (Playwright) Assert `#file-input` element is present in the DOM.
8. (Playwright) Assert `::file-selector-button` background resolves to `rgb(98, 194, 53)` (`--accent-cta`).
9. (Playwright) Assert `::file-selector-button` color resolves to `rgb(255, 255, 255)` (`--text-cta`).
10. (Playwright) Assert `::file-selector-button` has a non-zero `border-radius`.
11. (Playwright) Assert button background is visually distinct from card background.

## Expected Result

The `::file-selector-button` is styled with `background: var(--accent-cta)` (green,
`#62c235`) and `color: var(--text-cta)` (white). In dark mode the button resolves to
`rgb(98, 194, 53)` against the card background `rgb(36, 36, 40)`, providing high
contrast and visibility.

## Architecture

- `UploadCSSModule` (`testing/components/pages/upload_page/upload_css_module.py`) — static
  CSS analysis; tests call `rule_contains()` and `get_rule_body()` instead of parsing CSS inline.
- Playwright sync API with pytest module-scoped fixtures.
- `page.set_content()` injects the real CSS files into a minimal HTML fixture — no
  external server dependency.

## Linked Bugs

- **MYTUBE-591** (Done): `::file-selector-button` styling was missing from
  `upload.module.css`. Fix added `background: var(--accent-cta)`, `color: var(--text-cta)`,
  `border-radius`, `padding`, `font-weight`, and a hover rule.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (`pip install playwright && playwright install chromium`)

## Running

```bash
# From the repository root:
pytest testing/tests/MYTUBE-594/test_mytube_594.py -v
```
