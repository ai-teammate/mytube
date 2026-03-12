# MYTUBE-515 — Star rating widget redesign: color and size match visual specification

## What this test verifies

The StarRating component visual redesign:
- Heading "Rate this video" with `font-size: 16px` and `font-weight: 600`
- Star buttons are `24px` in size
- Filled stars use `#ff6666` (`var(--star-color)`)
- Empty stars use `var(--border-light)` (`#dcdcdc` in light theme)
- Hover effect applies `transform: scale(1.15)`

## Test layers

**Layer A — CSS source analysis** (no browser needed):
- Reads `web/src/components/StarRating.module.css` and verifies each CSS rule
- Reads `web/src/app/globals.css` to verify design token values
- Reads `web/src/components/StarRating.tsx` to verify heading text

**Layer B — Playwright computed-style checks**:
- Renders a self-contained HTML fixture that replicates the StarRating CSS
- Uses `window.getComputedStyle()` to verify all visual properties at runtime

## Dependencies

```bash
pip install pytest playwright
playwright install chromium
```

## Run

```bash
# From the repo root:
pytest testing/tests/MYTUBE-515/test_mytube_515.py -v
```

With live app:
```bash
WEB_BASE_URL=https://ai-teammate.github.io/mytube pytest testing/tests/MYTUBE-515/test_mytube_515.py -v
```

## Environment variables

| Variable             | Required | Default                               | Description               |
|----------------------|----------|---------------------------------------|---------------------------|
| `WEB_BASE_URL`       | No       | `https://ai-teammate.github.io/mytube`| Deployed web app base URL |
| `PLAYWRIGHT_HEADLESS`| No       | `true`                                | Run browser headless      |
| `PLAYWRIGHT_SLOW_MO` | No       | `0`                                   | Slow-motion delay (ms)    |

## Expected output when passing

```
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerACSSSource::test_heading_font_size_is_16px PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerACSSSource::test_heading_font_weight_is_600 PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerACSSSource::test_star_button_font_size_is_24px PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerACSSSource::test_empty_star_uses_border_light_variable PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerACSSSource::test_filled_star_uses_star_color_variable PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerACSSSource::test_star_color_token_is_ff6666 PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerACSSSource::test_border_light_token_is_defined PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerACSSSource::test_hover_effect_uses_transform_scale PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerACSSSource::test_heading_text_in_component_source PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerBPlaywrightStyles::test_heading_computed_font_size PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerBPlaywrightStyles::test_heading_computed_font_weight PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerBPlaywrightStyles::test_heading_text_content PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerBPlaywrightStyles::test_empty_star_computed_font_size PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerBPlaywrightStyles::test_empty_star_computed_color PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerBPlaywrightStyles::test_filled_star_computed_color PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerBPlaywrightStyles::test_star_group_role_and_label PASSED
testing/tests/MYTUBE-515/test_mytube_515.py::TestLayerBPlaywrightStyles::test_five_star_buttons_present PASSED

17 passed in X.XXs
```
