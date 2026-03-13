# MYTUBE-573 — Hero Landing Image Responsive Scaling

## Objective

Verify that the hero landing image (`/landing_image.png`) scales correctly at
mobile, tablet, and desktop viewports without layout breaks or distortion.

## Steps

1. Open the homepage at the specified viewport width.
2. Confirm the hero section (`section[aria-label="Hero"]`) is present and visible.
3. Locate the landing image (`img[alt="Personal Playback Preview"]`) and assert it
   has a positive non-zero rendered size (not collapsed).
4. Assert the image fits within its container (`.visualCanvas` / `.visualPanel`) —
   no overflow on any edge (hard assertion).
5. Assert `object-fit: cover` is applied to the image, guaranteeing the native
   1536×1024 (3:2) aspect ratio is maintained without distortion.

## Expected Result

The landing image scales responsively at all three breakpoints:

| Viewport | Width  |
|----------|--------|
| Mobile   | 375 px |
| Tablet   | 768 px |
| Desktop  | 1440 px |

At every breakpoint the image is visible, fits within its container, and its
aspect ratio is preserved via `object-fit: cover`.

## Component

`testing/components/pages/hero_section/hero_section_component.py` — `HeroSectionComponent`

Methods used:
- `is_hero_visible()` — confirms the hero section is rendered
- `get_landing_image_box()` — returns the bounding box of the landing image
- `get_visual_canvas_box()` — returns the bounding box of the container
- `get_landing_image_object_fit()` — returns the computed `object-fit` CSS value

## Test Type

`web` — Playwright (Chromium) live browser test against the deployed app.

## Environment Variables

| Variable                   | Required | Description                                    |
|----------------------------|----------|------------------------------------------------|
| `APP_URL` / `WEB_BASE_URL` | Yes      | Base URL of the deployed frontend application. |
| `PLAYWRIGHT_HEADLESS`      | No       | Run headless (default: `true`).                |
| `PLAYWRIGHT_SLOW_MO`       | No       | Slow-motion delay in ms (default: `0`).        |

## Running the Tests

```bash
# Against the deployed GitHub Pages app (default):
pytest testing/tests/MYTUBE-573/test_mytube_573.py -v

# Against a local dev server:
WEB_BASE_URL=http://localhost:3000 pytest testing/tests/MYTUBE-573/test_mytube_573.py -v
```

## Expected Output

```
PASSED  test_hero_landing_image_responsive_scaling[mobile]
PASSED  test_hero_landing_image_responsive_scaling[tablet]
PASSED  test_hero_landing_image_responsive_scaling[desktop]
```
