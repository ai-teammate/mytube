# MYTUBE-78 — Transcode raw video to HLS

Verifies that the Cloud Run Job correctly transcodes a raw video file into the specified multi-bitrate HLS renditions, and that the master playlist defines 360p, 720p, and 1080p streams.

## Dependencies

```bash
pip install pytest google-cloud-storage
```

Google Cloud SDK (`gcloud`) must be installed and authenticated.

## Required Environment Variables

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT_ID` | GCP project containing the Cloud Run Job |
| `GCP_REGION` | Region of the Cloud Run Job (default: `us-central1`) |
| `GCP_HLS_BUCKET` | HLS output bucket name (default: `mytube-hls-output`) |
| `GCP_TRANSCODER_JOB` | Cloud Run Job name (default: `mytube-transcoder`) |
| `VIDEO_ID` | Video ID to transcode |
| `RAW_OBJECT_PATH` | GCS path to the raw video file (e.g. `raw/<uuid>.mp4`) |
| `DB_DSN` | PostgreSQL DSN passed to the transcoding job |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON (or use ADC) |

## How to Run

```bash
export GCP_PROJECT_ID=my-project
export GCP_REGION=us-central1
export VIDEO_ID=abc-123
export RAW_OBJECT_PATH=raw/abc-123.mp4
export DB_DSN="postgres://user:pass@host:5432/mytube"

pytest testing/tests/MYTUBE-78/test_mytube_78.py -v
```

## Expected Output When Passing

```
testing/tests/MYTUBE-78/test_mytube_78.py::TestHLSTranscoding::test_job_executes_successfully PASSED
testing/tests/MYTUBE-78/test_mytube_78.py::TestHLSTranscoding::test_output_bucket_contains_video_folder PASSED
testing/tests/MYTUBE-78/test_mytube_78.py::TestHLSTranscoding::test_master_playlist_exists PASSED
testing/tests/MYTUBE-78/test_mytube_78.py::TestHLSTranscoding::test_segment_files_exist PASSED
testing/tests/MYTUBE-78/test_mytube_78.py::TestHLSTranscoding::test_master_playlist_has_hls_header PASSED
testing/tests/MYTUBE-78/test_mytube_78.py::TestHLSTranscoding::test_master_playlist_contains_stream_inf_tags PASSED
testing/tests/MYTUBE-78/test_mytube_78.py::TestHLSTranscoding::test_master_playlist_has_required_rendition[360p] PASSED
testing/tests/MYTUBE-78/test_mytube_78.py::TestHLSTranscoding::test_master_playlist_has_required_rendition[720p] PASSED
testing/tests/MYTUBE-78/test_mytube_78.py::TestHLSTranscoding::test_master_playlist_has_required_rendition[1080p] PASSED
```

## Notes

- Tests skip automatically when `GCP_PROJECT_ID`, `VIDEO_ID`, `RAW_OBJECT_PATH`, or `DB_DSN` are not set.
- The job fixture is module-scoped: the Cloud Run Job runs once for all tests.
- Bandwidth ranges used for rendition detection: 360p (400k–600k bps), 720p (1200k–1800k bps), 1080p (2400k–3600k bps).
