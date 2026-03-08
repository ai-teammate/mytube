# MYTUBE-376: Transcoder failure with CLEANUP_ON_TRANSCODE_FAILURE=false — artifacts retained

## Objective

Verify that the transcoder cleanup logic respects the `CLEANUP_ON_TRANSCODE_FAILURE=false`
configuration flag. When a transcoding job fails permanently, any partial HLS artifacts already
present in the output bucket must **not** be deleted.

## Preconditions

- GCP credentials available via `GOOGLE_APPLICATION_CREDENTIALS`.
- The `mytube-transcoder` Cloud Run Job is deployed in the configured project and region.
- The `mytube-hls-output` GCS bucket is accessible by the service account.

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | ✅ Yes | _(none)_ | Path to service account key JSON |
| `GCP_PROJECT_ID` | No | `ai-native-478811` | GCP project ID |
| `GCP_REGION` | No | `us-central1` | GCP region |
| `GCP_HLS_BUCKET` | No | `mytube-hls-output` | HLS output bucket name |
| `GCP_RAW_BUCKET` | No | `mytube-raw-uploads` | Raw uploads bucket name |
| `GCP_TRANSCODER_JOB` | No | `mytube-transcoder` | Cloud Run Job name |
| `CDN_BASE_URL` | No | `https://cdn.example.com` | CDN base URL |
| `TRANSCODER_FAILURE_WAIT_SECONDS` | No | `300` | Max seconds to wait for job failure |

## Test Steps

1. **Pre-seed partial HLS artifacts** — Upload fake `index.m3u8`, `360p.m3u8`, and
   `seg-0000.ts` under `videos/{TEST_VIDEO_ID}/` in the `mytube-hls-output` bucket to
   simulate files created by a partially completed transcoding run.
2. **Trigger a permanently failing job** — Execute the `mytube-transcoder` Cloud Run Job with
   `RAW_OBJECT_PATH` pointing to a non-existent GCS object and
   `CLEANUP_ON_TRANSCODE_FAILURE=false`. The download step fails immediately, causing the
   job to exit with a non-zero exit code.
3. **Verify artifacts are retained** — After the job fails, assert that all pre-seeded partial
   HLS artifacts still exist in the bucket (i.e., cleanup did not run).

## Expected Result

The job exits with a non-zero status but the partial HLS artifacts in `mytube-hls-output`
are retained because `CLEANUP_ON_TRANSCODE_FAILURE=false` disables the cleanup path.

## Run the test

From the repository root:

```bash
GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json \
  pytest testing/tests/MYTUBE-376/test_mytube_376.py -v
```

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_376.py` | Pytest test implementation |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
