# MYTUBE-373: Delete video via API — raw and HLS files deleted from GCS

## Objective

Verify that deleting a video via the API correctly removes associated raw upload files and HLS
output artifacts from GCS buckets when `DELETE_ON_VIDEO_DELETE=true`.

## Preconditions

- A video exists with a valid `gcs_raw_path` in `mytube-raw-uploads`.
- Transcoded HLS files exist in `mytube-hls-output` under the expected prefix.
- Environment variable `DELETE_ON_VIDEO_DELETE` is set to `true`.

## Test Layers

### Layer A — Go unit tests (always runs, no DB/GCS needed)

Runs the existing Go handler unit tests (`TestDeleteVideo`) with `DELETE_ON_VIDEO_DELETE=true` to
confirm the deletion path is exercised. Exercises:

- `DELETE /api/videos/:id` returns 204 when GCS cleanup is enabled.
- GCS cleanup is invoked for both the raw file and HLS prefix.
- GCS cleanup disabled (`DELETE_ON_VIDEO_DELETE=false`) skips GCS calls.
- GCS errors do not affect the HTTP 204 response (best-effort cleanup).

### Layer B — Integration test via HTTP + DB (requires `FIREBASE_TEST_TOKEN`)

1. Seeds a user and video row in the DB with synthetic `gcs_raw_path` and `hls_manifest_path`.
2. Starts the Go API binary with `DELETE_ON_VIDEO_DELETE=true`.
3. Issues an authenticated `DELETE /api/videos/:id` request.
4. Asserts HTTP 204 No Content.
5. Asserts the video's DB status is `'deleted'` (soft-deleted).
6. Asserts `GET /api/videos/:id` returns 404 (video no longer visible).
7. Asserts the raw file is absent from `mytube-raw-uploads` (GCS — skipped without real creds).
8. Asserts all HLS artifacts are absent from `mytube-hls-output` (GCS — skipped without real creds).

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `FIREBASE_TEST_TOKEN` | ✅ Yes (Layer B) | Firebase ID token for authenticated DELETE request. |
| `FIREBASE_PROJECT_ID` | ✅ Yes (Layer B) | Firebase project ID for the API server. |
| `FIREBASE_TEST_UID` | No | UID embedded in the test token. Default: `test-uid-mytube-373`. |
| `API_BINARY` | No | Path to pre-built Go binary. Default: `<repo_root>/api/mytube-api`. |
| `DB_HOST` | No | Database host. Default: `localhost`. |
| `DB_PORT` | No | Database port. Default: `5432`. |
| `DB_USER` | No | Database user. Default: `postgres`. |
| `DB_PASSWORD` | No | Database password. Default: `postgres`. |
| `DB_NAME` | No | Database name. Default: `mytube`. |
| `SSL_MODE` | No | SSL mode for DB connection. Default: `disable`. |
| `GOOGLE_APPLICATION_CREDENTIALS` | No | Path to service-account JSON. Defaults to `testing/fixtures/mock_service_account.json`. |
| `GCS_RAW_UPLOADS_BUCKET` | No | Raw-uploads bucket name. Default: `mytube-raw-uploads`. |
| `HLS_BUCKET` | No | HLS-output bucket name. Default: `mytube-hls-output`. |

## Enabling Live GCS Assertions

Steps 3–4 of the ticket (GCS bucket presence checks) are **skipped by default** when using the
mock service-account fixture. To enable them:

1. Obtain a real GCS service-account JSON key with read access to `mytube-raw-uploads` and
   `mytube-hls-output`.
2. Set `GOOGLE_APPLICATION_CREDENTIALS=/path/to/real-key.json` before running.
3. Install the GCS client library: `pip install google-cloud-storage`.

The tests will then verify that the raw file and all HLS objects under
`videos/<video_id>/` are absent after deletion.

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_373.py` | Test implementation (Layer A Go unit tests + Layer B integration) |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
| `README.md` | This file |
