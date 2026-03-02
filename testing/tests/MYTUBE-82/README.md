# MYTUBE-82 — Verify ephemeral disk cleanup: job handles large files without exceeding storage limits

## What this test verifies

The transcoder Cloud Run Job manages local (ephemeral) disk space correctly during the
download-transcode-upload cycle:

1. The temporary working directory is **always removed** after the job completes —
   whether it succeeds or fails — via `defer os.RemoveAll(workDir)`.
2. On any failure, the job **exits with a non-zero exit code** and sets the DB video
   status to `'failed'`, preventing a stuck `'processing'` state.
3. No orphan files remain on disk that could block future executions on the same
   Cloud Run instance.

The test is split into two parts:

**Part A — Go unit tests (always run, no GCP required)**

Runs the existing Go test suite for `api/cmd/transcoder` via `subprocess`:

- The transcoder binary builds cleanly
- The full test suite passes (all pipeline steps exercised with stubs)
- Happy-path run completes with no error
- Every failure path (download, transcode, upload, DB) calls `MarkFailed`
- Every failure path returns a non-nil error (→ `os.Exit(1)` in `main`)

**Part B — Disk-cleanup contract tests (always run, no GCP required)**

Structural analysis of `api/cmd/transcoder/main.go` to confirm:

- A per-job temporary directory is created with `os.MkdirTemp`
- The directory is cleaned up unconditionally with `defer os.RemoveAll(workDir)`
- The defer appears before the first pipeline step that can fail
- `repo.MarkFailed()` is called on every error path
- `os.Exit(1)` is called in `main()` on error
- `workDir` is a local variable (not global), isolating concurrent executions

## Requirements

- Python 3.10+
- Go 1.21+
- `pytest`

## Install dependencies

```bash
pip install pytest
```

## Run the test

From the repository root:

```bash
pytest testing/tests/MYTUBE-82/test_mytube_82.py -v
```

No environment variables are required — both Part A and Part B run without GCP credentials.

## Expected output (passing)

```
testing/tests/MYTUBE-82/test_mytube_82.py::TestTranscoderDiskCleanupGoTests::test_transcoder_builds PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestTranscoderDiskCleanupGoTests::test_all_transcoder_unit_tests_pass PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestTranscoderDiskCleanupGoTests::test_happy_path_exits_zero PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestTranscoderDiskCleanupGoTests::test_download_error_marks_video_failed PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestTranscoderDiskCleanupGoTests::test_transcode_error_marks_video_failed PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestTranscoderDiskCleanupGoTests::test_upload_error_marks_video_failed PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestTranscoderDiskCleanupGoTests::test_db_update_error_marks_video_failed PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestTranscoderDiskCleanupGoTests::test_all_failure_paths_return_nonzero PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestDiskCleanupContractAnalysis::test_temp_dir_created_with_os_mkdirtemp PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestDiskCleanupContractAnalysis::test_temp_dir_cleaned_up_with_defer_remove_all PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestDiskCleanupContractAnalysis::test_defer_cleanup_appears_before_first_error_return PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestDiskCleanupContractAnalysis::test_mark_failed_called_on_error PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestDiskCleanupContractAnalysis::test_os_exit_called_on_error_in_main PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestDiskCleanupContractAnalysis::test_work_dir_variable_named_consistently PASSED
testing/tests/MYTUBE-82/test_mytube_82.py::TestDiskCleanupContractAnalysis::test_no_global_temp_dir_variable PASSED
15 passed
```
