# MYTUBE-598 — Access playlist detail page with invalid UUID format

## Objective

Verify that the system handles a malformed playlist ID gracefully:
- The backend UUID validation guard returns **HTTP 400 Bad Request**.
- The UI displays a specific error or "not found" message rather than the generic
  "Could not load playlist. Please try again later." connection-failure string.

## Test Type

`e2e` — two layers:

| Layer | Description |
|-------|-------------|
| **API** | Direct HTTP call via `PlaylistApiService` — asserts HTTP 400 for `GET /api/playlists/not-a-valid-uuid-123` |
| **UI**  | Playwright browser test — asserts the UI shows a meaningful error, not a generic failure |

## Test Steps

1. Log in as the CI test user.
2. Navigate to `/pl/not-a-valid-uuid-123/`.
3. Intercept the `GET /api/playlists/not-a-valid-uuid-123` API response.
4. Assert the API responded with HTTP 400.
5. Assert the UI does **not** show the generic "Could not load playlist" message.
6. Assert the UI shows either `Playlist not found.` or an error alert.

## Expected Result

- `GET /api/playlists/not-a-valid-uuid-123` → HTTP 400 (backend `isValidUUID` guard fires).
- UI shows a user-friendly specific error, not the generic connection-failure string.

## Architecture

- `PlaylistApiService` (`testing/components/services/playlist_api_service.py`) — HTTP layer.
- `PlaylistPage` (`testing/components/pages/playlist_page/playlist_page.py`) — UI page object.
- `LoginPage` (`testing/components/pages/login_page/login_page.py`) — authentication.
- `WebConfig` (`testing/core/config/web_config.py`) — centralised env var access.

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (`pip install playwright && playwright install chromium`)

## Environment Variables

| Variable               | Description                                          | Default |
|------------------------|------------------------------------------------------|---------|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app              | `https://ai-teammate.github.io/mytube` |
| `API_BASE_URL`         | Deployed API base URL                                | `https://mytube-api-80693608388.us-central1.run.app` |
| `FIREBASE_TEST_EMAIL`  | CI test user email                                   | — |
| `FIREBASE_TEST_PASSWORD` | CI test user password                              | — |
| `PLAYWRIGHT_HEADLESS`  | Run browser headless                                 | `true` |
| `PLAYWRIGHT_SLOW_MO`   | Slow-motion delay in ms                              | `0` |

## Running

```bash
# From the repository root:
pytest testing/tests/MYTUBE-598/test_mytube_598.py -v
```
