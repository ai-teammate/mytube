# MYTUBE-582: Watch page recommendation visibility — section hidden when fewer than 2 results exist

## Objective

Verify that the "More like this" recommendation sidebar is hidden entirely when the backend
returns fewer than 2 recommendations (0 or 1 results).  The `RecommendationSidebar` component
returns `null` in this case, so no heading, placeholder, or empty-state message should appear.

## Preconditions

- The deployed web application is accessible at the URL defined by `WEB_BASE_URL` or `APP_URL`.
- Playwright with Chromium is installed in the test environment.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `WEB_BASE_URL` / `APP_URL` | No | Base URL of the deployed web app. Default: `https://ai-teammate.github.io/mytube`. |
| `API_BASE_URL` | No | Backend API base URL for video discovery. Default: `http://localhost:8081`. |
| `PLAYWRIGHT_HEADLESS` | No | Run browser headless. Default: `true`. |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms. Default: `0`. |

## Test Steps

1. **Fixture mode** — serve a local HTML page that mimics the null-render branch of
   `RecommendationSidebar` (0 recommendations). Assert "More like this" and
   "Recommendations coming soon" are absent using the `WatchPage` component.
2. **Live mode (0 results)** — navigate to the watch page via `WatchPage.navigate_to_video`,
   intercept `/api/videos/*/recommendations` to return `[]`, wait for the fetch to settle,
   assert sidebar heading is absent.
3. **Live mode (1 result)** — same as above but intercept returns a single-item list
   (below `MIN_RECOMMENDATIONS = 2`), assert sidebar remains hidden.

## Expected Result

- The `"More like this"` `<h2>` heading is **not** present in the DOM.
- No `"Recommendations coming soon"` placeholder text appears.
- The `RecommendationSidebar` renders `null` (no sidebar DOM node at all).

## How to Run Locally

```bash
# From the repository root
export WEB_BASE_URL=https://ai-teammate.github.io/mytube
pytest testing/tests/MYTUBE-582/test_mytube_582.py -v
```

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_582.py` | Dual-mode test: self-contained fixture + live Playwright route-intercept |
| `config.yaml` | Test metadata (framework, platform, dependencies) |

## Architecture

- **Fixture mode** always runs without network access — validates the null-render branch in isolation.
- **Live mode** tests skip automatically when the deployed app is unreachable.
- Navigation uses `WatchPage.navigate_to_video()` (page object — no raw Playwright in tests).
- Sidebar assertions use `WatchPage.is_recommendation_sidebar_present()` and
  `WatchPage.has_recommendations_placeholder()`.
- Browser setup/teardown is centralised in the `browser_page` pytest fixture.
- `VideoApiService` discovers a ready video ID; falls back to a placeholder UUID when none found.
