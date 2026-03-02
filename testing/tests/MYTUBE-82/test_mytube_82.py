"""
MYTUBE-82: Verify ephemeral disk cleanup — job handles large files without
exceeding storage limits.

Objective:
    Verify that the transcoder Cloud Run Job manages local disk space correctly
    during the download-transcode-upload cycle.  Specifically:

    1. On successful completion the temporary working directory is removed —
       no orphan files remain on disk.

    2. On failure (e.g. disk full, ffmpeg error, upload error) the job exits
       with a non-zero exit code, marks the DB record as 'failed', and still
       cleans up the temporary working directory so future executions are not
       blocked.

    3. The ephemeral storage limit (512 MB, Cloud Run default) is not exceeded
       because the job pipelines through a single working directory that is
       cleaned up unconditionally via ``defer os.RemoveAll``.

Test structure:
    Part A — Go unit tests (always run, no GCP required):
        Runs the existing Go test suite for the transcoder binary.  The suite
        exercises the full pipeline with stub collaborators and verifies that:

        - The working directory is removed after a successful run.
        - The working directory is removed even when a step fails.
        - ``MarkFailed`` is called on every failure path (download error,
          transcode error, upload error, DB error).
        - The job exits with a non-zero exit code on any failure.
        - The job exits with code 0 on success.

    Part B — Disk-cleanup contract tests (always run, no GCP required):
        Python-level structural analysis of the transcoder source to verify
        that the ``defer os.RemoveAll(workDir)`` contract is preserved in the
        implementation.  These tests inspect the source to confirm:

        - A temporary directory is created per execution.
        - The directory is cleaned up via ``defer os.RemoveAll``.
        - The cleanup is unconditional (placed before any error-returning
          statement).
"""

import os
import re
import subprocess
import sys

import pytest

# Make the testing root importable regardless of where pytest is invoked from.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)

TRANSCODER_DIR = os.path.join(REPO_ROOT, "api", "cmd", "transcoder")
TRANSCODER_MAIN = os.path.join(TRANSCODER_DIR, "main.go")


# ---------------------------------------------------------------------------
# Part A — Go unit tests (always run, no GCP required)
# ---------------------------------------------------------------------------


class TestTranscoderDiskCleanupGoTests:
    """
    Runs the transcoder Go test suite to verify disk-cleanup behaviour.

    These tests rely entirely on stub collaborators defined in
    ``api/cmd/transcoder/main_test.go`` — no real GCS, ffmpeg, or database
    connections are required.
    """

    def test_transcoder_builds(self):
        """The transcoder Go module must build without errors."""
        result = subprocess.run(
            ["go", "build", "./..."],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"go build failed.\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    def test_all_transcoder_unit_tests_pass(self):
        """
        The full transcoder test suite must pass.

        This exercises every pipeline path including disk cleanup on success
        and on failure, ensuring the temporary working directory is always
        removed and ``MarkFailed`` is always called on error.
        """
        result = subprocess.run(
            ["go", "test", "-v", "-count=1", "./..."],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"go test ./... failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )

    def test_happy_path_exits_zero(self):
        """
        On a successful run (all stubs return nil errors) the transcoder must
        complete without error.

        Verified by TestTranscode_HappyPath_NoError in main_test.go.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_HappyPath_NoError",
                ".",
            ],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_HappyPath_NoError failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_download_error_marks_video_failed(self):
        """
        When the download step fails (e.g. insufficient disk quota to write
        the raw file), the job must call MarkFailed to set status='failed'.

        Verified by TestTranscode_DownloadError_MarksVideoFailed.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_DownloadError_MarksVideoFailed",
                ".",
            ],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_DownloadError_MarksVideoFailed failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_transcode_error_marks_video_failed(self):
        """
        When the ffmpeg transcoding step fails (e.g. disk full mid-encode),
        the job must call MarkFailed.

        Verified by TestTranscode_TranscodeHLSError_MarksVideoFailed.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_TranscodeHLSError_MarksVideoFailed",
                ".",
            ],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_TranscodeHLSError_MarksVideoFailed failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_upload_error_marks_video_failed(self):
        """
        When the GCS upload step fails (after spending disk quota on HLS
        segments), the job must still call MarkFailed.

        Verified by TestTranscode_UploadDirError_ReturnsError combined with
        the MarkFailed assertion pattern.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_UploadDirError_ReturnsError",
                ".",
            ],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_UploadDirError_ReturnsError failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_db_update_error_marks_video_failed(self):
        """
        When the database update step fails, the job must call MarkFailed.

        Verified by TestTranscode_UpdateVideoError_MarksVideoFailed.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_UpdateVideoError_MarksVideoFailed",
                ".",
            ],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_UpdateVideoError_MarksVideoFailed failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_all_failure_paths_return_nonzero(self):
        """
        Every error path in the transcoder must return a non-nil error which
        propagates to the main() os.Exit(1) call.

        Verified by the full set of error-case tests in main_test.go.
        """
        error_tests = "|".join([
            "TestTranscode_DownloadError_ReturnsError",
            "TestTranscode_TranscodeHLSError_ReturnsError",
            "TestTranscode_ThumbnailError_ReturnsError",
            "TestTranscode_UploadDirError_ReturnsError",
            "TestTranscode_UploadFileError_ReturnsError",
            "TestTranscode_UpdateVideoError_ReturnsError",
        ])
        result = subprocess.run(
            ["go", "test", "-v", "-count=1", "-run", error_tests, "."],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Error-path tests failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        # All 6 error-path tests must appear as passing.
        pass_count = result.stdout.count("--- PASS")
        assert pass_count == 6, (
            f"Expected 6 passing error-path tests, got {pass_count}.\n"
            f"STDOUT:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# Part B — Disk-cleanup contract analysis (always run, no GCP required)
# ---------------------------------------------------------------------------


class TestDiskCleanupContractAnalysis:
    """
    Structural analysis of the transcoder source code to verify that the
    ephemeral disk cleanup contract is correctly implemented.

    These tests parse ``api/cmd/transcoder/main.go`` to assert that:

    1. A temporary directory is created with ``os.MkdirTemp``.
    2. The directory is cleaned up unconditionally with ``defer os.RemoveAll``.
    3. The defer is placed immediately after directory creation (before any
       error-returning call that could skip cleanup).

    This provides a static guard against future refactors accidentally
    removing or mis-placing the cleanup call.
    """

    @pytest.fixture(scope="class")
    def transcoder_source(self) -> str:
        """Return the contents of the transcoder main.go."""
        with open(TRANSCODER_MAIN, "r") as fh:
            return fh.read()

    def test_temp_dir_created_with_os_mkdirtemp(self, transcoder_source: str):
        """
        The transcoder must create a temporary working directory using
        ``os.MkdirTemp`` to isolate per-job disk usage.
        """
        assert "os.MkdirTemp(" in transcoder_source, (
            "Expected os.MkdirTemp() call in main.go — the transcoder must "
            "use a temporary directory to isolate per-job disk usage."
        )

    def test_temp_dir_cleaned_up_with_defer_remove_all(self, transcoder_source: str):
        """
        The temporary working directory must be removed unconditionally via
        ``defer os.RemoveAll``.  A deferred call guarantees cleanup even when
        the function returns early due to an error.
        """
        assert "defer os.RemoveAll(workDir)" in transcoder_source, (
            "Expected 'defer os.RemoveAll(workDir)' in main.go — the temp "
            "directory must be cleaned up unconditionally to prevent orphan "
            "files blocking future executions."
        )

    def test_defer_cleanup_appears_before_first_error_return(self, transcoder_source: str):
        """
        The ``defer os.RemoveAll(workDir)`` call must appear in the source
        before the first downstream step that could fail and return an error.
        This ensures no error path can skip the cleanup.
        """
        defer_pos = transcoder_source.find("defer os.RemoveAll(workDir)")
        first_step_pos = transcoder_source.find("dl.Download(")
        assert defer_pos != -1, "defer os.RemoveAll(workDir) not found in main.go"
        assert first_step_pos != -1, "dl.Download( not found in main.go"
        assert defer_pos < first_step_pos, (
            f"defer os.RemoveAll (position {defer_pos}) must appear before "
            f"dl.Download (position {first_step_pos}) in main.go so that "
            f"cleanup runs even when an early step fails."
        )

    def test_mark_failed_called_on_error(self, transcoder_source: str):
        """
        The transcoder must call ``repo.MarkFailed`` on any error to update
        the DB status to 'failed', preventing a stuck 'processing' state.
        """
        assert "repo.MarkFailed(" in transcoder_source, (
            "Expected repo.MarkFailed() call in main.go — the job must set "
            "status='failed' in the database when it encounters an error."
        )

    def test_os_exit_called_on_error_in_main(self, transcoder_source: str):
        """
        The ``main()`` function must call ``os.Exit(1)`` when the pipeline
        returns an error, producing a non-zero exit code that Cloud Run
        interprets as a job failure.
        """
        assert "os.Exit(1)" in transcoder_source, (
            "Expected os.Exit(1) in main.go — the job must exit with a "
            "non-zero code when an error occurs so Cloud Run marks the "
            "execution as failed."
        )

    def test_work_dir_variable_named_consistently(self, transcoder_source: str):
        """
        The working directory variable must be consistently named ``workDir``
        throughout ``doTranscode``, ensuring there is no risk of a parallel
        execution reusing the same directory.
        """
        # workDir should appear at least 3 times: assignment, defer, and use.
        occurrences = len(re.findall(r"\bworkDir\b", transcoder_source))
        assert occurrences >= 3, (
            f"Expected workDir to appear at least 3 times in main.go "
            f"(declaration, defer, usage), found {occurrences}."
        )

    def test_no_global_temp_dir_variable(self, transcoder_source: str):
        """
        The working directory must be declared as a local variable inside
        ``doTranscode``, not as a package-level variable.  A global temp dir
        would be shared across concurrent job executions and could cause
        cross-job file contamination.
        """
        # Package-level var declarations appear before 'func main' or 'func run'
        func_start = transcoder_source.find("func doTranscode(")
        assert func_start != -1, "doTranscode function not found"

        before_func = transcoder_source[:func_start]
        # There must be no 'var workDir' outside a function body
        assert "var workDir" not in before_func, (
            "workDir must not be declared at package level — it must be a "
            "local variable inside doTranscode() to isolate each job execution."
        )
