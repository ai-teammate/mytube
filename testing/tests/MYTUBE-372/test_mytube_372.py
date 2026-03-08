"""
MYTUBE-372: Transcoder logging for silent videos — log entry identifies missing audio stream.

Objective
---------
Verify that the transcoder provides helpful logging when it detects a missing
audio stream to assist in future debugging.

Steps
-----
1. Process a silent video file through the transcoder Cloud Run job.
2. Review the Cloud Run job's stdout/stderr logs.
3. Search for a specific log entry indicating that no audio was detected and
   conditional mapping is being applied.

Expected Result
---------------
The logs contain a clear, descriptive entry (e.g., "no audio stream detected,
skipping audio mapping") confirming the conditional logic was triggered.

Test Approach
-------------
Since the Cloud Run job cannot be executed directly in CI without GCP credentials,
this test uses two complementary verification methods:

1. **Static analysis** — reads ``api/cmd/transcoder/internal/ffmpeg/runner.go``
   and verifies that a ``log.Printf`` call with the expected message pattern is
   present at the exact code path where ``hasAudio == false``.  This confirms
   the logging statement is implemented and has not been accidentally removed.

2. **Go unit test execution** — runs the existing Go unit tests for the ffmpeg
   package with ``-v`` (verbose) to capture the live log output produced by
   ``log.Printf``.  The silent-video test scenarios (``TestTranscodeHLS_SilentVideo_*``)
   trigger the conditional path and emit the log line; we assert the expected
   message appears in the test runner's output.

Together these two methods provide high confidence that the Cloud Run job will
emit the required log entry when it processes a real silent video.

Architecture
------------
- Pure subprocess / file I/O — no framework or GCP credentials required.
- REPO_ROOT is resolved relative to this file's location.
- ``go test`` is expected to be available on the PATH (standard in the CI image).
"""
from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_RUNNER_SRC = os.path.join(
    _REPO_ROOT, "api", "cmd", "transcoder", "internal", "ffmpeg", "runner.go"
)
_FFMPEG_PKG = "./cmd/transcoder/internal/ffmpeg/..."
_API_DIR = os.path.join(_REPO_ROOT, "api")

# The exact log message pattern we expect the transcoder to emit for silent videos.
# The Go source uses log.Printf with an em-dash (—) between the file path and the
# descriptive reason.  We match both key phrases to be robust to minor wording changes.
_EXPECTED_LOG_FRAGMENT_1 = "no audio stream detected"
_EXPECTED_LOG_FRAGMENT_2 = "audio mapping skipped"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _read_runner_source() -> str:
    """Return the full text of runner.go, or skip the test if not found."""
    if not os.path.isfile(_RUNNER_SRC):
        pytest.skip(f"runner.go not found at {_RUNNER_SRC!r}")
    with open(_RUNNER_SRC, encoding="utf-8") as fh:
        return fh.read()


def _run_go_tests_verbose() -> subprocess.CompletedProcess:
    """
    Execute the ffmpeg package's Go unit tests with -v (verbose) so that
    log.Printf output appears in stdout/stderr.

    Returns the CompletedProcess regardless of exit code; callers decide
    whether to fail.
    """
    go_bin = "go"
    result = subprocess.run(
        [go_bin, "test", "-v", "-run", "TestTranscodeHLS_SilentVideo", _FFMPEG_PKG],
        capture_output=True,
        text=True,
        cwd=_API_DIR,
        timeout=120,
    )
    return result


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestTranscoderSilentVideoLogging:
    """MYTUBE-372: Transcoder must emit a descriptive log entry for silent videos."""

    # ------------------------------------------------------------------
    # Step 1 & 2 — Static analysis: log statement exists in source code
    # ------------------------------------------------------------------

    def test_runner_source_contains_no_audio_log_statement(self) -> None:
        """
        Verify that runner.go contains a log.Printf call that includes
        "no audio stream detected" — confirming the logging statement is
        implemented and not accidentally removed.
        """
        source = _read_runner_source()

        assert _EXPECTED_LOG_FRAGMENT_1 in source, (
            f"runner.go does not contain the expected log fragment "
            f"{_EXPECTED_LOG_FRAGMENT_1!r}.\n"
            f"The transcoder must emit a descriptive log entry when no audio "
            f"stream is detected so that Cloud Run logs can be used for debugging."
        )

    def test_runner_source_log_message_mentions_audio_mapping_skipped(self) -> None:
        """
        Verify that the log statement also includes "audio mapping skipped",
        confirming that the message communicates what conditional logic was applied.
        """
        source = _read_runner_source()

        assert _EXPECTED_LOG_FRAGMENT_2 in source, (
            f"runner.go does not contain the expected log fragment "
            f"{_EXPECTED_LOG_FRAGMENT_2!r}.\n"
            f"The log entry must explain that audio mapping was skipped so "
            f"developers reading Cloud Run logs understand the transcoding behaviour."
        )

    def test_runner_source_log_is_on_silent_video_code_path(self) -> None:
        """
        Verify that the log.Printf call appears *after* the ``!hasAudio`` check
        in runner.go — confirming it is triggered by the correct conditional.

        We look for the pattern:
            if !hasAudio {
                log.Printf("no audio stream detected ...
        allowing for any whitespace between the condition and the Printf call.
        """
        source = _read_runner_source()

        # Match the condition guard followed (anywhere in the block) by the log call.
        pattern = re.compile(
            r"if\s+!hasAudio\s*\{[^}]*log\.Printf\([^)]*no audio stream detected",
            re.DOTALL,
        )
        assert pattern.search(source), (
            "runner.go: expected to find 'if !hasAudio { log.Printf(... \"no audio "
            "stream detected ...' pattern but it was not present.  "
            "The log statement must be guarded by the !hasAudio condition so it is "
            "only emitted for silent videos."
        )

    # ------------------------------------------------------------------
    # Step 3 — Behavioural: Go unit tests emit the log message at runtime
    # ------------------------------------------------------------------

    def test_go_unit_tests_emit_no_audio_log_when_silent_video_processed(
        self,
    ) -> None:
        """
        Run the silent-video Go unit tests and verify that the expected log
        message appears in their output.

        The Go test framework echoes log.Printf output when -v is used, so
        the "no audio stream detected" line produced by TranscodeHLS must be
        present in the combined stdout+stderr of the test run.
        """
        result = _run_go_tests_verbose()
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"Go unit tests for the ffmpeg package FAILED (exit code "
            f"{result.returncode}).\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        assert _EXPECTED_LOG_FRAGMENT_1 in combined, (
            f"Go unit tests passed but the expected log fragment "
            f"{_EXPECTED_LOG_FRAGMENT_1!r} was NOT found in the test output.\n"
            f"This means TranscodeHLS did not call log.Printf with the expected "
            f"message when processing a silent video.\n\n"
            f"Captured output:\n{combined}"
        )

        assert _EXPECTED_LOG_FRAGMENT_2 in combined, (
            f"Go unit tests passed but the expected log fragment "
            f"{_EXPECTED_LOG_FRAGMENT_2!r} was NOT found in the test output.\n"
            f"Captured output:\n{combined}"
        )

    def test_go_unit_tests_silent_video_tests_all_pass(self) -> None:
        """
        Verify that all TestTranscodeHLS_SilentVideo_* test cases pass,
        confirming the conditional audio-mapping logic is correct.

        These tests use stub ProbeRunners that report no audio streams,
        reproducing the exact conditions that trigger the log message in production.
        """
        result = _run_go_tests_verbose()

        assert result.returncode == 0, (
            f"One or more TestTranscodeHLS_SilentVideo_* tests FAILED.\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )

        # Verify at least one SilentVideo test was actually executed.
        assert "TestTranscodeHLS_SilentVideo" in (result.stdout + result.stderr), (
            f"No TestTranscodeHLS_SilentVideo_* tests were executed — the test "
            f"filter may have matched nothing.\n"
            f"Output:\n{result.stdout + result.stderr}"
        )
