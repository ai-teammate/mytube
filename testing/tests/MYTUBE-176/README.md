# MYTUBE-176 — Browse videos by category (API + Web UI)

Automates the test case: verify that the category browse API and UI correctly
filter content by category ID.

## What is tested

| # | Layer | Endpoint / URL |
|---|-------|----------------|
| 1 | API   | `GET /api/videos?category_id=<id>&limit=20` |
| 2 | API   | `GET /api/categories` (to discover the Gaming category ID) |
| 3 | Web   | `/category/<id>/` (Playwright / Chromium) |

## Dependencies

```
pip install pytest playwright
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_BASE_URL` | `https://mytube-api-80693608388.us-central1.run.app` | Backend API base URL |
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Frontend base URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Set to `false` to watch the browser |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

No database access, no authentication, no secrets required — the test runs
entirely against the deployed public API and web app.

## Run

From the repository root:

```bash
python -m pytest testing/tests/MYTUBE-176/test_mytube_176.py -v
```

### Example with explicit API URL

```bash
API_BASE_URL=https://mytube-api-80693608388.us-central1.run.app \
APP_URL=https://ai-teammate.github.io/mytube \
python -m pytest testing/tests/MYTUBE-176/test_mytube_176.py -v
```

## Expected output when passing

```
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseAPI::test_api_returns_200_for_valid_category
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseAPI::test_api_returns_json_array
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseAPI::test_api_result_count_within_limit
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseAPI::test_video_cards_have_required_fields
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseAPI::test_missing_category_id_returns_400
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseAPI::test_invalid_category_id_returns_400
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseAPI::test_nonexistent_category_returns_empty_array
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseAPI::test_different_categories_return_different_results
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseUI::test_category_page_loads_without_error
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseUI::test_category_page_shows_heading
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseUI::test_category_page_heading_matches_category_name
PASSED testing/tests/MYTUBE-176/test_mytube_176.py::TestCategoryBrowseUI::test_category_page_is_not_loading
```
