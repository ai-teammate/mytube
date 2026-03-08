# MYTUBE-374 — Transcoding permanent failure: partial HLS outputs deleted from GCS

## Objective

Verify that when the transcoding job encounters a permanent failure and
`CLEANUP_ON_TRANSCODE_FAILURE=true`, all partial HLS segments and manifest files
created during the failed attempt are deleted from the `mytube-hls-output` GCS bucket.

## Test Type

`static-analysis+subprocess+mock` — combines Go source static analysis, Go unit
test subprocess execution, and Python mock-based GCS state verification.

## Test Structure

### Layer 1 — Static Analysis (`TestCleanupStaticAnalysis`)

Reads `api/cmd/transcoder/main.go` and asserts:

1. `CLEANUP_ON_TRANSCODE_FAILURE` environment variable is read.
2. The default value is `true` (enabled unless explicitly set to `"false"`).
3. `cleaner.DeletePrefix` is called on failure.
4. The HLS prefix format is `videos/<videoID>/`.
5. A confirmation log message `"deleted partial HLS output"` is emitted.
6. Cleanup is gated on `cfg.CleanupOnTranscodeFailure`.
7. An `HLSCleaner` interface is defined for dependency injection.
8. `repo.MarkFailed` is called when transcoding fails.

### Layer 2 — Go Unit Tests (`TestGoCleanupUnitTests`)

Runs the existing Go unit tests in `api/cmd/transcoder/` via subprocess:

- `TestTranscode_Failure_CleansUpHLSPrefix` — asserts `DeletePrefix` is called with the correct prefix on failure.
- `TestTranscode_FailureCleanupDisabled_DoesNotClean` — asserts no deletion when `CLEANUP_ON_TRANSCODE_FAILURE=false`.
- `TestTranscode_FailureCleanupError_OriginalErrorReturned` — asserts cleanup failure does not mask the original transcoding error.
- `TestTranscode_HappyPath_DoesNotCleanUp` — asserts `DeletePrefix` is never called on success.

### Layer 3 — Python Mock GCS (`TestHLSCleanupWithMockGCS`)

Uses `unittest.mock` to stub `google.cloud.storage.Client` and exercises
`HLSTranscoderService`:

- `test_bucket_empty_after_cleanup` — after successful cleanup, `list_output_objects` returns `[]`.
- `test_bucket_contains_partial_files_when_cleanup_disabled` — when cleanup is disabled, partial files remain.
- `test_list_output_objects_queries_correct_prefix` — verifies the correct GCS prefix `videos/<videoID>/` is used.
- `test_no_manifest_file_after_cleanup` — verifies `download_master_playlist` returns `None` after cleanup.

## Prerequisites

- Python 3.10+
- `pytest`
- Go 1.20+ (for Layer 2)

## Environment Variables

| Variable                       | Required | Description                                                                 |
|-------------------------------|----------|-----------------------------------------------------------------------------|
| `GO_BINARY`                   | No       | Path to the Go binary (default: `go` on `PATH`).                            |
| `GCP_PROJECT_ID`              | No       | GCP project ID (only needed for live GCS tests, not used in mock layer).    |
| `GCP_HLS_BUCKET`              | No       | Override the HLS output bucket name (default: `mytube-hls-output`).        |

## Running the Tests

```bash
# All layers:
pytest testing/tests/MYTUBE-374/test_mytube_374.py -v

# With custom Go binary:
GO_BINARY=/usr/local/go/bin/go pytest testing/tests/MYTUBE-374/test_mytube_374.py -v
```
