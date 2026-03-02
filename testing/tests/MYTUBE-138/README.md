# MYTUBE-138: Upload video — real-time progress bar updates during transfer

Automates the test case that verifies the frontend displays a real-time
progress indicator while a video file is being uploaded to GCS.

## What is tested

- The progress bar container (`aria-label="upload progress"`) appears when
  upload starts.
- The upload completes successfully (progress reaches 100% or page redirects
  to `/dashboard`).
- The phase label shows `"Upload complete"` or the page navigates to the
  dashboard (implicit completion).
- Any captured `aria-valuenow` values are integers in `[0, 100]`.
- No error alert is visible after a successful upload.

## Strategy

### Authentication
A fresh Firebase account is registered via the `/register` page for each test
run using the Firebase Auth Emulator. No pre-existing credentials or secrets
are required — only `APP_URL` pointing to the running app.

### Network interception
Network calls are intercepted via Playwright's `page.route()`:

| Intercepted call | Response |
|-----------------|----------|
| `POST **/api/videos` | `{"video_id": "test-video-id-138", "upload_url": "https://fake-gcs.example.com/..."}` |
| `PUT https://fake-gcs.example.com/**` | `200 OK` (empty body) |

This makes the test hermetic — no live backend or GCS required.

## Dependencies

Install via pip (from the repo root):

```bash
pip install pytest playwright psycopg2-binary
playwright install chromium
```

## Prerequisites

A local Next.js dev server and Firebase Auth Emulator must be running:

```bash
# 1. Start the Firebase Auth Emulator
mkdir -p /tmp/firebase-emulator
cat > /tmp/firebase-emulator/firebase.json << 'JSON'
{ "emulators": { "auth": { "port": 9099 } } }
JSON
cat > /tmp/firebase-emulator/.firebaserc << 'JSON'
{ "projects": { "default": "demo-mytube-test" } }
JSON
cd /tmp/firebase-emulator && firebase emulators:start --only auth --project demo-mytube-test &

# 2. Start the Next.js dev server (from web/)
NEXT_PUBLIC_FIREBASE_API_KEY=demo-key \
NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN=demo-mytube-test.firebaseapp.com \
NEXT_PUBLIC_FIREBASE_PROJECT_ID=demo-mytube-test \
NEXT_PUBLIC_USE_FIREBASE_EMULATOR=true \
NEXT_PUBLIC_API_URL=http://localhost:9999 \
npm run dev -- --port 3000 &
```

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_URL` | No | URL of the running web app (default: `https://ai-teammate.github.io/mytube`) |
| `PLAYWRIGHT_HEADLESS` | No | Run headless (default: `true`) |
| `PLAYWRIGHT_SLOW_MO` | No | Slow-motion delay in ms (default: `0`) |

## How to run

From the repository root:

```bash
APP_URL=http://localhost:3000 pytest testing/tests/MYTUBE-138/test_mytube_138.py -v
```

## Expected output when tests pass

```
testing/tests/MYTUBE-138/test_mytube_138.py::TestUploadProgressBar::test_progress_bar_appears_when_upload_starts PASSED
testing/tests/MYTUBE-138/test_mytube_138.py::TestUploadProgressBar::test_progress_bar_shows_100_or_upload_succeeded PASSED
testing/tests/MYTUBE-138/test_mytube_138.py::TestUploadProgressBar::test_upload_complete_or_redirect PASSED
testing/tests/MYTUBE-138/test_mytube_138.py::TestUploadProgressBar::test_progress_values_are_valid_if_captured PASSED
testing/tests/MYTUBE-138/test_mytube_138.py::TestUploadProgressBar::test_no_error_message_after_upload PASSED

5 passed
```
