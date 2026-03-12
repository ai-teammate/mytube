# MYTUBE-454: Hero section responsiveness — layout collapses to single column below 768px

## Overview

Verifies that the homepage hero section grid layout (`1.05fr 0.95fr` two-column grid)
correctly collapses into a single vertical column when the viewport width drops below
768 px.

## Test Structure

| Part | Mode | Description | Requires infrastructure? |
|------|------|-------------|--------------------------|
| A — Fixture desktop | Always runs | Serves a minimal HTML page reproducing the hero grid; verifies two columns at 1280 px using computed CSS + bounding-box geometry | No |
| B — Fixture mobile | Always runs | Same fixture page; verifies single column at 375 px using computed CSS + bounding-box stacked geometry | No |
| C — Live mobile | Skipped if unreachable | Navigates to deployed app, sets viewport to 375 px, asserts hero grid collapses to single column | Yes (deployed web app) |

Parts A and B always run — they use a self-contained fixture HTTP server.
Part C is skipped gracefully when the deployed app is unreachable.

## Architecture

- Uses `HeroSectionComponent` from `testing/components/pages/hero_section/` to encapsulate hero-section selectors and layout assertions.
- `WebConfig` from `testing/core/config/web_config.py` centralises env var access.
- Playwright sync API with a module-scoped `web_config` pytest fixture.

## Environment Variables

| Variable | Required for Part | Default | Description |
|----------|-------------------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | C only | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app |
| `PLAYWRIGHT_HEADLESS` | A, B, C | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | A, B, C | `0` | Slow-motion delay in ms |

## Running the Test

```bash
# From repo root — all parts (C skipped automatically if app is unreachable)
pytest testing/tests/MYTUBE-454/test_mytube_454.py -v
```

## Expected Output When Tests Pass

```
testing/tests/MYTUBE-454/test_mytube_454.py::TestMytube454HeroResponsiveness::test_fixture_desktop_two_column_layout PASSED
testing/tests/MYTUBE-454/test_mytube_454.py::TestMytube454HeroResponsiveness::test_fixture_mobile_grid_collapses_to_single_column PASSED
testing/tests/MYTUBE-454/test_mytube_454.py::TestMytube454HeroResponsiveness::test_live_hero_grid_collapses_to_single_column SKIPPED (deployed app unreachable)
```
