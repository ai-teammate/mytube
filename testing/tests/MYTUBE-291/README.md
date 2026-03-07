# MYTUBE-291 — Direct navigation to category page on static deployment

Verifies that when navigating directly to a category URL on the GitHub Pages
static deployment, the dynamic route parameter (category ID) is correctly
preserved and the page loads the expected category content.

## Dependencies

```bash
pip install playwright pytest
playwright install chromium
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed web app base URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms |

## Preconditions

- Application is deployed to GitHub Pages (static hosting).
- Category 1 (Education) must have at least one video in the deployed database.

## Running the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-291/test_mytube_291.py -v
```

## Expected output (passing)

```
PASSED test_url_is_not_redirected_to_placeholder
PASSED test_category_heading_is_present
PASSED test_video_grid_is_populated
PASSED test_no_invalid_category_error
```

## Notes

The test spec uses category 3 (Gaming) as an example, but the test is
implemented against category 1 (Education) because the deployed database
currently has videos only for that category. The routing mechanism tested is
identical across all categories.
