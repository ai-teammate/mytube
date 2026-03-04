# MYTUBE-241: Refresh registration page — page content persists and no 404 error

## Objective

Ensure that direct navigation and browser refreshes on the `/register/` sub-route do not trigger 404 errors from the GitHub Pages static hosting configuration.

## Test Type

Web UI — Playwright (Chromium)

## Dependencies

- `playwright` Python package with Chromium browser installed

## Install Dependencies

```bash
pip install pytest playwright
playwright install chromium
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless (`false` to watch) |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms (for debugging) |

## Run the Test

From the repository root:

```bash
cd /path/to/mytube
pytest testing/tests/MYTUBE-241/test_mytube_241.py -v
```

Or with a custom base URL:

```bash
APP_URL=https://ai-teammate.github.io/mytube \
  pytest testing/tests/MYTUBE-241/test_mytube_241.py -v
```

To run headed (non-headless) for debugging:

```bash
PLAYWRIGHT_HEADLESS=false \
  pytest testing/tests/MYTUBE-241/test_mytube_241.py -v -s
```

## Expected Output (Passing)

```
testing/tests/MYTUBE-241/test_mytube_241.py::TestRegisterPageRefresh::test_register_page_loads_on_direct_navigation PASSED
testing/tests/MYTUBE-241/test_mytube_241.py::TestRegisterPageRefresh::test_no_file_not_found_on_direct_navigation PASSED
testing/tests/MYTUBE-241/test_mytube_241.py::TestRegisterPageRefresh::test_register_page_heading_visible_after_hard_refresh PASSED
testing/tests/MYTUBE-241/test_mytube_241.py::TestRegisterPageRefresh::test_no_file_not_found_after_hard_refresh PASSED
```

## What Is Tested

1. **Direct navigation** to `/register/` shows the "Create an account" form heading.
2. **No "File not found"** text is present on direct navigation.
3. **Hard refresh** (`page.reload()`, equivalent to Ctrl+R) keeps the registration form visible.
4. **No "File not found"** text appears after the hard refresh.

The tests verify that the GitHub Pages `404.html` SPA fallback correctly redirects sub-route requests back to `index.html`, allowing the Next.js/React app router to handle routing client-side.
