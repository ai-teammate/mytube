# MYTUBE-372: Transcoder logging for silent videos — log entry identifies missing audio stream

## Objective

Verify that the transcoder Cloud Run job emits a clear, descriptive log entry when it detects a
missing audio stream in the input video.  The log entry must confirm that no audio was detected
and that audio mapping was skipped, so that the conditional logic is visible in Cloud Run
stdout/stderr for debugging purposes.

## Test Approach

The Cloud Run job cannot be executed directly in CI without GCP credentials, so this test uses
two complementary verification methods:

1. **Static analysis** — reads `api/cmd/transcoder/internal/ffmpeg/runner.go` and verifies that
   a `log.Printf` call containing the expected message fragments is present at the exact code path
   guarded by `!hasAudio`.  This confirms the logging statement is implemented and has not been
   accidentally removed.

2. **Go unit test execution** — runs the existing Go unit tests for the ffmpeg package with
   `-v` (verbose) to capture live `log.Printf` output.  The silent-video test cases
   (`TestTranscodeHLS_SilentVideo_*`) use stub `ProbeRunner` implementations that report no audio
   streams, reproducing the exact conditions that trigger the log message in production.  The
   expected message fragments are then asserted in the combined stdout/stderr of the test runner.

Together these two methods provide high confidence that the Cloud Run job will emit the required
log entry when it processes a real silent video.

## Environment

| Requirement | Details |
|---|---|
| `go` on PATH | Standard Go toolchain must be available (present in CI image). |
| `runner.go` location | `api/cmd/transcoder/internal/ffmpeg/runner.go` relative to repo root. |
| No GCP credentials required | All tests run fully locally via static analysis and `go test`. |

## Test Steps

| # | Ticket Step | Test Method |
|---|---|---|
| 1 | Process a silent video file through the transcoder Cloud Run job | Simulated via `TestTranscodeHLS_SilentVideo_*` Go unit tests using stub `ProbeRunner` that reports no audio streams — replicates the silent-video condition exactly. |
| 2 | Review the Cloud Run job's stdout/stderr logs | `go test -v` output is captured; `log.Printf` lines appear in the test runner's combined stdout/stderr. |
| 3 | Search for log entry indicating no audio detected and conditional mapping applied | Both `"no audio stream detected"` and `"audio mapping skipped"` are asserted in the captured output, and the static regex confirms the log call sits inside `if !hasAudio { … }`. |

## Expected Result

The captured test output contains a log line matching:

```
no audio stream detected in <filename> — transcoding video-only (audio mapping skipped)
```

All five test cases pass:

| Test | Verifies |
|---|---|
| `test_runner_source_contains_no_audio_log_statement` | `runner.go` contains the phrase `"no audio stream detected"` |
| `test_runner_source_log_message_mentions_audio_mapping_skipped` | `runner.go` contains the phrase `"audio mapping skipped"` |
| `test_runner_source_log_is_on_silent_video_code_path` | The `log.Printf` call is inside the `if !hasAudio { … }` block |
| `test_go_unit_tests_emit_no_audio_log_when_silent_video_processed` | The live `go test -v` output contains both expected log fragments |
| `test_go_unit_tests_silent_video_tests_all_pass` | All `TestTranscodeHLS_SilentVideo_*` test cases exit 0 |

## Test Files

| File | Purpose |
|---|---|
| `test_mytube_372.py` | Static-analysis + Go unit test implementation |
| `config.yaml` | Test metadata (framework, platform, dependencies) |
