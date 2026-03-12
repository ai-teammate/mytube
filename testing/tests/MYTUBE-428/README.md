# MYTUBE-428 — Decorative Icons Implementation: components render correct viewBox dimensions

## Objective

Verify that decorative icon components (`DecorPlay` and `DecorWave`) are implemented
with the correct viewBox dimensions as per technical requirements:
- `DecorPlay` uses `viewBox="0 0 120 120"`
- `DecorWave` uses `viewBox="0 0 120 120"`

## Test Type

`ui` — Static source analysis of React/TSX icon components.

## Test Structure

### Layer A — Static Source Analysis (always runs, no browser required)

Reads the TSX source files for `DecorPlay` and `DecorWave` from
`web/src/components/icons/` and verifies that each SVG element declares
`viewBox="0 0 120 120"` using a regex match.

Tests:
- `test_decor_play_viewbox_in_source` — verifies `DecorPlay.tsx` declares the correct viewBox
- `test_decor_wave_viewbox_in_source` — verifies `DecorWave.tsx` declares the correct viewBox

## Prerequisites

- Python 3.10+
- `pytest`
- Repository checked out (icon source files accessible at
  `web/src/components/icons/DecorPlay.tsx` and `web/src/components/icons/DecorWave.tsx`)

## Environment Variables

No environment variables required.

## Running the Tests

```bash
pytest testing/tests/MYTUBE-428/test_mytube_428.py -v
```

## Expected Output

```
PASSED  test_decor_play_viewbox_in_source
PASSED  test_decor_wave_viewbox_in_source
```
