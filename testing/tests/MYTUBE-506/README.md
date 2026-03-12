# MYTUBE-506 — Upload page responsive layout: 2-column grid collapses on mobile

## Objective

Verify the upload page workspace implements a two-column CSS grid on desktop that
collapses to a single column on mobile viewports (below 639 px).

## Steps

1. View the page on a desktop viewport (width ≥ 1280 px).
2. Inspect the `.workspace` container CSS computed properties.
3. Resize the viewport to a mobile width (375 px, below the 639 px breakpoint).
4. Inspect the collapsed layout and confirm vertical stacking order.

## Expected Result

- **Desktop (1280 × 720):** The `.workspace` container has `display: grid` with
  exactly **2 column tracks** — left column resolved within **280–330 px** (from
  `minmax(280px, 330px)`) and a **20 px column gap**.
- **Mobile (375 × 812):** The `@media (max-width: 639px)` rule fires, collapsing
  the grid to a **single `1fr` column** spanning the full viewport width.
- **Vertical stacking:** The upload card's rendered top edge is above the library
  area's top edge on mobile, confirming DOM-order stacking.

## Test Cases

| # | Test | Viewport | Description |
|---|------|----------|-------------|
| 1 | `test_desktop_two_column_grid` | 1280 × 720 | `.workspace` is a grid with 2 columns, left ≈ 280–330 px, gap = 20 px |
| 2 | `test_mobile_single_column_grid` | 375 × 812 | Grid collapses to 1 column > 300 px wide |
| 3 | `test_mobile_upload_card_stacks_above_library` | 375 × 812 | Upload card top edge < library area top edge |

## Environment

- **Browser:** Chromium (headless)
- **Framework:** Playwright (sync)
- **Auth bypass:** Local HTML fixture (`UploadLayoutPage` component) — no Firebase login required.
- **Component:** `testing/components/pages/upload_page/upload_layout_page.py`

## Test Approach

The `/upload` page requires Firebase authentication; unauthenticated access is
redirected to `/login`. To test the CSS grid rules in isolation a local HTTP
server serves a self-contained HTML fixture that replicates the
`upload.module.css` workspace block verbatim. The fixture is fully managed by
the `UploadLayoutPage` component (see `upload_layout_page.py`), which exposes
semantic methods (`get_workspace_styles`, `get_element_bounds`) used by the
tests. No raw Playwright APIs appear in the test methods.
