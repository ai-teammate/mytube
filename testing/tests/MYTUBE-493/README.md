# MYTUBE-493 — Homepage hero section: 'Browse Library' button visibility and ghost styling

## Objective

Verify that the 'Browse Library' CTA button is correctly rendered in the homepage hero section
with the exact specified text and ghost styling tokens.

## Steps

1. Navigate to the homepage: `https://ai-teammate.github.io/mytube/`
2. Locate the button or anchor element situated below the hero sub-text paragraph.
3. Verify that the button text is exactly **"Browse Library"**.
4. Inspect the element's CSS properties to confirm it uses ghost styling:
   - Transparent background (`rgba(0,0,0,0)` or `transparent`)
   - Visible border (non-zero width, non-transparent border color)
   - Non-transparent text color

## Expected Result

The "Browse Library" button is present and visible in the hero section, displays the correct
text, and adheres to the design system's ghost styling specifications.

## Test Cases

| Test | Description |
|------|-------------|
| `test_browse_library_button_is_present` | Button/anchor exists in the hero section and is visible |
| `test_browse_library_button_text_is_exact` | Button text is exactly "Browse Library" |
| `test_browse_library_button_has_ghost_styling` | CSS computed styles confirm ghost styling |

## Environment

- **URL**: https://ai-teammate.github.io/mytube/
- **Browser**: Chromium (headless)
- **Framework**: Playwright (sync)
- **Linked Bug**: MYTUBE-470
