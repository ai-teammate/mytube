# MYTUBE-519 — Search and category filter styling

Verifies the styling and focus effects of the search and category controls in the dashboard toolbar.

## What is tested

| Check | Selector | Property | Expected |
|---|---|---|---|
| Background | `input[aria-label="Search videos"]` | `background-color` | `#ffffff` (`--bg-content`) |
| Background | `select[aria-label="Filter by category"]` | `background-color` | `#ffffff` (`--bg-content`) |
| Border radius | both | `border-radius` | `12px` |
| Borderless | both | `border-top-style` | `none` |
| Focus ring | search input on click | `box-shadow` | contains `rgb(109, 64, 203)` (`--accent-logo`) |
| Chevron SVG | select | `background-image` | contains `svg` data URI |

## How to run

### Install dependencies

```bash
cd /path/to/repo
pip install -r testing/requirements.txt
playwright install chromium
```

### Run (fixture mode — no server needed)

```bash
pytest testing/tests/MYTUBE-519/test_mytube_519.py -v
```

### Run against live deployed app (requires auth credentials)

```bash
export WEB_BASE_URL=https://ai-teammate.github.io/mytube
export FIREBASE_TEST_EMAIL=test@example.com
export FIREBASE_TEST_PASSWORD=yourpassword
pytest testing/tests/MYTUBE-519/test_mytube_519.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-519/test_mytube_519.py::TestToolbarStyling::test_search_input_background PASSED
testing/tests/MYTUBE-519/test_mytube_519.py::TestToolbarStyling::test_category_select_background PASSED
testing/tests/MYTUBE-519/test_mytube_519.py::TestToolbarStyling::test_search_input_border_radius PASSED
testing/tests/MYTUBE-519/test_mytube_519.py::TestToolbarStyling::test_category_select_border_radius PASSED
testing/tests/MYTUBE-519/test_mytube_519.py::TestToolbarStyling::test_search_input_is_borderless PASSED
testing/tests/MYTUBE-519/test_mytube_519.py::TestToolbarStyling::test_category_select_is_borderless PASSED
testing/tests/MYTUBE-519/test_mytube_519.py::TestToolbarStyling::test_search_input_focus_box_shadow PASSED
testing/tests/MYTUBE-519/test_mytube_519.py::TestToolbarStyling::test_category_select_has_custom_chevron PASSED

8 passed in X.Xs
```
