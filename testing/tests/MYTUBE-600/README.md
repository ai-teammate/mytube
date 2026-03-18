# MYTUBE-600 — API request to playlist endpoint uses correct NEXT_PUBLIC_API_URL and receives CORS headers

## Objective

Verify that the frontend correctly identifies the API server origin and that the
API server permits the cross-origin request. Specifically:

- The playlist API request URL is directed at the API server (as baked into the
  static build via `NEXT_PUBLIC_API_URL`) and **not** at the frontend CDN host.
- The API server returns correct CORS response headers (`Access-Control-Allow-Origin`,
  `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers`) for a cross-origin
  request from the frontend origin.

## Test Type

`api` + `e2e` — Layer A: direct HTTP CORS check; Layer B: Playwright request interception.

## Test Steps

### Layer A — Direct API CORS verification

1. Obtain a valid playlist ID (create a temporary playlist via the API if
   `FIREBASE_TEST_TOKEN` is available; otherwise fall back to the CI test user's
   existing playlists).
2. Send `GET /api/playlists/{id}` with an `Origin: https://ai-teammate.github.io` header.
3. Assert HTTP 200.
4. Assert the request URL host matches `API_BASE_URL` (not the CDN).
5. Assert `Access-Control-Allow-Origin` header is present and equals
   `https://ai-teammate.github.io`.
6. Assert `Access-Control-Allow-Methods` header is present.
7. Assert `Access-Control-Allow-Headers` header is present.

### Layer B — Playwright request-interception test

1. Inject `sessionStorage.__spa_playlist_id = <uuid>` (MYTUBE-592 SPA fix).
2. Navigate to the playlist shell page at `{WEB_BASE_URL}/pl/_/`.
3. Wait for the `GET /api/playlists/{id}` response using Playwright's event-driven
   `expect_response` (no fixed sleeps).
4. Assert the intercepted request URL host is **not** the frontend CDN host — it
   must be the API server host.
5. If response headers are available, assert `Access-Control-Allow-Origin` equals
   `https://ai-teammate.github.io`.

## Expected Result

- The request URL correctly points to the API server (`NEXT_PUBLIC_API_URL` host),
  **not** `ai-teammate.github.io` (the CDN).
- The response contains valid CORS headers confirming cross-origin access is
  permitted for the frontend origin.

## Architecture

- `PlaylistApiService` (`testing/components/services/playlist_api_service.py`)
  handles all HTTP operations including CORS-header fetch (`get_with_origin_header`)
  and API reachability check (`is_reachable`). No raw `urllib` calls in the test file.
- `APIConfig` (`testing/core/config/api_config.py`) centralises API URL config.
- `WebConfig` (`testing/core/config/web_config.py`) centralises web URL config.
- Playwright sync API for Layer B — uses `expect_response()` for event-driven waiting.
- Module-scoped `setup_module` / `teardown_module` manage playlist lifecycle.

## Linked Bugs

- **MYTUBE-592** (Done): Playlist detail page showed 'Could not load playlist' error.
  Fix: `PlaylistPageClient.tsx` now reads the real UUID from
  `sessionStorage.__spa_playlist_id` via a lazy state initialiser (same pattern as
  `WatchPageClient` and `UserProfilePageClient`).

## Prerequisites

- Python 3.10+
- `pytest`
- `playwright` (`pip install playwright && playwright install chromium`)

## Environment Variables

| Variable               | Description                                                              |
|------------------------|--------------------------------------------------------------------------|
| `API_BASE_URL`         | Backend API base URL. Default: `http://localhost:8080`                   |
| `APP_URL`              | Base URL of the deployed web app. Default: `https://ai-teammate.github.io/mytube` |
| `WEB_BASE_URL`         | Alias for `APP_URL`.                                                     |
| `FIREBASE_TEST_TOKEN`  | Firebase ID token for the CI test user. Required for playlist creation.  |
| `FIREBASE_TEST_EMAIL`  | Used to derive the CI test username (prefix before `@`). Default: `tester@example.com` |
| `PLAYWRIGHT_HEADLESS`  | Run browser headless. Default: `true`.                                   |
| `PLAYWRIGHT_SLOW_MO`   | Slow-motion delay in ms for debugging. Default: `0`.                     |

## Running

```bash
# From the repository root:
pytest testing/tests/MYTUBE-600/test_mytube_600.py -v
```
