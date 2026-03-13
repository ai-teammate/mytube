# MYTUBE-533 — Hero Section Desktop Layout: Grid Structure Follows 2-Column Specification

## Objective

Verify the homepage hero section uses the specified CSS grid proportions on desktop
viewports (width ≥ 768 px): `grid-template-columns: 1.05fr 0.95fr` with `gap: 30px`.

## Test Type

`web` — Playwright (Python) · Chromium · 1280×800 viewport

## Preconditions

- Browser viewport width must be ≥ 768 px (triggers the 2-column grid breakpoint).
- The deployed application is reachable at the configured `WEB_BASE_URL`
  (default: `https://ai-teammate.github.io/mytube`).

## Steps

1. Navigate to the homepage at a 1280×800 desktop viewport.
2. Wait for the hero section (`<section aria-label="Hero">`) to be visible.
3. Scan the loaded CSS stylesheets for the `grid-template-columns` rule applied to
   the hero element.
4. Read the computed `column-gap` value.
5. Read the computed pixel widths of the two rendered grid columns.

## Expected Result

| Assertion | Expected |
|-----------|----------|
| Hero section visible at ≥ 768 px viewport | ✅ visible |
| Declared `grid-template-columns` | `1.05fr 0.95fr` |
| Computed `column-gap` | `30px` |
| Rendered column-width ratio (col1 / col2) | ≈ 1.1053 (±2%) |

## Architecture

- **Component**: `HeroSectionComponent` (`testing/components/pages/hero_section/`)
  encapsulates all selectors and CSS-inspection helpers.
- **Config**: `WebConfig` (`testing/core/config/web_config.py`) provides the base URL.
- No hardcoded URLs or selectors in the test module.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (Python package)
- Playwright Chromium browser: `playwright install chromium`

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `WEB_BASE_URL` / `APP_URL` | Deployed app base URL | `https://ai-teammate.github.io/mytube` |
| `PLAYWRIGHT_HEADLESS` | Run headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay (ms) | `0` |

## Running the Tests

```bash
# From the repository root:
pytest testing/tests/MYTUBE-533/test_mytube_533.py -v
```

## Expected Output

```
PASSED  TestHeroDesktopGridLayout::test_hero_section_is_visible
PASSED  TestHeroDesktopGridLayout::test_declared_grid_template_columns
PASSED  TestHeroDesktopGridLayout::test_computed_column_gap_is_30px
PASSED  TestHeroDesktopGridLayout::test_column_width_ratio_matches_specification
```
