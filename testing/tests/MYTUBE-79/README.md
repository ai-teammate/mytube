# MYTUBE-79 — Update video record on success

Verifies that after the transcoding Cloud Run Job completes, the `videos` table
row for the processed video is updated with the correct `status`, `hls_manifest_path`,
and `thumbnail_url` values.

## What is tested

1. A video row is inserted with status `'processing'` (matching the precondition).
2. The same `UPDATE` SQL the transcoder's `video.Repository.UpdateVideo` executes is applied.
3. The updated row is queried and asserted to have:
   - `status = 'ready'`
   - `hls_manifest_path = 'gs://mytube-hls-output/videos/{VIDEO_ID}/index.m3u8'`
   - `thumbnail_url` set to the CDN-based path `{CDN_BASE_URL}/videos/{VIDEO_ID}/thumbnail.jpg`

## Dependencies

- Python 3.11+
- `psycopg2-binary`
- `pytest`
- A running PostgreSQL instance reachable via the environment variables below

Install:

```bash
pip install psycopg2-binary pytest
```

## Environment variables

| Variable       | Default                    | Description                              |
|----------------|----------------------------|------------------------------------------|
| `DB_HOST`      | `localhost`                | PostgreSQL host                          |
| `DB_PORT`      | `5432`                     | PostgreSQL port                          |
| `DB_USER`      | `testuser`                 | Database user                            |
| `DB_PASSWORD`  | `testpass`                 | Database password                        |
| `DB_NAME`      | `mytube_test`              | Database name                            |
| `SSL_MODE`     | `disable`                  | SSL mode (`disable` / `require`)         |
| `GCP_HLS_BUCKET` | `mytube-hls-output`      | HLS output bucket name                   |
| `CDN_BASE_URL` | `https://cdn.example.com`  | CDN base URL for thumbnail path          |

## How to run

From the repository root:

```bash
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
