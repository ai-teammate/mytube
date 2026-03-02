# MYTUBE-80: Handle transcoding failure — database status set to failed and job exits with non-zero code

## Objective

Verify that when the Cloud Run transcoder encounters a processing failure (corrupted file, FFmpeg error, etc.), it:
1. Sets `videos.status = 'failed'` for the corresponding `VIDEO_ID` row.
2. Exits with a non-zero exit code, signalling failure to Cloud Run.

## Test type

Integration — two layers:
- **Go unit tests** (subprocess): run targeted tests from `api/cmd/transcoder/main_test.go` via `go test`
- **Database integration** (psycopg2): verify the `MarkFailed` SQL UPDATE at the DB level

## Prerequisites

- **Go 1.24+** installed and on `PATH`
- **Python 3.10+**
- **psycopg2-binary** (`pip install psycopg2-binary`)
- **PostgreSQL** running and accessible (for `TestMarkFailedSQLContract` tests only)
  - Default: `localhost:5432`, user `testuser`, password `testpass`, db `mytube_test`
  - Override with env vars: `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`

The Go unit tests (`TestTranscodingFailureExitCode` and `TestTranscodingFailureMarksDBFailed`) run without PostgreSQL.

## How to run

From the repository root:

```bash
# Install Python dependencies (if not already installed)
pip install pytest psycopg2-binary

# Run all tests
python3 -m pytest testing/tests/MYTUBE-80/test_mytube_80.py -v

# Run only Go-backed tests (no PostgreSQL required)
python3 -m pytest testing/tests/MYTUBE-80/test_mytube_80.py -v \
  -k "TestTranscodingFailureExitCode or TestTranscodingFailureMarksDBFailed"

# Run only DB integration tests (requires PostgreSQL)
python3 -m pytest testing/tests/MYTUBE-80/test_mytube_80.py -v \
  -k "TestMarkFailedSQLContract"
```

## Expected output (passing, with PostgreSQL)

```
TestTranscodingFailureExitCode::test_transcoder_package_compiles PASSED
TestTranscodingFailureExitCode::test_download_error_returns_non_nil_error PASSED
TestTranscodingFailureExitCode::test_ffmpeg_error_returns_non_nil_error PASSED
TestTranscodingFailureExitCode::test_thumbnail_error_returns_non_nil_error PASSED
TestTranscodingFailureMarksDBFailed::test_download_failure_calls_mark_failed PASSED
TestTranscodingFailureMarksDBFailed::test_ffmpeg_failure_calls_mark_failed PASSED
TestTranscodingFailureMarksDBFailed::test_db_update_failure_calls_mark_failed PASSED
TestTranscodingFailureMarksDBFailed::test_full_failure_test_suite_passes PASSED
TestMarkFailedSQLContract::test_mark_failed_sets_status_to_failed PASSED
TestMarkFailedSQLContract::test_failed_status_accepted_by_check_constraint PASSED
TestMarkFailedSQLContract::test_mark_failed_does_not_affect_other_rows PASSED

11 passed
```

## Test coverage

| Test | What it verifies |
|------|-----------------|
| `test_transcoder_package_compiles` | Package builds cleanly |
| `test_download_error_returns_non_nil_error` | Download failure → non-nil error → non-zero exit code |
| `test_ffmpeg_error_returns_non_nil_error` | FFmpeg failure → non-nil error → non-zero exit code |
| `test_thumbnail_error_returns_non_nil_error` | Thumbnail failure → non-nil error → non-zero exit code |
| `test_download_failure_calls_mark_failed` | Download failure → `MarkFailed()` called → DB status = 'failed' |
| `test_ffmpeg_failure_calls_mark_failed` | FFmpeg failure → `MarkFailed()` called → DB status = 'failed' |
| `test_db_update_failure_calls_mark_failed` | DB update failure → `MarkFailed()` still called |
| `test_full_failure_test_suite_passes` | All 6+ failure-path Go tests pass collectively |
| `test_mark_failed_sets_status_to_failed` | SQL UPDATE sets `videos.status = 'failed'` |
| `test_failed_status_accepted_by_check_constraint` | `'failed'` is a valid value in the status CHECK constraint |
| `test_mark_failed_does_not_affect_other_rows` | MarkFailed is scoped to the target VIDEO_ID only |

## Source files

- Transcoder main: `api/cmd/transcoder/main.go`
- Video repository: `api/cmd/transcoder/internal/video/repository.go`
- Go unit tests: `api/cmd/transcoder/main_test.go`
- DB migration: `api/migrations/0001_initial_schema.up.sql`
