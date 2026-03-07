# MYTUBE-362 — Type text in search bar — typed text and placeholder are visible

## Objective

Verify that the search bar placeholder and the text typed by the user are
legible and follow contrast rules:

- The placeholder text (`"Search videos…"`) is clearly visible.
- The typed text `"Visibility Test"` uses a dark colour and is **not**
  white-on-white (computed brightness ≤ 200/255 against a white background).

## Steps

1. Navigate to the homepage (`/`).
2. Observe the search bar in the header — confirm placeholder equals `"Search videos…"` and the input is visible.
3. Click into the search bar and type `"Visibility Test"`.
4. Assert that the computed text colour is dark (perceived brightness ≤ 200/255).

## Expected Result

| # | Assertion | Expected |
|---|-----------|----------|
| 1 | `<input type="search">` placeholder | `"Search videos…"` |
| 2 | Search input visibility | Visible |
| 3 | Input background brightness | ≥ 200/255 (light/white) |
| 4 | Typed text `"Visibility Test"` value in DOM | `"Visibility Test"` |
| 5 | Typed text computed colour brightness | ≤ 200/255 (dark, readable) |

## Environment Variables

| Variable           | Default                                  | Description                        |
|--------------------|------------------------------------------|------------------------------------|
| `APP_URL`          | `https://ai-teammate.github.io/mytube`   | Base URL of the deployed web app   |
| `WEB_BASE_URL`     | `https://ai-teammate.github.io/mytube`   | Alias for `APP_URL`                |
| `PLAYWRIGHT_HEADLESS` | `true`                               | Run browser headless               |
| `PLAYWRIGHT_SLOW_MO`  | `0`                                  | Slow-motion delay in ms            |

## Dependencies

- Python 3.11+
- `playwright` (`pip install playwright && playwright install chromium`)
- `pytest`

```bash
pip install pytest playwright
playwright install chromium
```

## How to Run

From the repository root:

```bash
pytest testing/tests/MYTUBE-362/test_mytube_362.py -v
```

## Expected Output (passing)

```
testing/tests/MYTUBE-362/test_mytube_362.py::TestSearchBarVisibility::test_search_input_is_present PASSED
testing/tests/MYTUBE-362/test_mytube_362.py::TestSearchBarVisibility::test_placeholder_is_visible_and_has_contrast PASSED
testing/tests/MYTUBE-362/test_mytube_362.py::TestSearchBarVisibility::test_typed_text_is_visible_and_dark PASSED

3 passed
```
