# MYTUBE-261 — Cancel video deletion in UI prompt — video remains in dashboard grid

Verifies that clicking Cancel in the video deletion confirmation prompt correctly aborts the deletion and keeps the video visible in the dashboard.

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
| `FIREBASE_TEST_EMAIL` | (required) | Test Firebase user email |
| `FIREBASE_TEST_PASSWORD` | (required) | Test Firebase user password |

## Preconditions

User is authenticated and viewing the /dashboard with at least one video, OR the test falls back to a local fixture server with a test video.

## Running the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-261/test_mytube_261.py -v
```

## Expected output (passing)

The test verifies that:
1. Delete button is visible and clickable for a video
2. Clicking Delete shows a confirmation prompt
3. Clicking Cancel in the prompt closes the dialog
4. The video remains visible in the dashboard
5. Video count is unchanged

## Test approach

### Live mode
When the dashboard renders with videos:
1. Navigate to `/dashboard`
2. Wait for videos table to load
3. Record the initial video count
4. Get the title of the first video
5. Click the Delete button for that video
6. Verify confirmation prompt appears
7. Click Cancel button
8. Verify video remains visible and count unchanged

### Fixture mode (fallback)
When the live dashboard is unavailable, a local HTTP server serves minimal HTML replicating the dashboard with video items and delete confirmation UI exactly as rendered by the app.
