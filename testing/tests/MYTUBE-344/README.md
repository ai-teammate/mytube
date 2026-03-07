# MYTUBE-344 — Verify footer content — site links and copyright present

## What this test verifies

Ensures the global site footer renders correctly on the homepage with:
- A visible `<footer>` element
- Footer navigation (`aria-label="Footer navigation"`) containing both links:
  - **Terms** → href containing `/terms`
  - **Privacy** → href containing `/privacy`
- A copyright paragraph containing `©`, `mytube`, and `All rights reserved`

## Prerequisites

| Requirement | Details |
|---|---|
| Chromium / Playwright | Installed via `pip install playwright && playwright install chromium` |
| `APP_URL` or `WEB_BASE_URL` | Base URL of the deployed app (default: `https://ai-teammate.github.io/mytube`) |
| `PLAYWRIGHT_HEADLESS` | Run browser in headless mode (default: `true`) |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms for debugging (default: `0`) |

## Install dependencies

```bash
pip install pytest playwright
playwright install chromium
# or via requirements.txt:
pip install -r testing/requirements.txt
```

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-344/ -v
```

With a custom base URL:

```bash
APP_URL=https://ai-teammate.github.io/mytube pytest testing/tests/MYTUBE-344/ -v
```

## Expected output when passing

```
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_footer_is_visible PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_terms_link_is_visible PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_terms_link_text PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_terms_link_href PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_privacy_link_is_visible PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_privacy_link_text PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_privacy_link_href PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_copyright_text_is_visible PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_copyright_text_contains_mytube PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_copyright_text_contains_all_rights_reserved PASSED
testing/tests/MYTUBE-344/test_mytube_344.py::TestFooterContent::test_copyright_text_contains_copyright_symbol PASSED
```

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web application |
| `WEB_BASE_URL` | No | _(falls back to APP_URL)_ | Alternative env var for the base URL |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Set to `false` to run with a visible browser |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms (useful for debugging) |
