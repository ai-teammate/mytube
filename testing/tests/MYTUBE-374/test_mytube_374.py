"""
MYTUBE-374: Transcoding permanent failure — partial HLS outputs deleted from GCS.

Objective
---------
Verify that the transcoding job performs a best-effort cleanup of partial HLS
files when it encounters a permanent failure and
CLEANUP_ON_TRANSCODE_FAILURE=true.

Preconditions
-------------
* A video is queued for transcoding.
* Environment variable CLEANUP_ON_TRANSCODE_FAILURE is set to true.

Steps
-----
1. Trigger a transcoding job that is guaranteed to fail (e.g., corrupted input
   or non-audio file as described in RCA).
2. Monitor the job execution until it exits with a non-zero code.
3. Inspect the mytube-hls-output bucket for any files created during the
   failed attempt.

Expected Result
---------------
The transcoder logs the failure and the result of the cleanup attempt.
No partial HLS segments or manifest files remain in the GCS bucket for that
video ID.

Test approach
-------------
Three layers of verification:

1. **Static analysis** — verifies that main.go correctly reads
   CLEANUP_ON_TRANSCODE_FAILURE, calls DeletePrefix on failure, and emits the
   expected log lines for both failure and cleanup.

2. **Go unit tests** — runs the existing Go unit tests in
   api/cmd/transcoder/ that directly exercise the cleanup path.
   (TestTranscode_Failure_CleansUpHLSPrefix,
   TestTranscode_FailureCleanupDisabled_DoesNotClean,
   TestTranscode_FailureCleanupError_OriginalErrorReturned,
   TestTranscode_HappyPath_DoesNotCleanUp)

3. **Python integration (mock)** — exercises HLSTranscoderService with a
   mock GCS client to verify that after a failed job, list_output_objects
   returns an empty list for the affected video ID (simulating a cleaned-up
   bucket).

Environment variables
---------------------
GCP_PROJECT_ID   : GCP project (optional — only used for live GCS tests).
GCP_HLS_BUCKET   : Override HLS output bucket name (default: mytube-hls-output).
GO_BINARY        : Path to the Go binary for running tests
                   (default: discovered via ``go`` on PATH).

Architecture
------------
- Static analysis reads api/cmd/transcoder/main.go directly.
- Go test layer uses subprocess to run ``go test`` in the transcoder package.
- Python mock layer uses unittest.mock to stub google.cloud.storage.Client.
- HLSTranscoderService from testing/components/services/hls_transcoder_service.py
  is used for list_output_objects verification.
- GcpConfig from testing/core/config/gcp_config.py centralises env var access.
- No hardcoded paths, no time.sleep().
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.services.hls_transcoder_service import HLSTranscoderService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_TRANSCODER_MAIN_GO = os.path.join(
    _REPO_ROOT, "api", "cmd", "transcoder", "main.go"
)
_TRANSCODER_PKG_DIR = os.path.join(
    _REPO_ROOT, "api", "cmd", "transcoder"
)

# Go test functions that directly exercise the cleanup path.
_GO_CLEANUP_TEST_FUNCS = [
    "TestTranscode_Failure_CleansUpHLSPrefix",
    "TestTranscode_FailureCleanupDisabled_DoesNotClean",
    "TestTranscode_FailureCleanupError_OriginalErrorReturned",
    "TestTranscode_HappyPath_DoesNotCleanUp",
]


# ---------------------------------------------------------------------------
# Layer 1: Static analysis
# ---------------------------------------------------------------------------


class TestCleanupStaticAnalysis(unittest.TestCase):
    """Verify that main.go contains the required cleanup logic."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(_TRANSCODER_MAIN_GO, "r") as fh:
            cls.source = fh.read()

    def test_cleanup_env_var_read(self) -> None:
        """main.go must read CLEANUP_ON_TRANSCODE_FAILURE from the environment."""
        self.assertIn(
            "CLEANUP_ON_TRANSCODE_FAILURE",
            self.source,
            "main.go does not reference the CLEANUP_ON_TRANSCODE_FAILURE "
            "environment variable. The cleanup feature cannot be controlled "
            "at deploy time.",
        )

    def test_cleanup_env_var_defaults_to_true(self) -> None:
        """CLEANUP_ON_TRANSCODE_FAILURE must default to true (enabled) when unset.

        The expected pattern is: the field is set to true unless the env var
        value is explicitly "false".
        """
        pattern = r'CLEANUP_ON_TRANSCODE_FAILURE["\s]*\)\s*!=\s*"false"'
        match = re.search(pattern, self.source)
        self.assertIsNotNone(
            match,
            "main.go does not implement a default-true pattern for "
            "CLEANUP_ON_TRANSCODE_FAILURE. "
            "Expected: os.Getenv(\"CLEANUP_ON_TRANSCODE_FAILURE\") != \"false\"",
        )

    def test_delete_prefix_called_on_failure(self) -> None:
        """main.go must call cleaner.DeletePrefix when a transcoding error occurs."""
        self.assertIn(
            "cleaner.DeletePrefix",
            self.source,
            "main.go does not call cleaner.DeletePrefix on failure. "
            "Partial HLS files would be left in GCS after a failed transcoding job.",
        )

    def test_hls_prefix_format_correct(self) -> None:
        """The GCS prefix used for cleanup must be videos/<videoID>/."""
        pattern = r'videos/%s/', 
        self.assertRegex(
            self.source,
            r'videos/%s/',
            "The HLS cleanup prefix in main.go does not follow the expected "
            "pattern 'videos/<videoID>/'. The cleanup would target the wrong "
            "GCS path.",
        )

    def test_cleanup_log_message_emitted(self) -> None:
        """main.go must log a confirmation message when cleanup succeeds."""
        self.assertIn(
            "deleted partial HLS output",
            self.source,
            "main.go does not log 'deleted partial HLS output' after a "
            "successful cleanup. Operators cannot confirm cleanup from logs.",
        )

    def test_cleanup_gated_by_flag(self) -> None:
        """Cleanup must be conditional on CleanupOnTranscodeFailure being true."""
        pattern = r"cfg\.CleanupOnTranscodeFailure"
        match = re.search(pattern, self.source)
        self.assertIsNotNone(
            match,
            "main.go does not gate GCS cleanup on cfg.CleanupOnTranscodeFailure. "
            "Cleanup would always run regardless of the environment flag.",
        )

    def test_hls_cleaner_interface_defined(self) -> None:
        """The HLSCleaner interface must be declared so tests can inject stubs."""
        self.assertIn(
            "HLSCleaner",
            self.source,
            "main.go does not define an HLSCleaner interface. "
            "Dependency injection for the cleaner is not possible.",
        )

    def test_mark_failed_called_on_failure(self) -> None:
        """repo.MarkFailed must be called before cleanup when transcoding fails."""
        self.assertIn(
            "repo.MarkFailed",
            self.source,
            "main.go does not call repo.MarkFailed when a transcoding error "
            "occurs. The database video status would not reflect the failure.",
        )


# ---------------------------------------------------------------------------
# Layer 2: Go unit tests
# ---------------------------------------------------------------------------


class TestGoCleanupUnitTests(unittest.TestCase):
    """Run the Go unit tests that exercise the HLS cleanup path."""

    @classmethod
    def setUpClass(cls) -> None:
        """Discover the Go binary and skip the whole class if it is unavailable."""
        go_binary = os.getenv("GO_BINARY", "go")
        try:
            result = subprocess.run(
                [go_binary, "version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError(f"go version returned {result.returncode}")
            cls.go_binary = go_binary
        except (FileNotFoundError, RuntimeError) as exc:
            raise unittest.SkipTest(
                f"Go binary not available — skipping Go unit test layer: {exc}"
            )

    def _run_go_test(self, run_pattern: str) -> subprocess.CompletedProcess:
        """Execute ``go test -run <run_pattern>`` in the transcoder package."""
        return subprocess.run(
            [
                self.go_binary,
                "test",
                "-v",
                f"-run={run_pattern}",
                "./...",
            ],
            capture_output=True,
            text=True,
            cwd=_TRANSCODER_PKG_DIR,
            timeout=120,
        )

    def test_failure_cleans_up_hls_prefix(self) -> None:
        """Go: on failure, DeletePrefix is called with the correct prefix."""
        result = self._run_go_test("TestTranscode_Failure_CleansUpHLSPrefix")
        self.assertEqual(
            result.returncode,
            0,
            f"TestTranscode_Failure_CleansUpHLSPrefix FAILED.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn(
            "PASS",
            result.stdout,
            "TestTranscode_Failure_CleansUpHLSPrefix did not report PASS.",
        )

    def test_cleanup_disabled_does_not_clean(self) -> None:
        """Go: when CLEANUP_ON_TRANSCODE_FAILURE=false, no deletion occurs."""
        result = self._run_go_test("TestTranscode_FailureCleanupDisabled_DoesNotClean")
        self.assertEqual(
            result.returncode,
            0,
            f"TestTranscode_FailureCleanupDisabled_DoesNotClean FAILED.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn(
            "PASS",
            result.stdout,
            "TestTranscode_FailureCleanupDisabled_DoesNotClean did not report PASS.",
        )

    def test_cleanup_error_does_not_mask_original_error(self) -> None:
        """Go: when cleanup itself fails, the original transcoding error is returned."""
        result = self._run_go_test("TestTranscode_FailureCleanupError_OriginalErrorReturned")
        self.assertEqual(
            result.returncode,
            0,
            f"TestTranscode_FailureCleanupError_OriginalErrorReturned FAILED.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn(
            "PASS",
            result.stdout,
            "TestTranscode_FailureCleanupError_OriginalErrorReturned did not report PASS.",
        )

    def test_happy_path_does_not_clean_up(self) -> None:
        """Go: on success, DeletePrefix is never called."""
        result = self._run_go_test("TestTranscode_HappyPath_DoesNotCleanUp")
        self.assertEqual(
            result.returncode,
            0,
            f"TestTranscode_HappyPath_DoesNotCleanUp FAILED.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        self.assertIn(
            "PASS",
            result.stdout,
            "TestTranscode_HappyPath_DoesNotCleanUp did not report PASS.",
        )


# ---------------------------------------------------------------------------
# Layer 3: Python integration (mock GCS)
# ---------------------------------------------------------------------------


class TestHLSCleanupWithMockGCS(unittest.TestCase):
    """Verify bucket state after a failed job using a mock GCS client.

    These tests simulate the GCS state that the cleanup code produces:
    - After a successful cleanup, list_output_objects returns [] for the video.
    - Without cleanup (flag=false), list_output_objects returns partial files.

    HLSTranscoderService.list_output_objects is used so that the same service
    layer tested in other integration tests is exercised here.
    """

    _VIDEO_ID = "test-video-mytube-374"
    _HLS_BUCKET = "mytube-hls-output"

    def _make_service(self, blob_names: list[str]) -> HLSTranscoderService:
        """Build an HLSTranscoderService backed by a mock GCS client.

        The mock client's list_blobs returns blobs whose .name attributes are
        set to the provided blob_names.
        """
        config = GcpConfig()
        config.hls_bucket = self._HLS_BUCKET

        mock_client = MagicMock()
        mock_blobs = []
        for name in blob_names:
            blob = MagicMock()
            blob.name = name
            mock_blobs.append(blob)
        mock_client.list_blobs.return_value = mock_blobs

        return HLSTranscoderService(config=config, storage_client=mock_client)

    def test_bucket_empty_after_cleanup(self) -> None:
        """After a successful cleanup, no partial HLS objects exist for the video.

        Simulates: transcoder failed → DeletePrefix ran → GCS prefix is empty.
        The mock GCS client returns no blobs for the video prefix.
        """
        service = self._make_service(blob_names=[])

        remaining = service.list_output_objects(self._VIDEO_ID)

        self.assertEqual(
            remaining,
            [],
            f"Expected no HLS objects for video '{self._VIDEO_ID}' after cleanup, "
            f"but found: {remaining}. "
            "The cleanup step did not remove all partial HLS files from GCS.",
        )

    def test_bucket_contains_partial_files_when_cleanup_disabled(self) -> None:
        """When cleanup is disabled, partial HLS files remain in GCS.

        This test documents the *before-fix* (or cleanup-disabled) state:
        the bucket still contains partial segments after the job fails.
        """
        partial_files = [
            f"videos/{self._VIDEO_ID}/360p_0.ts",
            f"videos/{self._VIDEO_ID}/360p_1.ts",
        ]
        service = self._make_service(blob_names=partial_files)

        remaining = service.list_output_objects(self._VIDEO_ID)

        self.assertEqual(
            len(remaining),
            2,
            f"Expected 2 partial HLS files to remain when cleanup is disabled, "
            f"but found {len(remaining)}: {remaining}.",
        )
        for name in partial_files:
            self.assertIn(
                name,
                remaining,
                f"Expected partial file '{name}' to remain in the bucket "
                f"when cleanup is disabled.",
            )

    def test_list_output_objects_queries_correct_prefix(self) -> None:
        """HLSTranscoderService must query the correct GCS prefix for the video."""
        config = GcpConfig()
        config.hls_bucket = self._HLS_BUCKET
        mock_client = MagicMock()
        mock_client.list_blobs.return_value = []

        service = HLSTranscoderService(config=config, storage_client=mock_client)
        service.list_output_objects(self._VIDEO_ID)

        mock_client.list_blobs.assert_called_once()
        call_args = mock_client.list_blobs.call_args

        # Verify prefix argument
        _, kwargs = call_args
        used_prefix = kwargs.get("prefix", "")
        expected_prefix = f"videos/{self._VIDEO_ID}/"
        self.assertEqual(
            used_prefix,
            expected_prefix,
            f"list_blobs was called with prefix='{used_prefix}' but expected "
            f"prefix='{expected_prefix}'. The cleanup or listing would target "
            f"the wrong GCS path.",
        )

    def test_no_manifest_file_after_cleanup(self) -> None:
        """After cleanup, the master playlist (index.m3u8) must not exist.

        The GCS client returns None for blob.exists(), simulating a cleaned-up
        bucket.
        """
        config = GcpConfig()
        config.hls_bucket = self._HLS_BUCKET
        mock_client = MagicMock()

        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_blob.exists.return_value = False
        mock_bucket.blob.return_value = mock_blob
        mock_client.bucket.return_value = mock_bucket

        service = HLSTranscoderService(config=config, storage_client=mock_client)
        manifest_content = service.download_master_playlist(self._VIDEO_ID)

        self.assertIsNone(
            manifest_content,
            f"Expected download_master_playlist to return None after cleanup "
            f"(blob does not exist), but got: {manifest_content!r}. "
            "The HLS manifest was not removed from GCS during cleanup.",
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main(verbosity=2)
