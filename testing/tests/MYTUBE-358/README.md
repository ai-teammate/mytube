# MYTUBE-358 — Access My Videos page while authenticated

## Objective
Verify that the `/my-videos` route is correctly implemented and accessible to authenticated users.

## Preconditions
- User is logged in with a valid Firebase session (set `FIREBASE_TEST_EMAIL` and `FIREBASE_TEST_PASSWORD`).

## Steps
1. Navigate directly to `/my-videos` while authenticated.

## Expected Result
The page loads successfully. The URL stays on `/my-videos` with no redirect to `/` or `/login`. The `DashboardContent` component (video table or upload CTA) is visible.

## Environment Variables
| Variable | Description | Default |
|---|---|---|
| `FIREBASE_TEST_EMAIL` | Registered Firebase test user email | — (required) |
| `FIREBASE_TEST_PASSWORD` | Firebase test user password | — (required) |
| `APP_URL` / `WEB_BASE_URL` | Base URL of the deployed app | `https://ai-teammate.github.io/mytube` |
| `PLAYWRIGHT_HEADLESS` | Run browser headless | `true` |
| `PLAYWRIGHT_SLOW_MO` | Slow-motion delay in ms | `0` |
