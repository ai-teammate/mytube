# MYTUBE-81 — Generate video thumbnail: thumbnail extracted at the 5-second mark

## What this test verifies

A JPEG thumbnail is correctly extracted from the source video at the 5-second timestamp and uploaded to the correct GCS path `videos/{VIDEO_ID}/thumbnail.jpg` in the `mytube-hls-output` bucket.

The test is split into two parts:

**Part A — Local contract tests (always run, no GCP required)**

Runs the Go unit-test suite for `api/cmd/transcoder` via `subprocess`:
- The transcoder binary builds cleanly
- The full unit-test suite passes
- `ExtractThumbnail` is called during the pipeline
- The thumbnail is uploaded to `videos/{VIDEO_ID}/thumbnail.jpg`
- The `ThumbnailURL` written to the database follows the CDN pattern `{CDN_BASE_URL}/videos/{VIDEO_ID}/thumbnail.jpg`
- The FFmpeg runner unit tests pass (verifying correct FFmpeg arguments for thumbnail extraction)

**Part B — Infrastructure smoke tests (require live GCP credentials + TEST_VIDEO_ID)**

Uses the `google-cloud-storage` SDK to verify the live HLS output bucket:
1. The `mytube-hls-output` bucket is accessible
2. A `thumbnail.jpg` exists at `videos/{VIDEO_ID}/thumbnail.jpg` for a known transcoded video
3. The object contains valid JPEG data (magic bytes `FF D8 FF`)

## Requirements

- Python 3.10+
- Go 1.21+
- `pytest`
- `google-cloud-storage` (for Part B only)
- GCP Application Default Credentials (for Part B only)

## Environment variables

| Variable          | Required | Description                                                             |
|-------------------|----------|-------------------------------------------------------------------------|
| `GCP_PROJECT_ID`  | Part B   | GCP project ID — omit to skip infrastructure tests                     |
| `GCP_HLS_BUCKET`  | Part B   | HLS output bucket name (default: `mytube-hls-output`)                  |
| `TEST_VIDEO_ID`   | Part B   | UUID of a known, already-transcoded video to verify in the live bucket  |

## Install dependencies

```bash
pip install pytest
# For Part B:
pip install google-cloud-storage
```

## Run the test

**Part A only (no GCP credentials needed):**

```bash
pytest testing/tests/MYTUBE-81/test_mytube_81.py -v
```

**With Part B (live GCS verification):**

```bash
export GCP_PROJECT_ID=my-project
export TEST_VIDEO_ID=<uuid-of-transcoded-video>
gcloud auth application-default login
pytest testing/tests/MYTUBE-81/test_mytube_81.py -v
```

## Expected output (passing — Part A only, no GCP credentials)

```
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_transcoder_builds PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_transcoder_unit_tests_pass PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_extract_thumbnail_called_with_5_second_offset PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_thumbnail_uploaded_to_correct_gcs_path PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_thumbnail_url_written_to_db_with_cdn_pattern PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_ffmpeg_thumbnail_extraction_unit_tests_pass PASSED
6 passed, 3 skipped
```

## Expected output (passing — with GCP credentials and TEST_VIDEO_ID)

```
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_transcoder_builds PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_transcoder_unit_tests_pass PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_extract_thumbnail_called_with_5_second_offset PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_thumbnail_uploaded_to_correct_gcs_path PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_thumbnail_url_written_to_db_with_cdn_pattern PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestTranscoderThumbnailContract::test_ffmpeg_thumbnail_extraction_unit_tests_pass PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestThumbnailInfrastructure::test_hls_bucket_is_accessible PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestThumbnailInfrastructure::test_thumbnail_object_exists_in_bucket PASSED
testing/tests/MYTUBE-81/test_mytube_81.py::TestThumbnailInfrastructure::test_thumbnail_is_valid_jpeg PASSED
9 passed
```
