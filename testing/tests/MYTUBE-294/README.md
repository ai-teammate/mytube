# MYTUBE-294 — Refresh user profile page on static deployment

Verifies that performing a browser refresh on a user profile page in a static
(GitHub Pages) deployment does not produce a "User not found" error or a
broken URL stuck at `/u/_/`.

## What is tested

| Layer | URL pattern |
|-------|-------------|
| Web   | `/u/tester` → refresh → URL preserved as `/u/tester/` |

The test exercises the full SPA 404-fallback refresh cycle:

1. Navigate to `/u/tester` — GitHub Pages `404.html` fires, stores username in
   `sessionStorage`, and redirects to the `/u/_/` shell.
2. Shell reads `sessionStorage`, corrects the URL via `history.replaceState`,
   and loads the profile (heading + video grid visible).
3. Browser refresh (`page.reload()`) — the 404-fallback chain runs again.
4. After reload: URL is `/u/tester/` (not `/u/_/`), no "User not found" error,
   profile heading and video grid are visible.

## Test modes

**Fixture mode** (default in CI): a local HTTP server on port 19294 replicates
the GitHub Pages SPA fallback behaviour — 404.html redirect, shell page, and
mock API endpoints.

**Live mode**: used automatically when `WEB_BASE_URL` points to a deployed
environment where `/u/tester` renders the profile `<h1>` heading within 10 s.

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

## Run

From the repository root:

```bash
python -m pytest testing/tests/MYTUBE-294/test_mytube_294.py -v
```

## Expected output when passing

```
PASSED TestProfilePageRefresh::test_initial_profile_loads
PASSED TestProfilePageRefresh::test_url_after_initial_load
PASSED TestProfilePageRefresh::test_profile_content_visible_after_refresh
PASSED TestProfilePageRefresh::test_url_preserved_after_refresh
PASSED TestProfilePageRefresh::test_video_grid_visible_after_refresh
```
