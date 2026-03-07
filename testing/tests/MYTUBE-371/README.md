# MYTUBE-371 Test

## Overview

End-to-end silent video processing — video status transitions to `ready`
and HLS manifest URL is written.

## What is tested

1. Upload a silent video file via the REST API (`POST /api/videos` to obtain a
   signed GCS URL, then `PUT` the file content to that URL).
2. Poll until the Eventarc trigger fires and the Cloud Run transcoding job
   completes (status transitions from `pending` → `processing` → `ready`).
3. Query the `videos` table directly: assert `status = 'ready'` and
   `hls_manifest_path IS NOT NULL`.
4. Assert that the manifest URL returned by `GET /api/videos/:id` is
   accessible via the configured CDN (HTTP 200).

## Environment variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `FIREBASE_TEST_TOKEN` | **yes** | — | Firebase ID token for authenticated upload |
| `API_BASE_URL` | **yes** | `http://localhost:8080` | Deployed API base URL |
| `SILENT_VIDEO_PATH` | no | auto-generated | Path to a silent `.mp4` file to upload |
| `E2E_POLL_TIMEOUT` | no | `600` | Seconds to wait for `status=ready` |
| `E2E_POLL_INTERVAL` | no | `10` | Seconds between status polls |
| `DB_HOST` / `DB_PORT` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` / `SSL_MODE` | no | test defaults | DB connection |

## Skip conditions

The test is skipped (not failed) when:

- `FIREBASE_TEST_TOKEN` is not set — a valid Firebase ID token is needed to
  call the authenticated upload endpoint.
- The API is unreachable.
- No GCS signed URL is returned (GCP credentials misconfigured in the API).

## Architecture

```
test_mytube_371.py
    └── POST /api/videos         (AuthService — gets signed URL + video_id)
    └── PUT  <signed_url>        (urllib — uploads silent video bytes to GCS)
    └── poll GET /api/videos/:id (VideoApiService — waits for status=ready)
    └── psycopg2                 (DB assertion — status, hls_manifest_path)
    └── urllib.request           (CDN assertion — manifest URL returns 200)
```
