# MYTUBE-139: Complete video upload — user redirected to dashboard with processing status

## What this test verifies

End-to-end upload flow:
1. Authenticated user fills the `/upload` form and selects a video file.
2. Upload progresses to 100%.
3. Application redirects to `/dashboard?uploaded=<videoId>`.
4. Dashboard renders (not a 404 page).
5. Uploaded video appears with a **"Processing"** status.

## Dependencies

| Dependency | Notes |
|---|---|
| `playwright` | `pip install playwright && playwright install chromium` |
| `pytest` | `pip install pytest` |
| Firebase test account | Real credentials required — no emulator |
| Deployed web app | Must be running and accessible at `WEB_BASE_URL` |
| Backend API | Must be running to accept `POST /api/videos` and issue signed GCS URLs |

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `FIREBASE_TEST_EMAIL` | Yes | — | Email of the registered Firebase test user |
| `FIREBASE_TEST_PASSWORD` | Yes | — | Password of the registered Firebase test user |
| `WEB_BASE_URL` / `APP_URL` | No | `https://ai-teammate.github.io/mytube` | Base URL of the web app |
| `PLAYWRIGHT_HEADLESS` | No | `true` | Set to `false` to watch the browser |
| `PLAYWRIGHT_SLOW_MO` | No | `0` | Slow-motion delay in ms for debugging |

## How to run

```bash
# From the repository root
cd /path/to/mytube

# Install Python dependencies
pip install pytest playwright
playwright install chromium

# Run the test
FIREBASE_TEST_EMAIL=your@email.com \
FIREBASE_TEST_PASSWORD=yourpassword \
pytest testing/tests/MYTUBE-139/test_mytube_139.py -v
```

## Expected output when the test passes

```
testing/tests/MYTUBE-139/test_mytube_139.py::TestUploadRedirectsToDashboard::test_redirected_to_dashboard_url PASSED
testing/tests/MYTUBE-139/test_mytube_139.py::TestUploadRedirectsToDashboard::test_dashboard_url_has_uploaded_query_param PASSED
testing/tests/MYTUBE-139/test_mytube_139.py::TestUploadRedirectsToDashboard::test_dashboard_page_renders_not_404 PASSED
testing/tests/MYTUBE-139/test_mytube_139.py::TestUploadRedirectsToDashboard::test_uploaded_video_shows_processing_status PASSED
```

## Notes

- The test creates a minimal valid MP4 file at runtime — no large video fixtures required.
- The test video is uploaded to the real GCS bucket; it will remain in `pending` or `processing` state. Manual cleanup may be needed.
- The entire module is skipped automatically if `FIREBASE_TEST_EMAIL` or `FIREBASE_TEST_PASSWORD` is not set.
