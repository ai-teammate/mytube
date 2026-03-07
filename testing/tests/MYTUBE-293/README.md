# MYTUBE-293 — Direct navigation to user profile on static deployment

## Scenario

Verifies that the SPA redirect mechanism on GitHub Pages correctly recovers a user's
profile when navigating directly to a deep URL such as `/u/<username>`.

GitHub Pages serves a custom `public/404.html` for any path it cannot resolve.
That script extracts the real username from the URL, stores it in
`sessionStorage['__spa_username']`, and redirects the browser to the shell path
`/u/_/`. The React component (`UserProfilePageClient`) then reads the key, calls
`history.replaceState` to restore the real URL, removes the key from sessionStorage,
and fetches the profile data for the recovered username.

### Test steps covered

| # | Test | Description |
|---|------|-------------|
| 1–2 | `test_direct_navigation_redirects_through_spa_shell` | Direct URL triggers 404.html; browser lands on `/u/_/` or the corrected URL |
| 2 | `test_spa_username_in_session_storage_after_redirect` | `sessionStorage['__spa_username']` contains the real username after redirect |
| 3 | `test_profile_content_rendered_after_spa_redirect` | Profile renders with avatar and `<h1>` heading for the CI test user |
| 4 | `test_url_corrected_back_to_real_username_after_mount` | Address bar is corrected to `/u/<username>/` via `history.replaceState` |
| 5 | `test_session_storage_cleared_after_component_mounts` | `sessionStorage['__spa_username']` is `null` after the component mounts |

## Preconditions

- The application is deployed to GitHub Pages at `https://ai-teammate.github.io/mytube`.
- **The CI test user must exist** in the deployed application's Firestore database.
  The username is derived from `FIREBASE_TEST_EMAIL` (the prefix before `@`).
  Default: `ci-test` (from `ci-test@mytube.test`).

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Base URL of the deployed app |
| `FIREBASE_TEST_EMAIL` | `ci-test@mytube.test` | Email of the CI test Firebase user; username derived from prefix |
| `PLAYWRIGHT_HEADLESS` | `true` | Run browser headless |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms for debugging |

## Running locally

```bash
# From the repository root
cd testing
pip install -r requirements.txt
playwright install chromium

# Run against the deployed app (default)
pytest tests/MYTUBE-293/ -v

# Run with a specific base URL
APP_URL=http://localhost:3000 pytest tests/MYTUBE-293/ -v

# Run headed for debugging
PLAYWRIGHT_HEADLESS=false pytest tests/MYTUBE-293/ -v -s
```
