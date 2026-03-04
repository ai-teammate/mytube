# MYTUBE-179: Search bar functionality — keyword submission from header displays results

## What this test verifies

Navigates to the home page, types a search term into the SiteHeader search bar,
and submits via **Enter key** and via **Search button** click. Asserts that:

1. The browser redirects to `/search?q=<term>`.
2. The `<h1>` heading on the search page references the query term.
3. At least one VideoCard link (`a[href^="/v/"]`) is rendered in the results.
4. Every VideoCard href follows the `/v/<id>` pattern.

Both submission paths (Enter key and button click) are exercised independently.

## Test modes

| Mode    | When                                          | What is tested                                          |
|---------|-----------------------------------------------|---------------------------------------------------------|
| Live    | `API_BASE_URL` set, ready video discoverable  | Real deployed Next.js app — SiteHeader + SearchPage     |
| Fixture | No `API_BASE_URL` or no video found           | Local mock HTTP servers + minimal HTML fixtures         |

## Dependencies

- Python 3.11+
- `playwright` (with Chromium browser)
- `pytest`

## Install dependencies

```bash
pip install pytest playwright
playwright install chromium
```

## Environment variables

| Variable              | Default                                | Description                                              |
|-----------------------|----------------------------------------|----------------------------------------------------------|
| `WEB_BASE_URL`        | `https://ai-teammate.github.io/mytube` | Base URL of the deployed web app                         |
| `APP_URL`             | —                                      | Alternative base URL (takes priority over `WEB_BASE_URL`)|
| `API_BASE_URL`        | —                                      | Backend API URL; when set, enables live mode             |
| `PLAYWRIGHT_HEADLESS` | `true`                                 | Run headless (`true`/`false`)                            |
| `PLAYWRIGHT_SLOW_MO`  | `0`                                    | Slow-motion delay in ms (debug)                          |

## Run the test

```bash
# Fixture mode (no backend required — always works locally)
pytest testing/tests/MYTUBE-179/test_mytube_179.py -v

# Live mode (tests against real deployed app)
API_BASE_URL=https://your-api.run.app \
  WEB_BASE_URL=https://ai-teammate.github.io/mytube \
  pytest testing/tests/MYTUBE-179/test_mytube_179.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarEnterKey::test_url_redirects_to_search_path PASSED
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarEnterKey::test_url_contains_query_param PASSED
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarEnterKey::test_results_heading_contains_term PASSED
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarEnterKey::test_video_cards_are_rendered PASSED
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarEnterKey::test_video_card_hrefs_point_to_watch_page PASSED
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarButtonClick::test_url_redirects_to_search_path PASSED
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarButtonClick::test_url_contains_query_param PASSED
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarButtonClick::test_results_heading_contains_term PASSED
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarButtonClick::test_video_cards_are_rendered PASSED
testing/tests/MYTUBE-179/test_mytube_179.py::TestSearchBarButtonClick::test_video_card_hrefs_point_to_watch_page PASSED
```

## Preconditions

**Live mode**: A user with username `tester` must exist and have at least one
video in `ready` status in the backend database.

**Fixture mode**: No external services required.

## New components

- `testing/components/pages/search_page/search_page.py` — `SearchPage` page object
