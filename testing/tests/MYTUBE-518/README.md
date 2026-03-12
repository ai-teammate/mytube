# MYTUBE-518 — Dashboard Redesign Styles Test

## Objective

Verify the visual design of the dashboard heading and the toolbar container
according to the redesign specifications.

## Test Approach

Pure static analysis — no browser or authentication required.

- **Layer A**: reads `web/src/app/dashboard/_content.module.css` and checks each CSS property
- **Layer B**: reads `web/src/app/dashboard/_content.tsx` and verifies style class usage
- **Layer C**: reads `web/src/app/globals.css` and verifies the `--bg-card` design token

## Dependencies

```
pytest
```

Install:
```bash
pip install pytest
```

## Run

From the repository root:
```bash
pytest testing/tests/MYTUBE-518/test_mytube_518.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerACSSProperties::test_section_heading_font_size PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerACSSProperties::test_section_heading_font_weight PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerACSSProperties::test_toolbar_background_uses_bg_card_token PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerACSSProperties::test_toolbar_border_radius PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerACSSProperties::test_toolbar_grid_columns PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerACSSProperties::test_toolbar_grid_display PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerBSourceStructure::test_heading_uses_section_heading_class PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerBSourceStructure::test_heading_text_is_my_videos PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerBSourceStructure::test_toolbar_uses_toolbar_class PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerBSourceStructure::test_toolbar_grid_uses_toolbar_grid_class PASSED
testing/tests/MYTUBE-518/test_mytube_518.py::TestLayerCDesignTokens::test_bg_card_token_defined_in_globals PASSED
```

## Environment Variables

None required — test runs entirely from source files.
