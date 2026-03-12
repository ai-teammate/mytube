# MYTUBE-452 — Hero section feature pills and headline: visual styling matches design tokens

## Objective

Verify the homepage hero section correctly renders the headline and feature pills
using the established design tokens defined in `globals.css`.

## Test Type

`frontend` — Static source code analysis (no browser required).

## Test Structure

### Layer A — CSS Token Validation (always runs)

Reads `web/src/app/globals.css` and verifies that the required design tokens are
correctly defined in the `:root` block:

1. `--accent-pill-bg` is `#e5daf6`
2. `--text-pill` is `#6d40cb`
3. `--text-secondary` is `#666666`

### Layer B — Source Code Structural Analysis (always runs)

Walks `web/src/` (excluding `node_modules`, `.next`, `__tests__`) looking for TSX/CSS
files containing hero section content and confirms:

1. A hero section exists with headline or pill label text
2. Feature pills reference `var(--accent-pill-bg)` for background color
3. Feature pills reference `var(--text-pill)` for text color
4. The headline uses `clamp()` for responsive font sizing
5. The headline has `letter-spacing: -0.02em`
6. The sub-text references `var(--text-secondary)` for color
7. The sub-text has a `max-width` using `ch` units ≤ 62ch

## Prerequisites

- Python 3.10+
- `pytest`

## Running the Tests

```bash
pytest testing/tests/MYTUBE-452/test_mytube_452.py -v
```

## Expected Output (when feature is implemented)

```
PASSED  TestLayerACSSTokens::test_accent_pill_bg_token_defined
PASSED  TestLayerACSSTokens::test_text_pill_token_defined
PASSED  TestLayerACSSTokens::test_text_secondary_token_defined
PASSED  TestLayerBHeroSection::test_hero_section_exists_in_source
PASSED  TestLayerBHeroSection::test_feature_pills_use_accent_pill_bg_token
PASSED  TestLayerBHeroSection::test_feature_pills_use_text_pill_token
PASSED  TestLayerBHeroSection::test_headline_uses_clamp_font_size
PASSED  TestLayerBHeroSection::test_headline_has_letter_spacing
PASSED  TestLayerBHeroSection::test_subtext_uses_text_secondary_token
PASSED  TestLayerBHeroSection::test_subtext_max_width_62ch
```
