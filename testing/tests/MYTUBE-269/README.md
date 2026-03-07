# MYTUBE-269: Browse category with no assigned videos — empty state message displayed

## Objective

Verify the frontend correctly renders an empty state when a category exists but contains no videos.

## Test Strategy

This test:

1. **Discovers an empty category** via the API (`GET /api/categories` and `GET /api/videos?category_id=<id>`)
2. **Navigates to the category page** in a browser (`/category/<id>/`)
3. **Verifies empty state rendering:**
   - Page loads without error
   - Heading is visible
   - No video cards are present
   - User-friendly empty message is displayed: "No videos in this category yet."

## Running the Test

```bash
# From the repo root:
pytest testing/tests/MYTUBE-269/test_mytube_269.py -v

# With environment variables:
APP_URL=https://my-deployed-app.com pytest testing/tests/MYTUBE-269/test_mytube_269.py -v
```

## Environment Variables

| Variable              | Default                                              | Required |
| --------------------- | ---------------------------------------------------- | -------- |
| `API_BASE_URL`        | `https://mytube-api-80693608388.us-central1.run.app` | No       |
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube`             | No       |
| `PLAYWRIGHT_HEADLESS` | `true`                                               | No       |
| `PLAYWRIGHT_SLOW_MO`  | `0`                                                  | No       |

## Notes

- The test dynamically discovers a category with zero videos at runtime.
- If no empty category exists in the test data, the test is skipped.
- Uses the `CategoryPage` page object and `CategoryBrowseService` API service for clean, maintainable test code.
