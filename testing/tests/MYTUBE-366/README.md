# MYTUBE-366 — Cross-Browser Text Visibility

## Objective

Verify that input text, placeholders, and button labels are visible and correctly styled across **Chromium** (Chrome), **Firefox**, and **WebKit** (Safari engine).

## Dependencies

```bash
pip install -r testing/requirements.txt
playwright install chromium firefox webkit
```

## Running the test

From the repository root:

```bash
cd /path/to/mytube
pip install -r testing/requirements.txt
playwright install chromium firefox webkit

pytest testing/tests/MYTUBE-366/test_mytube_366.py -v
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of deployed web app |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browsers headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay (ms) for debugging |

## Expected output (passing)

```
testing/tests/MYTUBE-366/test_mytube_366.py::TestCrossBrowserTextVisibility::test_search_bar_visibility[chromium] PASSED
testing/tests/MYTUBE-366/test_mytube_366.py::TestCrossBrowserTextVisibility::test_search_bar_visibility[firefox] PASSED
testing/tests/MYTUBE-366/test_mytube_366.py::TestCrossBrowserTextVisibility::test_search_bar_visibility[webkit] PASSED
testing/tests/MYTUBE-366/test_mytube_366.py::TestCrossBrowserTextVisibility::test_search_button_label_visibility[chromium] PASSED
...
12 passed in X.XXs
```
