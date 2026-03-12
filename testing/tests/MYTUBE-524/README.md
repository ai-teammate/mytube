# MYTUBE-524 — Dashboard empty state redesign: styled message and upload CTA displayed

## Objective

Verify the visual implementation of the empty state on the redesigned dashboard.
When a logged-in user has no uploaded videos, the dashboard must display:

1. A styled empty-state message using `var(--text-secondary)` colour (`#666666` in light mode).
2. A functional "Upload your first video" CTA link pointing to `/upload`.

## Test Type

`ui` — Playwright browser-based UI test (dual live/fixture mode).

## Test Structure

### Fixture mode (default — always runs)

Starts a local HTTP server serving minimal HTML that replicates the empty-state
section of the production dashboard (same CSS class names, `data-testid`
attributes, and `:root { --text-secondary: #666666 }` declaration).  No
credentials required.

### Live mode (requires `FIREBASE_TEST_EMAIL` + `FIREBASE_TEST_PASSWORD`)

- Logs in via the web app's Firebase login form.
- Navigates to `/dashboard/` — the CI test user is expected to have no videos.
- Asserts all structural and styling properties against the live deployed app.

## Tests

| # | Test | Assertion |
|---|------|-----------|
| 1 | `test_empty_state_message_is_visible` | Page body contains "You haven" (partial match) |
| 2 | `test_empty_state_uses_text_secondary_color` | Computed CSS `color` of `.emptyState` equals `rgb(102, 102, 102)` |
| 3 | `test_upload_cta_is_visible` | Upload CTA element is present and visible |
| 4 | `test_upload_cta_links_to_upload_page` | CTA anchor `href` contains `upload` |

## Source Code References

- `web/src/app/dashboard/_content.tsx` — empty state branch (`videos.length === 0`)
- `web/src/app/dashboard/_content.module.css` — `.emptyState { color: var(--text-secondary) }`

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (with Chromium browser installed: `playwright install chromium`)

## Environment Variables

| Variable                 | Required for | Description                                    |
|--------------------------|--------------|------------------------------------------------|
| `APP_URL` / `WEB_BASE_URL` | Live mode  | Base URL of the deployed web app.              |
| `FIREBASE_TEST_EMAIL`    | Live mode    | Firebase test user email.                      |
| `FIREBASE_TEST_PASSWORD` | Live mode    | Firebase test user password.                   |
| `PLAYWRIGHT_HEADLESS`    | Optional     | Run browser headless (default: `true`).        |
| `PLAYWRIGHT_SLOW_MO`     | Optional     | Slow-motion delay in ms (default: `0`).        |

## Running the Tests

```bash
# Fixture mode (no credentials needed):
pytest testing/tests/MYTUBE-524/test_mytube_524.py -v

# Live mode:
FIREBASE_TEST_EMAIL=user@example.com \
FIREBASE_TEST_PASSWORD=secret \
pytest testing/tests/MYTUBE-524/test_mytube_524.py -v
```

## Expected Output (fixture mode)

```
PASSED  TestDashboardEmptyState::test_empty_state_message_is_visible
PASSED  TestDashboardEmptyState::test_empty_state_uses_text_secondary_color
PASSED  TestDashboardEmptyState::test_upload_cta_is_visible
PASSED  TestDashboardEmptyState::test_upload_cta_links_to_upload_page
```
