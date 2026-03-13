# MYTUBE-583 — Recommendation UI: functional vertical list replaces placeholder

## Ticket Objective

Verify the frontend watch page correctly renders the new recommendation section using the standard `VideoCard` component.

**Expected Result**: The old placeholder text "Recommendations coming soon" is replaced by a "More like this" section containing a vertical list of `VideoCard` components. Each card displays the correct thumbnail, title, and metadata (uploader username, view count, date).

## Test Approach

### Layer A — Static Source Analysis (always runs)

Checks against actual source files without requiring a running app:

- `RecommendationSidebar.tsx` does **NOT** contain the old placeholder text "Recommendations coming soon"
- `RecommendationSidebar.tsx` contains an `<h2>More like this</h2>` heading
- `RecommendationSidebar.tsx` imports and renders the `VideoCard` component for each recommendation via `.map()`
- `RecommendationSidebar.module.css` defines a vertical flex list (`flex-direction: column`) within the `.list` rule
- `VideoCard.tsx` renders title, uploader username, and view count metadata

### Layer B — Fixture Browser Test (always runs, self-contained)

Starts a local HTTP server serving a minimal HTML page that replicates `RecommendationSidebar` with two `VideoCard` items. Verifies:

- "More like this" heading is visible
- "Recommendations coming soon" placeholder text is absent
- Two `VideoCard` items are rendered with thumbnail, title link, and metadata
- The `.list` container uses `flex-direction: column` (vertical stack)

### Layer C — Live Browser Test (conditional)

Runs only when `APP_URL`/`WEB_BASE_URL` is reachable **and** a video with ≥2 recommendations is found via the API:

- Uses `VideoApiService` to discover a ready video
- Checks the recommendations API endpoint for ≥2 results
- Navigates to the watch page
- Asserts the "More like this" heading and `VideoCard` items are visible
- Asserts "Recommendations coming soon" text is not present

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app | `https://ai-teammate.github.io/mytube` |
| `API_BASE_URL` | API base URL | `http://localhost:8081` |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

## Running Locally

```bash
# From repo root
pytest testing/tests/MYTUBE-583/test_mytube_583.py -v
```
