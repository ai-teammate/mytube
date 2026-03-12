# MYTUBE-449 — Redesigned VideoCard Layout

## Objective

Verify the redesigned VideoCard component correctly applies the new visual styles,
thumbnail labels, and tag pills according to the design specification.

## Steps Verified

1. **Navigate** to the homepage where the video grid is rendered.
2. **Locate** video cards on the homepage.
3. **Inspect the outer card element** — background colour, border-radius, and box-shadow.
4. **Inspect the thumbnail area** — aspect-ratio, border-radius, and the "HD" overlay label.
5. **Inspect tag pills** — background colour and text colour (skipped if no tagged videos are seeded).

## Expected Results

| Element | Property | Expected Value |
|---------|----------|----------------|
| Outer card | `background-color` | `rgb(243, 244, 248)` (`var(--bg-card)` = `#f3f4f8`) |
| Outer card | `border-radius` | `16px` |
| Outer card | `box-shadow` | non-empty, contains 8px Y-offset (`var(--shadow-card)` = `0 8px 20px rgba(0,0,0,0.08)`) |
| Thumbnail anchor | `aspect-ratio` | `16 / 9` (numeric ratio ≈ 1.7778) |
| Thumbnail anchor | `border-radius` | `12px 12px 0px 0px` |
| HD label span | text | `"HD"` |
| HD label span | `color` | `rgb(255, 255, 255)` (white) |
| HD label span | `background-color` | `rgba(0, 0, 0, 0.55)` (semi-transparent dark) |
| Tag pill span | `background-color` | `rgb(229, 218, 246)` (`var(--accent-pill-bg)` = `#e5daf6`) |
| Tag pill span | `color` | `rgb(109, 64, 203)` (`var(--text-pill)` = `#6d40cb`) |

## CSS Design Tokens (globals.css — light theme)

```
--bg-card:        #f3f4f8  → rgb(243, 244, 248)
--shadow-card:    0 8px 20px rgba(0, 0, 0, 0.08)
--accent-pill-bg: #e5daf6  → rgb(229, 218, 246)
--text-pill:      #6d40cb  → rgb(109, 64, 203)
```

## How to Run Locally

```bash
cd /path/to/mytube

# Install dependencies (first time only)
pip install playwright pytest
playwright install chromium

# Run all tests in this folder
pytest testing/tests/MYTUBE-449/ -v

# Run against a local dev server
BASE_URL=http://localhost:3000 pytest testing/tests/MYTUBE-449/ -v

# Run with visible browser
PLAYWRIGHT_HEADLESS=false pytest testing/tests/MYTUBE-449/ -v
```

## Notes

- The tag-pill test (`test_tag_pills_background_and_color`) will be **skipped** if
  no video cards with tags are present on the homepage. Seed at least one video with
  tags to exercise that code path.
- The HD label background assertion uses a numeric alpha tolerance (`±0.01`) to
  accommodate browser floating-point normalisation of the opacity value.
- The aspect-ratio assertion parses the computed value numerically to avoid
  false positives from strings like `"160 / 90"`.
