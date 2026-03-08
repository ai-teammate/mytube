"""
MYTUBE-378: GCS deletion safety check — only video-specific prefixes targeted.

Objective
---------
Verify that the deletion logic is restricted to the specific video ID prefix to
prevent accidental deletion of unrelated data in Google Cloud Storage.

Steps
-----
1. Inspect the Go source code of the deletion helper (manage_video.go) to
   verify the safety constraints are implemented:
   - ``parseGCSPrefix`` always constructs the deletion prefix as
     ``videos/<videoID>/`` regardless of what the stored manifest URL contains.
   - ``cleanupVideoGCSObjects`` rejects raw paths that start with ``videos/``
     (guard against cross-bucket contamination).
2. Run the Go unit tests for the ``internal/handler`` package that exercise
   the GCS cleanup logic with a mock deleter, verifying:
   - Only ``raw-bucket/<exact_raw_path>`` is passed to DeleteObject (the path
     is taken directly from the DB, not derived from user input).
   - Only ``hls-bucket/videos/<videoID>/`` is passed to DeletePrefix (always
     the video-specific prefix, never a root or arbitrary path).
   - When DELETE_ON_VIDEO_DELETE=false no GCS operations are attempted.

Expected Result
---------------
The deletion logic only targets paths prefixed with ``videos/{VIDEO_ID}/``
for HLS objects and the specific ``gcs_raw_path`` stored in the database for
raw uploads. It must never attempt to delete root bucket directories or
arbitrary paths derived from unvalidated user input.

Architecture
------------
- Step 1 performs static source-code inspection using regex/string matching.
- Step 2 delegates to ``go test`` to execute the existing Go unit tests that
  stub the GCS client and assert on the exact paths passed to the deleter.
- No live GCS client is required; all GCS I/O is intercepted by the stub.

Environment variables
---------------------
- REPO_ROOT: Path to the repository root.
             Default: auto-detected relative to this file's location.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ─── Helpers ──────────────────────────────────────────────────────────────────

def _repo_root() -> Path:
    """Return the repository root, honouring the REPO_ROOT env-var."""
    env = os.environ.get("REPO_ROOT")
    if env:
        return Path(env)
    # Walk up from this file until we find go.mod in the api/ directory.
    candidate = Path(__file__).resolve().parent
    for _ in range(10):
        if (candidate / "api" / "go.mod").exists():
            return candidate
        candidate = candidate.parent
    raise RuntimeError("Could not locate repository root (api/go.mod not found)")


def _read_source(repo_root: Path, rel_path: str) -> str:
    full = repo_root / rel_path
    if not full.exists():
        pytest.fail(f"Source file not found: {full}")
    return full.read_text(encoding="utf-8")


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def repo_root() -> Path:
    return _repo_root()


@pytest.fixture(scope="module")
def manage_video_src(repo_root: Path) -> str:
    return _read_source(repo_root, "api/internal/handler/manage_video.go")


# ─── Test Class ───────────────────────────────────────────────────────────────

class TestGCSDeletionSafety:
    """Verify that GCS deletion is restricted to video-specific prefixes."""

    # ── Step 1: Static source-code inspection ────────────────────────────────

    def test_parse_gcs_prefix_enforces_video_prefix(self, manage_video_src: str):
        """parseGCSPrefix must always produce a 'videos/<videoID>/' prefix.

        The function must:
        1. Extract the bucket from the gs:// URL.
        2. Ignore the stored path suffix — construct the prefix from videoID
           so that corrupt or crafted DB values cannot target arbitrary paths.
        """
        # Verify the expected-prefix pattern is present in source.
        assert 'fmt.Sprintf("videos/%s/", videoID)' in manage_video_src, (
            "parseGCSPrefix must construct the deletion prefix as "
            "'videos/<videoID>/' (fmt.Sprintf(\"videos/%s/\", videoID)). "
            "The safety constraint was not found in manage_video.go."
        )

    def test_raw_path_hls_guard_present(self, manage_video_src: str):
        """cleanupVideoGCSObjects must reject raw paths prefixed with 'videos/'.

        If the raw path stored in the DB starts with 'videos/' it looks like an
        HLS manifest path rather than a raw upload path. The code must skip
        deletion in that case to prevent cross-bucket contamination.
        """
        assert 'strings.HasPrefix(rawPath, "videos/")' in manage_video_src, (
            "cleanupVideoGCSObjects must guard against raw paths that start "
            "with 'videos/' (strings.HasPrefix(rawPath, \"videos/\")). "
            "The safety check was not found in manage_video.go."
        )

    def test_raw_deletion_uses_exact_db_path(self, manage_video_src: str):
        """Raw-file deletion must use paths.RawPath directly from the database.

        The raw upload path must be taken from the GCSPaths struct returned by
        SoftDelete (i.e. the stored gcs_raw_path column), never derived from
        the video ID or any request parameter.
        """
        assert "paths.RawPath" in manage_video_src, (
            "Raw GCS deletion must reference paths.RawPath (the stored "
            "gcs_raw_path from the DB), not a path constructed from video ID "
            "or request parameters. paths.RawPath not found in manage_video.go."
        )

    def test_hls_deletion_uses_parse_gcs_prefix(self, manage_video_src: str):
        """HLS deletion must go through parseGCSPrefix, not use the URL directly.

        cleanupVideoGCSObjects must call parseGCSPrefix() to extract the bucket
        and safe prefix instead of passing the raw gs:// manifest URL to the
        deleter.
        """
        assert "parseGCSPrefix(" in manage_video_src, (
            "cleanupVideoGCSObjects must call parseGCSPrefix() to obtain the "
            "safe deletion prefix — found no call to parseGCSPrefix() in "
            "manage_video.go."
        )

    def test_delete_prefix_not_called_with_arbitrary_path(self, manage_video_src: str):
        """DeletePrefix must never be called with an unvalidated manifest URL.

        The code must NOT pass *paths.HLSManifestPath directly to DeletePrefix.
        It must first parse the URL through parseGCSPrefix to obtain the safe,
        video-specific prefix.
        """
        # Look for patterns that would directly pass HLSManifestPath to DeletePrefix
        # (i.e. calling deleter.DeletePrefix with *paths.HLSManifestPath without parsing)
        dangerous_pattern = re.search(
            r'DeletePrefix\s*\([^)]*HLSManifestPath[^)]*\)',
            manage_video_src,
        )
        assert dangerous_pattern is None, (
            "DeletePrefix must not be called with the raw HLSManifestPath "
            "value. The path must be parsed through parseGCSPrefix first to "
            "restrict deletion to the 'videos/<videoID>/' prefix."
        )

    def test_parse_gcs_prefix_returns_false_for_non_gs_url(self, manage_video_src: str):
        """parseGCSPrefix must reject non-gs:// URLs (returns ok=false).

        If the stored manifest URL does not start with 'gs://', the function
        must return ok=false so no deletion attempt is made.
        """
        assert 'not a gs:// URL' in manage_video_src or \
               '"gs://"' in manage_video_src or \
               'TrimPrefix(manifestURL, "gs://")' in manage_video_src, (
            "parseGCSPrefix must validate that the URL starts with 'gs://' "
            "and return false otherwise. The validation was not found in "
            "manage_video.go."
        )

    def test_empty_bucket_rejected_by_parse_gcs_prefix(self, manage_video_src: str):
        """parseGCSPrefix must reject empty bucket names (returns ok=false).

        An empty bucket string would cause DeletePrefix to target an unnamed
        bucket which is dangerous. The function must guard against this.
        """
        assert 'bucket != ""' in manage_video_src, (
            "parseGCSPrefix must reject an empty bucket name "
            "(bucket != \"\") and return ok=false. "
            "The guard was not found in manage_video.go."
        )

    # ── Step 2: Run existing Go unit tests for GCS cleanup ───────────────────

    def test_go_unit_tests_pass(self, repo_root: Path):
        """Go unit tests for the handler package must pass.

        Runs: go test ./internal/handler/... -run TestDeleteVideo_GCS
        inside the api/ directory and asserts exit code 0.

        This exercises the full GCS cleanup path with a stub ObjectDeleter that
        records all paths passed to DeleteObject and DeletePrefix, and asserts
        that:
          - Only 'raw-bucket/<exact_raw_path>' is deleted (not a derived path).
          - Only 'hls-bucket/videos/<videoID>/' prefix is deleted.
          - No deletions occur when DELETE_ON_VIDEO_DELETE=false.
        """
        api_dir = repo_root / "api"
        if not api_dir.exists():
            pytest.fail(f"API directory not found: {api_dir}")

        result = subprocess.run(
            [
                "go", "test",
                "./internal/handler/...",
                "-run", "TestDeleteVideo_GCS",
                "-v",
                "-count=1",
            ],
            capture_output=True,
            text=True,
            cwd=str(api_dir),
            timeout=120,
        )

        assert result.returncode == 0, (
            f"Go unit tests for GCS cleanup failed (exit code {result.returncode}).\n\n"
            f"=== STDOUT ===\n{result.stdout}\n\n"
            f"=== STDERR ===\n{result.stderr}"
        )

        # Verify both tests ran and explicitly passed.
        assert "--- PASS: TestDeleteVideo_GCSCleanup_DeletesRawAndHLS" in result.stdout, (
            "TestDeleteVideo_GCSCleanup_DeletesRawAndHLS did not report PASS.\n"
            f"stdout:\n{result.stdout}"
        )
        assert "--- PASS: TestDeleteVideo_GCSCleanupDisabled_DoesNotDelete" in result.stdout, (
            "TestDeleteVideo_GCSCleanupDisabled_DoesNotDelete did not report PASS.\n"
            f"stdout:\n{result.stdout}"
        )
