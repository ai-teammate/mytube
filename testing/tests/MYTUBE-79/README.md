# MYTUBE-79 — Update video record on success

Verifies that after the transcoding Cloud Run Job completes, the `videos` table
row for the processed video is updated with the correct `status`, `hls_manifest_path`,
and `thumbnail_url` values.

## What is tested

1. A video row is inserted with status `'processing'` (matching the precondition).
2. The Cloud Run transcoding job is executed via `HLSTranscoderService` for that video ID.
3. The `videos` table is queried and the row written by the transcoder is asserted to have:
   - `status = 'ready'`
   - `hls_manifest_path = 'gs://mytube-hls-output/videos/{VIDEO_ID}/index.m3u8'`
   - `thumbnail_url` set to the CDN-based path `{CDN_BASE_URL}/videos/{VIDEO_ID}/thumbnail.jpg`

## Dependencies

- Python 3.11+
- `psycopg2-binary`
- `pytest`
- `google-cloud-storage`
- `gcloud` CLI authenticated with sufficient permissions
- A running PostgreSQL instance reachable via the environment variables below

Install:

```bash
pip install psycopg2-binary pytest google-cloud-storage
```

## Environment variables

| Variable                       | Required | Default             | Description                                               |
|-------------------------------|----------|---------------------|-----------------------------------------------------------|
| `GCP_PROJECT_ID`              | **Yes**  | —                   | GCP project containing the Cloud Run Job                  |
| `GCP_REGION`                  | No       | `us-central1`       | Region of the Cloud Run Job                               |
| `GCP_HLS_BUCKET`              | No       | `mytube-hls-output` | HLS output bucket name                                    |
| `GCP_TRANSCODER_JOB`          | No       | `mytube-transcoder` | Cloud Run Job name                                        |
| `RAW_OBJECT_PATH`             | **Yes**  | —                   | GCS object path of the raw video (e.g. `raw/abc123.mp4`)  |
| `DB_DSN`                      | No       | built from DB_* vars| Full PostgreSQL DSN for the transcoding job               |
| `DB_HOST`                     | No       | `localhost`         | PostgreSQL host                                           |
| `DB_PORT`                     | No       | `5432`              | PostgreSQL port                                           |
| `DB_USER`                     | No       | `testuser`          | Database user                                             |
| `DB_PASSWORD`                 | No       | `testpass`          | Database password                                         |
| `DB_NAME`                     | No       | `mytube_test`       | Database name                                             |
| `SSL_MODE`                    | No       | `disable`           | SSL mode (`disable` / `require`)                          |
| `CDN_BASE_URL`                | No       | `https://cdn.example.com` | CDN base URL for thumbnail path assertion           |
| `GOOGLE_APPLICATION_CREDENTIALS` | No    | ADC                 | Path to GCP service account key file                      |

The test skips automatically when `GCP_PROJECT_ID` or `RAW_OBJECT_PATH` is not set.

## How to run

From the repository root:

```bash
export GCP_PROJECT_ID=my-gcp-project
export RAW_OBJECT_PATH=raw/some-video.mp4
pytest testing/tests/MYTUBE-79/test_mytube_79.py -v
```

## Expected output (passing)

```
testing/tests/MYTUBE-79/test_mytube_79.py::TestVideoRecordUpdatedOnSuccess::test_status_is_ready PASSED
testing/tests/MYTUBE-79/test_mytube_79.py::TestVideoRecordUpdatedOnSuccess::test_hls_manifest_path_matches_expected_pattern PASSED
testing/tests/MYTUBE-79/test_mytube_79.py::TestVideoRecordUpdatedOnSuccess::test_hls_manifest_path_contains_video_id PASSED
testing/tests/MYTUBE-79/test_mytube_79.py::TestVideoRecordUpdatedOnSuccess::test_hls_manifest_path_ends_with_index_m3u8 PASSED
testing/tests/MYTUBE-79/test_mytube_79.py::TestVideoRecordUpdatedOnSuccess::test_thumbnail_url_matches_cdn_path PASSED
testing/tests/MYTUBE-79/test_mytube_79.py::TestVideoRecordUpdatedOnSuccess::test_thumbnail_url_contains_video_id PASSED
testing/tests/MYTUBE-79/test_mytube_79.py::TestVideoRecordUpdatedOnSuccess::test_thumbnail_url_ends_with_thumbnail_jpg PASSED

7 passed
```

## Expected output (when GCP env vars are not set)

```
SKIPPED [7] testing/tests/MYTUBE-79/test_mytube_79.py - GCP_PROJECT_ID is not set

7 skipped
```
