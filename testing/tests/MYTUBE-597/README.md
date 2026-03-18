# MYTUBE-597 — Authenticated user navigates to playlist from dashboard

## Purpose

Regression test for **MYTUBE-592**: verifies that an authenticated user can navigate from the
Dashboard → My Playlists tab → click a playlist title, and the `/pl/[id]` page loads
successfully **without** the *"Could not load playlist. Please try again later."* error.

## Background

MYTUBE-592 identified that `PlaylistPageClient.tsx` was missing the GitHub Pages SPA
`sessionStorage` fallback (`__spa_playlist_id`). When navigating to a playlist via the dashboard
link, the GitHub Pages `404.html` SPA shell redirected the browser to `/pl/_/` and stored the
real UUID in `sessionStorage`. The component then sent `GET /api/playlists/_`, which failed
UUID validation → HTTP 400 → error message. The fix applies the same `history.replaceState`
pattern already used by `WatchPageClient` and `UserProfilePageClient`.

## Test Steps

1. Create a test playlist via `POST /api/playlists` (HTTP 201).
2. Log in via `/login/` using CI test credentials.
3. Navigate to `/dashboard/`.
4. Click the **"My playlists"** tab.
5. Wait for the playlist table to render with the test playlist visible.
6. Click the playlist title link (`<a href="/pl/<uuid>/">`).
7. Wait for the `/pl/[id]` page to load (networkidle).
8. Assert:
   - No *"Could not load playlist. Please try again later."* error is shown.
   - The playlist `<h1>` title is visible.
   - *"Playlist not found."* is not shown.
   - The page URL contains `/pl/`.

## Assertions

| Test | Description |
|------|-------------|
| `test_no_error_message` | Primary MYTUBE-592 regression check — no load error shown |
| `test_playlist_title_visible` | `<h1>` title rendered, confirming data loaded |
| `test_not_found_page_not_shown` | UUID not lost during SPA routing |
| `test_page_url_contains_playlist_id` | `history.replaceState` URL correction worked |

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app | `https://ai-teammate.github.io/mytube` |
| `API_BASE_URL` | Backend API base URL | `https://mytube-api-80693608388.us-central1.run.app` |
| `FIREBASE_API_KEY` | Firebase Web API key | — |
| `FIREBASE_TEST_EMAIL` | CI test user email | — |
| `FIREBASE_TEST_PASSWORD` | CI test user password | — |
| `FIREBASE_TEST_TOKEN` | Pre-obtained Firebase ID token (for API setup) | — |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

## Framework

- **Type**: Web UI (end-to-end)
- **Framework**: Playwright (sync API)
- **Browser**: Chromium
- **Page Objects**: `LoginPage`, `DashboardPage`, `PlaylistPage`
- **Services**: `PlaylistApiService`, `AuthService`, `WebConfig`
