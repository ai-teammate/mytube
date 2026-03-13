# MYTUBE-572 — Hero visual panel image update: landing_image.png is rendered

## Objective

Verify that the Personal Playback Preview placeholder in the hero section has
been replaced with the `landing_image.png` asset.

## Test Type

`e2e` — Static source analysis + live Playwright browser test.

## Test Structure

### Part A — Static Source Analysis (always runs)

Reads `web/src/components/HeroSection.tsx` and verifies:

1. The `<Image>` inside the `visualCanvas` block uses `src="/landing_image.png"`.
2. No generic placeholder image patterns (e.g. `via.placeholder.com`, `picsum.photos`)
   remain in the hero component source.

### Part B — Live Browser E2E (requires resolvable `APP_URL` / `WEB_BASE_URL`)

Uses Playwright (Chromium, headless) to:

1. Navigate to the homepage.
2. Wait for the hero section to be visible.
3. Retrieve the rendered `src` and `srcset` of the hero visual-canvas image via
   `HeroSectionComponent.get_visual_image_src()`.
4. Assert that `landing_image.png` appears in either attribute (Next.js Image
   rewrites the src via `_next/image`).

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (`playwright install chromium`)

## Environment Variables

| Variable        | Required for | Description                       |
|-----------------|--------------|-----------------------------------|
| `WEB_BASE_URL`  | Part B only  | Base URL of the deployed web app. |
| `APP_URL`       | Part B only  | Alternative base URL override.    |

## Running the Tests

```bash
# Part A only (no browser / URL needed):
pytest testing/tests/MYTUBE-572/test_mytube_572.py -v -k "not Live"

# Both parts:
WEB_BASE_URL=https://ai-teammate.github.io/mytube \
  pytest testing/tests/MYTUBE-572/test_mytube_572.py -v
```

## Expected Output

```
PASSED  test_hero_tsx_references_landing_image
PASSED  test_hero_tsx_no_placeholder_only
PASSED  test_landing_image_rendered_in_hero
```
