# MYTUBE-570 — Video watch page loading: skeleton placeholders

Verifies that skeleton screens are displayed on the watch page for both the
video player container and the metadata section while data is loading.

## Objective

Confirm that skeleton placeholder UI is immediately visible for the player
area and the title/metadata section whenever a user navigates to a video watch
page, eliminating UI flicker and providing a smooth perceived-performance
experience.

## Modes

| Mode | When it runs | Tests |
|------|-------------|-------|
| Static source analysis | Always | 7 |
| Live Playwright | When `APP_URL` is set | 2 |

### Static analysis (always runs)

Parses `web/src/app/v/[id]/WatchPageSkeleton.tsx` and
`web/src/app/v/[id]/WatchPageClient.tsx` and asserts:

- `WatchPageSkeleton.tsx` exists in the watch page route directory.
- `WatchPageSkeleton` renders a player-area skeleton placeholder (CSS class
  `playerFill`, `playerContainer`, or `player-fill`).
- `WatchPageSkeleton` renders title/metadata skeleton elements.
- `WatchPageSkeleton` uses at least 2 `<Skeleton>` components.
- `WatchPageClient` returns `<WatchPageSkeleton />` while `loading` is `true`.
- `WatchPageClient` initialises `loading` state as `true`.
- `WatchPageSkeleton` imports the `Skeleton` base component.

### Live Playwright (requires `APP_URL`)

1. **Skeleton visible while API stalled** — Intercepts `GET /api/videos/**`
   via Playwright route, navigates to `/v/_/`, waits for the route to be
   reached, then asserts `aria-hidden="true"` skeleton divs are present in
   both `<main>` (≥ 2) and `<aside>` (≥ 1). Releases the route with a 404
   after assertions complete.

2. **Skeleton disappears after API responds** — Intercepts `GET /api/videos/**`
   and immediately fulfils with 404. Asserts that all `aria-hidden="true"`
   skeleton divs in `<main>` disappear once the not-found state renders.

## Run

```bash
# Static analysis only (default — no browser required)
pytest testing/tests/MYTUBE-570/test_mytube_570.py -v

# Live mode (requires a running app)
APP_URL=http://localhost:3000 pytest testing/tests/MYTUBE-570/test_mytube_570.py -v
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed web app | `https://ai-teammate.github.io/mytube` |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |

## Files

| File | Purpose |
|------|---------|
| `test_mytube_570.py` | Test implementation (Layer A static + Layer B live) |
| `config.yaml` | Test configuration (timeouts, browser, env var names) |
| `__init__.py` | Package marker |
