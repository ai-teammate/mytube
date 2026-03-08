"""
MYTUBE-389: Missing local thumbnail file — existence check prevents fatal error
            and job completion.

Objective
---------
Verify that the transcoder checks for the existence of ``thumbnail.jpg`` on the
local filesystem before attempting an upload, preventing fatal 'no such file or
directory' errors and job failure.

Preconditions
-------------
A video-only source file is used to ensure FFmpeg does not produce a thumbnail.

Steps (mapped to test assertions)
----------------------------------
1. Upload the video-only file to the raw uploads bucket.
   → Simulated by ``stubDownloader`` writing the raw input file to disk.
2. Trigger the Cloud Run transcoding job for that video.
   → Simulated by calling ``transcode()`` with a ``stubTranscoder`` whose
     ``ExtractThumbnail`` returns nil but does **not** write ``thumbnail.jpg``
     (``silentThumbFail: true``), matching the video-only input behaviour.
3. Monitor the job execution logs for the thumbnail upload phase.
   → Go tests are run with ``-v`` so that ``log.Printf`` output is captured;
     the test asserts that ``event=thumbnail_skipped`` appears in the output.

Expected Results
----------------
- The transcoder identifies that ``thumbnail.jpg`` is missing (os.Stat fails),
  logs a warning containing ``event=thumbnail_skipped``, and does NOT call
  UploadFile for the thumbnail path.
- The job continues to the HLS upload phase (UploadDir is called).
- The job exits with code 0 (transcode() returns nil).
- The DB record is updated with status=ready and an empty thumbnail_url.

Architecture Notes
------------------
Layer A — Go unit tests (always runs, no infrastructure required):
    Targets the four ``TestTranscode_SilentThumbnailFailure_*`` tests in
    ``api/cmd/transcoder/main_test.go`` which together exercise the exact
    code path described in this ticket:

    +---------------------------------------------------------+-------+
    | Test                                                    | Asserts|
    +---------------------------------------------------------+-------+
    | TestTranscode_SilentThumbnailFailure_SucceedsWithout... | exit 0 |
    | TestTranscode_SilentThumbnailFailure_NoThumbnailUpload  | no upl |
    | TestTranscode_SilentThumbnailFailure_EmptyThumbnailURL..| empty  |
    | TestTranscode_SilentThumbnailFailure_HLSUploaded        | HLS ok |
    +---------------------------------------------------------+-------+

    An additional Python-level assertion checks that the Go test output
    contains the expected ``event=thumbnail_skipped`` warning log line,
    confirming the descriptive warning requirement from the ticket.

Environment Variables
---------------------
TRANSCODER_DIR : Path to the transcoder source directory.
                 Default: <repo_root>/api/cmd/transcoder
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_TRANSCODER_DIR = os.path.join(_REPO_ROOT, "api", "cmd", "transcoder")
TRANSCODER_DIR: str = os.getenv("TRANSCODER_DIR", _DEFAULT_TRANSCODER_DIR)

# Regex pattern that the Go unit tests target for the silence-thumbnail scenario.
_SILENT_FAILURE_PATTERN = "TestTranscode_SilentThumbnailFailure"

# Expected token in log output confirming the existence-check warning was emitted.
_EXPECTED_LOG_TOKEN = "thumbnail_skipped"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_go_tests(pattern: str) -> subprocess.CompletedProcess:
    """Run ``go test -v -count=1 -run <pattern>`` in TRANSCODER_DIR.

    Returns the CompletedProcess regardless of exit code so callers can
    inspect both successful and failing outcomes.
    """
    return subprocess.run(
        [
            "go", "test",
            "-v",
            "-count=1",
            f"-run={pattern}",
            ".",
        ],
        cwd=TRANSCODER_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def go_test_result() -> subprocess.CompletedProcess:
    """Run the SilentThumbnailFailure Go unit tests once and cache the result."""
    if not os.path.isdir(TRANSCODER_DIR):
        pytest.skip(
            f"Transcoder source directory not found at {TRANSCODER_DIR!r}. "
            "Set TRANSCODER_DIR to the path of api/cmd/transcoder."
        )
    return _run_go_tests(_SILENT_FAILURE_PATTERN)


# ---------------------------------------------------------------------------
# Layer A — Go unit tests
# ---------------------------------------------------------------------------


class TestMissingThumbnailExistenceCheck:
    """MYTUBE-389: thumbnail existence check prevents fatal error and job failure."""

    def test_go_silent_thumbnail_failure_tests_pass(
        self, go_test_result: subprocess.CompletedProcess
    ) -> None:
        """All TestTranscode_SilentThumbnailFailure_* Go tests must pass.

        These tests exercise the exact code path where:
        - FFmpeg exits 0 but does not write thumbnail.jpg (video-only input).
        - The transcoder calls os.Stat(thumbPath) and finds no file.
        - The job must complete without error (exit code 0).

        A non-zero exit code means the transcoder would either:
        a) attempt to upload a non-existent file → fatal "no such file" error, or
        b) abort the job when thumbnail is missing → incorrect behaviour.
        """
        combined = go_test_result.stdout + go_test_result.stderr

        assert go_test_result.returncode == 0, (
            f"Go unit tests for silent thumbnail failure returned exit code "
            f"{go_test_result.returncode} — the existence check is broken.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

        assert "PASS" in combined or "ok" in combined, (
            "Expected 'PASS' or 'ok' in Go test output but got:\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

    def test_go_silent_thumbnail_failure_tests_found(
        self, go_test_result: subprocess.CompletedProcess
    ) -> None:
        """The targeted Go tests must be discovered (not zero tests run).

        Fails if the test pattern matches nothing, which would silently pass
        without exercising any assertions.
        """
        combined = go_test_result.stdout + go_test_result.stderr

        assert _SILENT_FAILURE_PATTERN in combined, (
            f"No tests matching '{_SILENT_FAILURE_PATTERN}' were found or run.\n"
            "This likely means the test pattern is wrong or the Go test file "
            "has been renamed.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

    def test_warning_log_emitted_for_missing_thumbnail(
        self, go_test_result: subprocess.CompletedProcess
    ) -> None:
        """The transcoder must emit a warning log when thumbnail.jpg is absent.

        The log must contain ``thumbnail_skipped`` (from the structured log
        token ``event=thumbnail_skipped``) to satisfy the ticket requirement
        that a descriptive warning is logged rather than a fatal error.

        This assertion checks that ``log.Printf`` is called with the expected
        event token when os.Stat(thumbPath) finds no file — confirming that the
        existence check is wired to the warning path rather than an error path.
        """
        combined = go_test_result.stdout + go_test_result.stderr

        assert _EXPECTED_LOG_TOKEN in combined, (
            f"Expected the log warning token '{_EXPECTED_LOG_TOKEN}' in Go test "
            "output, but it was not found.\n\n"
            "The transcoder should log a message like:\n"
            "  'warning: thumbnail file not written after extraction ... "
            "event=thumbnail_skipped reason=silent_ffmpeg_failure'\n"
            "when os.Stat(thumbnail.jpg) finds no file.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

    def test_no_thumbnail_upload_attempted(
        self, go_test_result: subprocess.CompletedProcess
    ) -> None:
        """The TestTranscode_SilentThumbnailFailure_NoThumbnailUpload test must pass.

        This is the core regression guard for MYTUBE-389: confirms that the
        existence check (os.Stat) prevents UploadFile from being called for
        thumbnail.jpg when the file does not exist on disk.
        """
        combined = go_test_result.stdout + go_test_result.stderr

        assert "TestTranscode_SilentThumbnailFailure_NoThumbnailUpload" in combined, (
            "TestTranscode_SilentThumbnailFailure_NoThumbnailUpload was not run — "
            "cannot confirm that thumbnail upload is suppressed when the file is absent.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

        assert "--- FAIL: TestTranscode_SilentThumbnailFailure_NoThumbnailUpload" not in combined, (
            "TestTranscode_SilentThumbnailFailure_NoThumbnailUpload FAILED.\n"
            "This means the transcoder attempted to upload thumbnail.jpg even "
            "though the file was not written to disk — the existence check is broken.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

    def test_hls_upload_continues_after_missing_thumbnail(
        self, go_test_result: subprocess.CompletedProcess
    ) -> None:
        """The TestTranscode_SilentThumbnailFailure_HLSUploaded test must pass.

        Verifies that the HLS upload phase proceeds even when thumbnail.jpg is
        absent — the job must not abort early because of the missing thumbnail.
        """
        combined = go_test_result.stdout + go_test_result.stderr

        assert "TestTranscode_SilentThumbnailFailure_HLSUploaded" in combined, (
            "TestTranscode_SilentThumbnailFailure_HLSUploaded was not run — "
            "cannot confirm HLS upload continues after missing thumbnail.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

        assert "--- FAIL: TestTranscode_SilentThumbnailFailure_HLSUploaded" not in combined, (
            "TestTranscode_SilentThumbnailFailure_HLSUploaded FAILED.\n"
            "This means the HLS upload was NOT performed after the thumbnail "
            "was found to be missing — the job aborted prematurely.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

    def test_job_exits_zero_without_thumbnail(
        self, go_test_result: subprocess.CompletedProcess
    ) -> None:
        """The TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail test must pass.

        Confirms that transcode() returns nil (exit code 0) when thumbnail.jpg
        is absent — a fatal error here would match the bug described in MYTUBE-389.
        """
        combined = go_test_result.stdout + go_test_result.stderr

        assert "TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail" in combined, (
            "TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail was not run.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

        assert "--- FAIL: TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail" not in combined, (
            "TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail FAILED.\n"
            "This means transcode() returned a non-nil error when thumbnail.jpg "
            "was absent — the job encountered a fatal error instead of continuing.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

    def test_db_updated_with_empty_thumbnail_url(
        self, go_test_result: subprocess.CompletedProcess
    ) -> None:
        """The TestTranscode_SilentThumbnailFailure_EmptyThumbnailURLInDB test must pass.

        Confirms the DB record is updated with an empty thumbnail_url (not a
        broken path) when no thumbnail was produced.
        """
        combined = go_test_result.stdout + go_test_result.stderr

        assert "TestTranscode_SilentThumbnailFailure_EmptyThumbnailURLInDB" in combined, (
            "TestTranscode_SilentThumbnailFailure_EmptyThumbnailURLInDB was not run.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )

        assert "--- FAIL: TestTranscode_SilentThumbnailFailure_EmptyThumbnailURLInDB" not in combined, (
            "TestTranscode_SilentThumbnailFailure_EmptyThumbnailURLInDB FAILED.\n"
            "This means the DB was updated with a non-empty thumbnail_url even "
            "though no thumbnail was produced.\n\n"
            f"stdout:\n{go_test_result.stdout}\n"
            f"stderr:\n{go_test_result.stderr}"
        )
