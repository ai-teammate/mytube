# MYTUBE-238 — Profile page handles playlists API error gracefully

## What this test verifies

Intercepts `GET /api/users/:username/playlists` with a 500 Internal Server Error
and verifies that the profile page at `/u/tester`:

- Does not crash (no uncaught JS errors)
- Still displays the username heading and avatar
- Still shows the Videos tab
- Does not render a React error boundary
- Resolves the playlists loading state (not stuck spinning)
- Shows a graceful error message, empty state, or hides the playlists tab

## Dependencies

```
playwright>=1.40.0
pytest>=7.0.0
```

Install:

```bash
pip install playwright pytest
playwright install chromium
```

## How to run

From the repository root:

```bash
cd /path/to/mytube
pytest testing/tests/MYTUBE-238/test_mytube_238.py -v
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `APP_URL` / `WEB_BASE_URL` | `https://ai-teammate.github.io/mytube` | Deployed frontend URL |
| `PLAYWRIGHT_HEADLESS` | `true` | Set to `false` to watch the browser |
| `PLAYWRIGHT_SLOW_MO` | `0` | Slow-motion delay in ms for debugging |

No Firebase credentials are required — this test does not log in.

## Expected output when all tests pass

```
testing/tests/MYTUBE-238/test_mytube_238.py::TestProfilePagePlaylistsApiError::test_page_does_not_crash PASSED
testing/tests/MYTUBE-238/test_mytube_238.py::TestProfilePagePlaylistsApiError::test_username_heading_is_visible PASSED
testing/tests/MYTUBE-238/test_mytube_238.py::TestProfilePagePlaylistsApiError::test_avatar_is_visible PASSED
testing/tests/MYTUBE-238/test_mytube_238.py::TestProfilePagePlaylistsApiError::test_videos_tab_is_accessible PASSED
testing/tests/MYTUBE-238/test_mytube_238.py::TestProfilePagePlaylistsApiError::test_no_react_error_boundary PASSED
testing/tests/MYTUBE-238/test_mytube_238.py::TestProfilePagePlaylistsApiError::test_playlists_section_not_stuck_loading PASSED
testing/tests/MYTUBE-238/test_mytube_238.py::TestProfilePagePlaylistsApiError::test_playlists_section_shows_graceful_state PASSED
```

## Notes

- If the test is **skipped**, it means the GitHub Pages static export did not
  pre-generate the `/u/tester` route. The route interception logic is correct
  but requires the deployed SPA to render the profile component.
- The playlists API is intercepted via `page.route("**/api/users/*/playlists", ...)`
  before navigation, so the mock is active from the first page load.
