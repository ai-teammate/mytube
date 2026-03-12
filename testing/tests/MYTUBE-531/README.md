# MYTUBE-531 — Hero CTA 'Upload Your First Video'

## Objective

Verify that the primary CTA button ("Upload Your First Video") is correctly
styled and redirects the user to the upload page.

## Steps

1. Navigate to the homepage.
2. Locate the "Upload Your First Video" button (`.btn.cta`).
3. Verify the styling includes:
   - a green gradient pill background (`linear-gradient(90deg, #62c235 0%, #4fa82b 100%)`)
   - a pill shape (large `border-radius`, Tailwind `rounded-full`)
   - a green glow box-shadow (`rgba(98, 194, 53, 0.3)`)
   - white text colour (`#ffffff`)
4. Click the button.

## Expected Result

The button is rendered with the correct gradient pill styling and green
box-shadow; clicking it navigates the browser to the `/upload` page.

## Component

`testing/components/pages/hero_section/hero_section_component.py` — `HeroSectionComponent`

## Test Type

`web` — Playwright (Chromium) live browser test against the deployed app.

## Environment Variables

| Variable                    | Required | Description                                        |
|-----------------------------|----------|----------------------------------------------------|
| `APP_URL` / `WEB_BASE_URL`  | Yes      | Base URL of the deployed frontend application.     |
| `PLAYWRIGHT_HEADLESS`       | No       | Run headless (default: `true`).                    |
| `PLAYWRIGHT_SLOW_MO`        | No       | Slow-motion delay in ms (default: `0`).            |

## Running the Tests

```bash
# Against the deployed GitHub Pages app (default):
pytest testing/tests/MYTUBE-531/test_mytube_531.py -v

# Against a local dev server:
WEB_BASE_URL=http://localhost:3000 pytest testing/tests/MYTUBE-531/test_mytube_531.py -v
```

## Expected Output

```
PASSED  TestHeroCtaUploadButton::test_upload_cta_is_visible
PASSED  TestHeroCtaUploadButton::test_upload_cta_has_green_gradient_background
PASSED  TestHeroCtaUploadButton::test_upload_cta_has_pill_shape
PASSED  TestHeroCtaUploadButton::test_upload_cta_has_green_box_shadow
PASSED  TestHeroCtaUploadButton::test_upload_cta_has_white_text
PASSED  TestHeroCtaUploadButton::test_upload_cta_href_points_to_upload
PASSED  TestHeroCtaUploadButton::test_upload_cta_click_navigates_to_upload_page
```
