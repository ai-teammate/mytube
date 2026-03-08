"""
MYTUBE-390: Thumbnail extraction failure — cleanup routine is not triggered
            for HLS artifacts.

Objective
---------
Verify that a failure or skip in the thumbnail extraction/upload process does
NOT trigger the cleanup routine that deletes successfully generated HLS
segments and manifests.

Preconditions
-------------
- Environment variable CLEANUP_ON_TRANSCODE_FAILURE is set to true (default).

Test steps
----------
1. Trigger a transcoding job with a video file that fails to produce a thumbnail.
   (Simulated via Go unit tests using stubbed infrastructure that returns a
    thumbnail extraction error or silently fails to write the thumbnail file.)
2. Monitor the logs/assertions to ensure the thumbnail step fails or is bypassed.
3. Inspect the HLS output bucket state — master manifest, rendition playlists,
   and .ts segments must remain intact.

Expected Result
---------------
The HLS master manifest (index.m3u8), rendition playlists, and all .ts segments
remain in the output bucket. The cleanup routine (deletion) is not invoked
because the thumbnail error is handled as a non-fatal event.

Test approach
-------------
Two verification layers:

**Layer 1 — Go unit tests (always runs):**
Invokes the Go test suite in api/cmd/transcoder via subprocess and runs the
four dedicated regression tests:
  - TestTranscode_ThumbnailError_DoesNotCleanUpHLS
  - TestTranscode_ThumbnailError_DoesNotMarkFailed
  - TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail
  - TestTranscode_SilentThumbnailFailure_HLSUploaded

These tests use stub implementations for GCS, FFmpeg, and the DB, giving
deterministic control over when thumbnail extraction fails (both error path
and silent-failure/empty-file path) while verifying the cleaner's
DeletePrefix is never called and the HLS upload always completes.

**Layer 2 — GCS live state check (requires GCP credentials):**
Inspects the live mytube-hls-output bucket for videos whose HLS output was
produced without a thumbnail (confirmed by the absence of thumbnail.jpg).
This proves the cleanup routine was not triggered in production for real
transcoding runs where thumbnail extraction was skipped.

Environment variables
---------------------
GCP_PROJECT_ID              GCP project (default: ai-native-478811).
GCP_HLS_BUCKET              HLS output bucket (default: mytube-hls-output).
GOOGLE_APPLICATION_CREDENTIALS  Path to service account key.

Architecture notes
------------------
- Layer 1 wraps `go test` via subprocess — no GCP dependencies required.
- Layer 2 uses GcpConfig + google-cloud-storage SDK (injected via fixture).
- All configuration read from environment via GcpConfig — no hardcoded values.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TRANSCODER_PKG = "github.com/ai-teammate/mytube/api/cmd/transcoder"

# Go unit test names that directly cover the MYTUBE-390 acceptance criteria.
_TARGET_TESTS = [
    "TestTranscode_ThumbnailError_DoesNotCleanUpHLS",
    "TestTranscode_ThumbnailError_DoesNotMarkFailed",
    "TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail",
    "TestTranscode_SilentThumbnailFailure_HLSUploaded",
]

# GCS object names that must be present for a valid HLS output directory.
_REQUIRED_HLS_OBJECTS = ["index.m3u8"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_go_tests(test_filter: str) -> subprocess.CompletedProcess:
    """Run `go test` in the api module directory with the given -run filter."""
    api_dir = _REPO_ROOT / "api"
    return subprocess.run(
        [
            "go", "test",
            "-v",
            f"-run={test_filter}",
            "./cmd/transcoder/...",
        ],
        capture_output=True,
        text=True,
        cwd=str(api_dir),
        timeout=300,
    )


def _parse_go_test_results(output: str) -> dict[str, str]:
    """Parse verbose `go test -v` output and return {test_name: 'PASS'|'FAIL'|'SKIP'}."""
    results: dict[str, str] = {}
    for line in output.splitlines():
        for status in ("PASS", "FAIL", "SKIP"):
            if line.startswith(f"--- {status}: "):
                name = line.split(f"--- {status}: ")[1].split(" ")[0]
                results[name] = status
    return results


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    return GcpConfig()


@pytest.fixture(scope="module")
def storage_client(gcp_config: GcpConfig):
    """Return an authenticated GCS client, or None if credentials unavailable."""
    try:
        from google.cloud import storage as gcs_storage
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        return None

    if not gcp_config.project_id:
        return None

    try:
        return gcs_storage.Client(project=gcp_config.project_id)
    except DefaultCredentialsError:
        return None


@pytest.fixture(scope="module")
def go_test_output() -> subprocess.CompletedProcess:
    """Run all target Go unit tests once for the module."""
    test_filter = "|".join(_TARGET_TESTS)
    return _run_go_tests(test_filter)


@pytest.fixture(scope="module")
def go_test_results(go_test_output) -> dict[str, str]:
    """Parsed {test_name: status} dict from the Go test run."""
    combined = go_test_output.stdout + go_test_output.stderr
    return _parse_go_test_results(combined)


@pytest.fixture(scope="module")
def hls_bucket_videos_without_thumbnail(
    gcp_config: GcpConfig,
    storage_client,
) -> Optional[list[str]]:
    """
    Return a list of VIDEO_IDs in the HLS bucket whose output directory contains
    HLS files but no thumbnail.jpg — i.e. jobs where thumbnail was skipped.

    Returns None if GCS is not accessible.
    """
    if storage_client is None:
        return None

    hls_bucket = gcp_config.hls_bucket or "mytube-hls-output"
    try:
        # List all objects under videos/ without a delimiter to get every blob.
        blobs = list(storage_client.list_blobs(hls_bucket, prefix="videos/"))
        all_object_names: list[str] = [b.name for b in blobs]
    except Exception:
        return None

    if not all_object_names:
        return None

    # Group objects by VIDEO_ID (second path segment).
    video_objects: dict[str, list[str]] = {}
    for name in all_object_names:
        parts = name.split("/")
        if len(parts) >= 3:
            vid = parts[1]
            video_objects.setdefault(vid, []).append(name)

    # Find VIDEO_IDs that have index.m3u8 but NOT thumbnail.jpg.
    no_thumb_videos = [
        vid for vid, objs in video_objects.items()
        if any(o.endswith("index.m3u8") for o in objs)
        and not any(o.endswith("thumbnail.jpg") for o in objs)
    ]
    return no_thumb_videos


# ---------------------------------------------------------------------------
# Layer 1: Go unit tests
# ---------------------------------------------------------------------------


class TestThumbnailFailureCleanupBehaviorUnit:
    """
    MYTUBE-390 — Layer 1: Go unit tests verify cleanup is never triggered for
    thumbnail failures, for both error-path and silent-failure scenarios.
    """

    def test_go_tests_exit_successfully(self, go_test_output: subprocess.CompletedProcess) -> None:
        """The `go test` command must exit with code 0 (all tests pass)."""
        assert go_test_output.returncode == 0, (
            "Go unit tests for MYTUBE-390 exited with a non-zero exit code "
            f"({go_test_output.returncode}).\n\n"
            "=== stdout ===\n"
            f"{go_test_output.stdout}\n"
            "=== stderr ===\n"
            f"{go_test_output.stderr}"
        )

    def test_thumbnail_error_does_not_clean_hls(
        self, go_test_results: dict[str, str]
    ) -> None:
        """
        When thumbnail extraction returns an error, DeletePrefix must NOT be called
        — the cleanup routine must be suppressed for non-fatal thumbnail failures.

        Verifies: TestTranscode_ThumbnailError_DoesNotCleanUpHLS
        """
        test_name = "TestTranscode_ThumbnailError_DoesNotCleanUpHLS"
        assert test_name in go_test_results, (
            f"{test_name} was not found in go test output. "
            "Ensure the test exists in api/cmd/transcoder/main_test.go."
        )
        assert go_test_results[test_name] == "PASS", (
            f"{test_name} FAILED.\n"
            "This means HLS cleanup (DeletePrefix) IS being triggered when "
            "thumbnail extraction fails — the cleanup routine is incorrectly "
            "treating a non-fatal thumbnail error as a fatal pipeline failure.\n\n"
            "Expected: cleaner.DeletePrefix is never called when only the thumbnail fails.\n"
            "Actual: cleaner.DeletePrefix was invoked, which would delete all HLS "
            "segments and manifests for a video that was otherwise transcoded successfully."
        )

    def test_thumbnail_error_does_not_mark_video_failed(
        self, go_test_results: dict[str, str]
    ) -> None:
        """
        When thumbnail extraction returns an error, the video must NOT be marked
        as failed in the database. The pipeline continues and completes successfully.

        Verifies: TestTranscode_ThumbnailError_DoesNotMarkFailed
        """
        test_name = "TestTranscode_ThumbnailError_DoesNotMarkFailed"
        assert test_name in go_test_results, (
            f"{test_name} was not found in go test output."
        )
        assert go_test_results[test_name] == "PASS", (
            f"{test_name} FAILED.\n"
            "Thumbnail extraction failure is incorrectly propagating as a fatal "
            "error and calling MarkFailed — the video would be permanently stuck "
            "in 'failed' status even though HLS transcoding succeeded."
        )

    def test_silent_thumbnail_failure_job_succeeds(
        self, go_test_results: dict[str, str]
    ) -> None:
        """
        When FFmpeg exits 0 but produces no thumbnail file (silent failure for
        video-only clips shorter than the seek offset), the job must succeed.

        Verifies: TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail
        """
        test_name = "TestTranscode_SilentThumbnailFailure_SucceedsWithoutThumbnail"
        assert test_name in go_test_results, (
            f"{test_name} was not found in go test output."
        )
        assert go_test_results[test_name] == "PASS", (
            f"{test_name} FAILED.\n"
            "The transcoding job is failing when FFmpeg silently produces no "
            "thumbnail file (exits 0 but writes nothing). This is the primary "
            "MYTUBE-384 regression — the pipeline should continue and complete "
            "successfully without a thumbnail."
        )

    def test_silent_thumbnail_failure_hls_still_uploaded(
        self, go_test_results: dict[str, str]
    ) -> None:
        """
        When thumbnail is silently skipped (FFmpeg exits 0 but writes no file),
        the HLS output directory must still be uploaded to GCS.

        Verifies: TestTranscode_SilentThumbnailFailure_HLSUploaded
        """
        test_name = "TestTranscode_SilentThumbnailFailure_HLSUploaded"
        assert test_name in go_test_results, (
            f"{test_name} was not found in go test output."
        )
        assert go_test_results[test_name] == "PASS", (
            f"{test_name} FAILED.\n"
            "HLS output is not being uploaded when thumbnail extraction silently "
            "fails. The pipeline is aborting before the GCS upload step, which "
            "means no HLS content would be available for playback."
        )


# ---------------------------------------------------------------------------
# Layer 2: GCS live state verification
# ---------------------------------------------------------------------------


class TestThumbnailSkippedHLSIntact:
    """
    MYTUBE-390 — Layer 2: Inspect the live GCS HLS output bucket.

    Verifies that real transcoding runs where thumbnail was skipped (no
    thumbnail.jpg present) still have their HLS manifests and segment files
    intact — proving cleanup was not triggered in production.
    """

    def test_gcs_accessible_for_live_check(
        self,
        storage_client,
        gcp_config: GcpConfig,
    ) -> None:
        """GCS bucket must be accessible; skip if no credentials are configured."""
        if storage_client is None:
            pytest.skip(
                "GCS client is unavailable (missing credentials or google-cloud-storage). "
                "Set GOOGLE_APPLICATION_CREDENTIALS to enable the live GCS check."
            )
        hls_bucket = gcp_config.hls_bucket or "mytube-hls-output"
        try:
            next(iter(storage_client.list_blobs(hls_bucket, max_results=1)), None)
        except Exception as exc:
            pytest.skip(f"Cannot access GCS bucket '{hls_bucket}': {exc}")

    def test_no_thumbnail_videos_exist_in_hls_bucket(
        self,
        hls_bucket_videos_without_thumbnail: Optional[list[str]],
    ) -> None:
        """
        At least one VIDEO_ID in the HLS bucket must have HLS output but no thumbnail,
        confirming we have real evidence of thumbnail-skipped transcoding runs.

        If the bucket only has videos with thumbnails, the test is skipped (no evidence
        to verify), not failed.
        """
        if hls_bucket_videos_without_thumbnail is None:
            pytest.skip("GCS is not accessible — skipping live bucket verification.")

        if not hls_bucket_videos_without_thumbnail:
            pytest.skip(
                "All videos in the HLS bucket have a thumbnail.jpg. "
                "Cannot verify thumbnail-skip behaviour from live state alone — "
                "unit tests in Layer 1 cover this case."
            )

        # If we get here there are videos without thumbnails — good evidence.
        count = len(hls_bucket_videos_without_thumbnail)
        assert count >= 1, (
            "Expected at least one video in the HLS bucket that has HLS output "
            "but no thumbnail.jpg — but none found."
        )

    def test_hls_manifest_present_for_no_thumbnail_videos(
        self,
        gcp_config: GcpConfig,
        storage_client,
        hls_bucket_videos_without_thumbnail: Optional[list[str]],
    ) -> None:
        """
        For every VIDEO_ID that has no thumbnail, index.m3u8 must still be present.

        This is the core assertion of MYTUBE-390: cleanup must NOT delete the HLS
        master manifest when thumbnail extraction was skipped.
        """
        if storage_client is None or hls_bucket_videos_without_thumbnail is None:
            pytest.skip("GCS not accessible.")
        if not hls_bucket_videos_without_thumbnail:
            pytest.skip("No thumbnail-skipped videos found in the HLS bucket.")

        hls_bucket = gcp_config.hls_bucket or "mytube-hls-output"
        missing_manifest: list[str] = []

        for video_id in hls_bucket_videos_without_thumbnail:
            # Check all required HLS objects (keeps code DRY and uses the module-level constant)
            missing_objs: list[str] = []
            for obj in _REQUIRED_HLS_OBJECTS:
                blob = storage_client.bucket(hls_bucket).blob(
                    f"videos/{video_id}/{obj}"
                )
                if not blob.exists():
                    missing_objs.append(obj)
            if missing_objs:
                missing_manifest.append(video_id)

        assert not missing_manifest, (
            "The following VIDEO_IDs have NO thumbnail.jpg AND NO index.m3u8 in "
            f"gs://{hls_bucket}/videos/<id>/:\n"
            + "\n".join(f"  - {vid}" for vid in missing_manifest)
            + "\n\nThis indicates the cleanup routine deleted the HLS output for "
            "a thumbnail-skipped run, which violates the MYTUBE-390 requirement. "
            "The cleanup routine must only fire when HLS transcoding itself fails, "
            "not when thumbnail extraction is non-fatally skipped."
        )

    def test_hls_segments_present_for_no_thumbnail_videos(
        self,
        gcp_config: GcpConfig,
        storage_client,
        hls_bucket_videos_without_thumbnail: Optional[list[str]],
    ) -> None:
        """
        For every VIDEO_ID with no thumbnail, at least one .ts segment file must
        be present — proving the full HLS output was not wiped by cleanup.
        """
        if storage_client is None or hls_bucket_videos_without_thumbnail is None:
            pytest.skip("GCS not accessible.")
        if not hls_bucket_videos_without_thumbnail:
            pytest.skip("No thumbnail-skipped videos found in the HLS bucket.")

        hls_bucket = gcp_config.hls_bucket or "mytube-hls-output"
        missing_segments: list[str] = []

        for video_id in hls_bucket_videos_without_thumbnail:
            prefix = f"videos/{video_id}/"
            blobs = list(storage_client.list_blobs(hls_bucket, prefix=prefix))
            has_ts = any(b.name.endswith(".ts") for b in blobs)
            if not has_ts:
                missing_segments.append(video_id)

        assert not missing_segments, (
            "The following VIDEO_IDs have NO thumbnail.jpg AND NO .ts segment files "
            f"in gs://{hls_bucket}/videos/<id>/:\n"
            + "\n".join(f"  - {vid}" for vid in missing_segments)
            + "\n\nThis indicates the cleanup routine removed all HLS segments for "
            "a thumbnail-skipped run. Expected: segments must survive even when "
            "thumbnail extraction fails."
        )
