"""
MYTUBE-391: Video-only input failing thumbnail extraction —
system provides fallback placeholder.

Objective
---------
Verify that the system provides a default placeholder image when a thumbnail
cannot be extracted from a video-only source stream.

Steps
-----
1. Execute the transcoding job for a video-only MP4 file (no audio).
2. Once the job completes with exit code 0, navigate to the output GCS bucket
   at ``videos/{VIDEO_ID}/``.
3. Download and inspect the ``thumbnail.jpg`` file.

Expected Result
---------------
A ``thumbnail.jpg`` file exists in the GCS path.  The file contains the
standard system placeholder image, ensuring the video has a visual
representative in the UI even when extraction is impossible.

Test approach
-------------
Three layers:

**Layer A — Static analysis** (always runs, no GCP credentials required):
    Reads ``api/cmd/transcoder/main.go`` to verify that the transcoder
    contains logic to write a fallback placeholder image to
    ``videos/{VIDEO_ID}/thumbnail.jpg`` when thumbnail extraction silently
    fails (thumbReady == false at upload time).

**Layer B — Go unit tests** (always runs when ``go`` is on PATH):
    Runs the transcoder Go unit-test suite and checks that a test exercises
    the placeholder-fallback path and asserts that
    ``videos/{VIDEO_ID}/thumbnail.jpg`` IS uploaded even when FFmpeg exits 0
    but writes no thumbnail file.

**Layer C — GCS integration** (runs when GOOGLE_APPLICATION_CREDENTIALS is set
    and points to a valid service-account key for a real GCP project):
    1. Uploads a minimal video-only MP4 probe (a few frames, no audio stream)
       to the raw-uploads bucket.
    2. Executes the Cloud Run transcoding job via ``gcloud run jobs execute``.
    3. Asserts the job exits with code 0.
    4. Downloads ``videos/{VIDEO_ID}/thumbnail.jpg`` from the HLS-output bucket.
    5. Verifies that the file is a valid JPEG (starts with the JPEG SOI magic
       bytes ``\\xFF\\xD8``) and is non-empty.

Environment variables (Layer C)
--------------------------------
- GOOGLE_APPLICATION_CREDENTIALS  Path to a GCP service-account JSON key.
                                   Required for Layer C; test is skipped when absent.
- GCP_PROJECT_ID                   GCP project ID (default: ai-native-478811).
- GCP_REGION                       GCP region (default: us-central1).
- GCP_HLS_BUCKET                   HLS-output bucket (default: mytube-hls-output).
- GCP_RAW_BUCKET                   Raw-uploads bucket (default: mytube-raw-uploads).
- GCP_TRANSCODER_JOB               Cloud Run Job name (default: mytube-transcoder).
- CDN_BASE_URL                     CDN base URL (default: https://cdn.example.com).
- TRANSCODER_WAIT_SECONDS          Max seconds to wait for the job (default: 300).

Architecture notes
------------------
- Static analysis reads ``api/cmd/transcoder/main.go`` directly; no subprocess.
- Go tests run via ``go test ./api/cmd/transcoder/`` in a subprocess.
- GCS interactions use ``HLSTranscoderService`` and
  ``google.cloud.storage.Client`` — no raw SDK calls inline in the test.
- ``GcpConfig`` centralises all environment variable access.
- No hardcoded credential values, URLs, or bucket names.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.services.hls_transcoder_service import HLSTranscoderService

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_TRANSCODER_MAIN_GO = os.path.join(
    _REPO_ROOT, "api", "cmd", "transcoder", "main.go"
)
_TRANSCODER_PKG_DIR = os.path.join(_REPO_ROOT, "api", "cmd", "transcoder")

_DEFAULT_PROJECT_ID = "ai-native-478811"
_TRANSCODER_WAIT_SECONDS = int(os.environ.get("TRANSCODER_WAIT_SECONDS", "300"))

# JPEG magic bytes — every valid JPEG file starts with 0xFF 0xD8.
_JPEG_SOI = b"\xff\xd8"

# Minimal synthetic MP4 bytes that represent a 1-frame video-only file.
# This is not a real MP4; the upload and transcoding will fail if actually
# played, but it is used in Layer C only when a real Cloud Run job is
# executed.  A real test environment should provide a proper video-only MP4
# via the GCS_TEST_VIDEO_ONLY_OBJECT env var.
_DUMMY_VIDEO_BYTES = (
    b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00isomiso2avc1mp41"
    + b"\x00" * 256
)


# ===========================================================================
# Layer A — Static analysis of main.go
# ===========================================================================


class TestPlaceholderStaticAnalysis(unittest.TestCase):
    """Verify that main.go contains placeholder-fallback logic for missing thumbnails."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(_TRANSCODER_MAIN_GO, "r") as fh:
            cls.source = fh.read()

    def test_placeholder_upload_when_thumb_not_ready(self) -> None:
        """main.go must upload a fallback placeholder when thumbReady is false.

        When thumbnail extraction silently fails (FFmpeg exits 0 but writes no
        file), the transcoder must write a standard placeholder JPEG to the HLS
        bucket at ``videos/{VIDEO_ID}/thumbnail.jpg`` instead of skipping the
        upload entirely.  This ensures every video has a thumbnail image in the
        UI regardless of source stream composition.

        The implementation must contain an ``else`` branch (after the
        ``thumbReady`` check) that uploads the placeholder file.  Accepted
        patterns include references to a built-in placeholder asset, a
        hard-coded placeholder byte slice, or a call to generate and upload a
        placeholder image.
        """
        # Check that the code handles the "thumbReady == false" case by
        # uploading a placeholder rather than simply skipping the upload.
        # We look for evidence that when thumbReady is false, the code still
        # writes thumbnail.jpg to the GCS bucket using the placeholder.
        has_placeholder_logic = (
            "placeholder" in self.source.lower()
            or "fallback" in self.source.lower()
            # Check for a pattern where the upload happens even when thumbReady is false.
            # The simplest implementation would upload a placeholder in an else branch.
            or (
                "!thumbReady" in self.source
                and "thumbnail.jpg" in self.source
                and "UploadFile" in self.source
                # There must be an upload path reachable when thumbReady is false.
                and _has_placeholder_upload_path(self.source)
            )
        )
        self.assertTrue(
            has_placeholder_logic,
            "main.go does not implement fallback placeholder logic for "
            "video-only thumbnail extraction failures.\n\n"
            "Expected: when thumbReady == false after FFmpeg exits 0 (silent "
            "failure for video-only input), the transcoder must upload a "
            "standard placeholder image to "
            "'videos/{VIDEO_ID}/thumbnail.jpg' in the HLS bucket instead of "
            "skipping the upload.\n\n"
            "Actual: the code only uploads thumbnail.jpg inside the "
            "'if thumbReady { ... }' block; there is no else-branch that "
            "uploads a placeholder.  As a result, video-only files have no "
            "thumbnail in the GCS bucket and no thumbnail_url in the database, "
            "leaving them without a visual representative in the UI.\n\n"
            "Relevant section of main.go (Step 5):\n"
            "  if thumbReady {\n"
            "      // upload thumbnail.jpg\n"
            "  }\n"
            "  // ← missing: else { upload placeholder to thumbnail.jpg }\n",
        )

    def test_placeholder_thumbnail_url_set_in_db(self) -> None:
        """When a placeholder is used, thumbnail_url in the DB must be non-empty.

        The DB record must reference the placeholder image URL so the frontend
        can display it rather than rendering a broken-image icon or an empty
        thumbnail slot.
        """
        # If the placeholder logic test already failed, skip this dependent check.
        has_placeholder_logic = (
            "placeholder" in self.source.lower()
            or "fallback" in self.source.lower()
            or _has_placeholder_upload_path(self.source)
        )
        if not has_placeholder_logic:
            self.skipTest(
                "Skipping DB thumbnail_url check — placeholder logic is absent "
                "(see test_placeholder_upload_when_thumb_not_ready)."
            )

        # After uploading the placeholder, thumbnailURL must be assigned in the
        # else/fallback branch and UpdateVideo must be called with that value.
        import re
        else_block_pattern = re.compile(
            r'else\s*\{[^}]*thumbnailURL[^}]*\}',
            re.DOTALL,
        )
        self.assertTrue(
            else_block_pattern.search(self.source),
            "main.go must set thumbnailURL in the placeholder/else branch before "
            "calling UpdateVideo, so the DB record is updated with a non-empty URL.",
        )


def _has_placeholder_upload_path(source: str) -> bool:
    """Return True if the source contains placeholder-thumbnail upload logic.

    Looks for an UploadFile call inside an ``else`` block, which indicates
    that a fallback/placeholder upload path exists when thumbReady is false.
    Using a targeted else-block regex avoids false positives from unrelated
    UploadFile call sites (e.g. HLS segment uploads in the happy path).
    """
    import re
    else_upload_pattern = re.compile(
        r'else\s*\{[^}]*UploadFile[^}]*\}',
        re.DOTALL,
    )
    return bool(else_upload_pattern.search(source))


# ===========================================================================
# Layer B — Go unit tests
# ===========================================================================


def _go_available() -> bool:
    """Return True if the ``go`` binary is on PATH."""
    try:
        subprocess.run(["go", "version"], capture_output=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def _run_go_tests(pattern: str) -> subprocess.CompletedProcess:
    """Run Go unit tests matching *pattern* in the transcoder package."""
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-run", pattern, "."],
        cwd=_TRANSCODER_PKG_DIR,
        capture_output=True,
        text=True,
    )


@pytest.mark.skipif(not _go_available(), reason="go binary not found on PATH")
class TestPlaceholderGoUnit:
    """Layer B: Go unit tests must cover the placeholder-fallback path."""

    def test_go_unit_placeholder_fallback_test_exists(self) -> None:
        """A Go unit test must exist that asserts placeholder upload on silent thumb fail.

        The test suite must contain a test function (matching
        ``*SilentThumbnailFailure*Placeholder*`` or
        ``*VideoOnly*Placeholder*``) that:
        1. Injects ``silentThumbFail: true`` into the stub transcoder.
        2. Asserts that ``videos/{VIDEO_ID}/thumbnail.jpg`` IS present in
           ``ul.uploadedFiles`` (i.e. the placeholder was uploaded).

        Currently, the test suite only contains
        ``TestTranscode_SilentThumbnailFailure_NoThumbnailUpload``, which
        asserts the OPPOSITE: that thumbnail.jpg is NOT uploaded.  That test
        is inconsistent with the MYTUBE-391 requirement.
        """
        main_test_go = os.path.join(_TRANSCODER_PKG_DIR, "main_test.go")
        if not os.path.isfile(main_test_go):
            pytest.fail(f"main_test.go not found at {main_test_go}")

        with open(main_test_go, "r") as fh:
            test_source = fh.read()

        placeholder_test_exists = (
            "SilentThumbnailFailure_PlaceholderUploaded" in test_source
            or "VideoOnly_PlaceholderThumbnailUploaded" in test_source
            or (
                "silentThumbFail" in test_source
                and "PlaceholderUploaded" in test_source
            )
        )
        assert placeholder_test_exists, (
            "No Go unit test found that asserts a placeholder thumbnail.jpg is "
            "uploaded when FFmpeg exits 0 but writes no thumbnail file.\n\n"
            "Expected: a test function such as "
            "TestTranscode_SilentThumbnailFailure_PlaceholderUploaded or "
            "TestTranscode_VideoOnly_PlaceholderThumbnailUploaded that:\n"
            "  - uses stubTranscoder{silentThumbFail: true}\n"
            "  - asserts 'videos/{VIDEO_ID}/thumbnail.jpg' is present in "
            "ul.uploadedFiles\n\n"
            "Actual: the only relevant test is "
            "TestTranscode_SilentThumbnailFailure_NoThumbnailUpload, which "
            "asserts that thumbnail.jpg is NOT uploaded (the opposite of the "
            "MYTUBE-391 requirement).\n\n"
            f"Inspected file: {main_test_go}"
        )

    def test_go_unit_existing_silent_fail_tests_pass(self) -> None:
        """All existing SilentThumbnailFailure Go tests must still pass.

        These are regression tests for MYTUBE-384 (job must not abort when
        thumbnail extraction fails).  They must continue to pass after any
        MYTUBE-391 implementation work.
        """
        result = _run_go_tests("TestTranscode_SilentThumbnailFailure")
        assert result.returncode == 0, (
            "One or more existing SilentThumbnailFailure Go unit tests failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_go_unit_happy_path_passes(self) -> None:
        """HappyPath Go unit tests must pass to confirm no regression in normal flow."""
        result = _run_go_tests("TestTranscode_HappyPath")
        assert result.returncode == 0, (
            "One or more HappyPath Go unit tests failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ===========================================================================
# Layer C — GCS integration (skipped without credentials)
# ===========================================================================


def _gcp_creds_available() -> bool:
    """Return True if a valid GCP service-account credentials file is configured."""
    path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "")
    if not path or not os.path.isfile(path):
        return False
    # Skip the bundled mock credentials — they are not accepted by real GCP APIs.
    mock_path = os.path.join(
        _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
    )
    return os.path.abspath(path) != os.path.abspath(mock_path)


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    cfg = GcpConfig()
    if not cfg.project_id:
        cfg.project_id = _DEFAULT_PROJECT_ID
    return cfg


@pytest.fixture(scope="module")
def storage_client(gcp_config: GcpConfig):
    """Create an authenticated GCS client; skip if credentials are unavailable."""
    try:
        from google.cloud import storage as gcs_storage
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        pytest.skip("google-cloud-storage is not installed")

    if not _gcp_creds_available():
        pytest.skip(
            "GOOGLE_APPLICATION_CREDENTIALS is not set or points to the mock "
            "fixture — skipping Layer C GCS integration tests."
        )
    return gcs_storage.Client()


@pytest.fixture(scope="module")
def transcoder_service(gcp_config: GcpConfig, storage_client):
    return HLSTranscoderService(config=gcp_config, storage_client=storage_client)


@pytest.fixture(scope="module")
def video_only_test_run(gcp_config: GcpConfig, transcoder_service: HLSTranscoderService, storage_client):
    """Upload a video-only MP4 to the raw bucket and run the transcoding job.

    Yields a dict with:
        video_id   — the UUID used for this run
        job_result — JobExecutionResult from HLSTranscoderService
    """
    # Use a synthetic video-only raw object path from env, or upload a probe.
    raw_object_path = os.environ.get("GCS_TEST_VIDEO_ONLY_OBJECT", "")
    video_id = str(uuid.uuid4())

    if not raw_object_path:
        # Upload a minimal placeholder MP4 to the raw bucket.  In a real CI
        # environment the caller should provide a proper video-only MP4 via
        # GCS_TEST_VIDEO_ONLY_OBJECT.
        raw_object_path = f"raw/mytube-391-probe-{video_id}.mp4"
        blob = storage_client.bucket(gcp_config.raw_bucket).blob(raw_object_path)
        blob.upload_from_string(_DUMMY_VIDEO_BYTES, content_type="video/mp4")

    result = transcoder_service.run_transcoding_job(
        video_id=video_id,
        raw_object_path=raw_object_path,
        timeout_seconds=_TRANSCODER_WAIT_SECONDS,
    )
    yield {"video_id": video_id, "job_result": result}

    # Cleanup: delete probe object if we uploaded it.
    if not os.environ.get("GCS_TEST_VIDEO_ONLY_OBJECT"):
        try:
            storage_client.bucket(gcp_config.raw_bucket).blob(raw_object_path).delete()
        except Exception:
            pass


@pytest.mark.skipif(
    not _gcp_creds_available() or not os.environ.get("GCS_TEST_VIDEO_ONLY_OBJECT"),
    reason=(
        "Skipping Layer C GCS integration tests — "
        "GOOGLE_APPLICATION_CREDENTIALS and GCS_TEST_VIDEO_ONLY_OBJECT must both be set"
    ),
)
class TestPlaceholderGCSIntegration:
    """Layer C: Live Cloud Run job + GCS verification of placeholder thumbnail."""

    def test_transcoding_job_exits_zero(
        self, video_only_test_run: dict, gcp_config: GcpConfig
    ) -> None:
        """The transcoding job must complete successfully (exit code 0).

        A video-only MP4 (no audio stream) must transcode to HLS successfully.
        """
        result = video_only_test_run["job_result"]
        assert result.success and result.exit_code == 0, (
            f"Transcoding job failed for video-only input.\n"
            f"exit_code={result.exit_code}\n"
            f"error_message={result.error_message!r}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}\n\n"
            "The transcoding job must exit with code 0 for video-only MP4 input "
            "(MYTUBE-391 Step 1)."
        )

    def test_thumbnail_jpg_exists_in_gcs(
        self,
        video_only_test_run: dict,
        transcoder_service: HLSTranscoderService,
        gcp_config: GcpConfig,
    ) -> None:
        """thumbnail.jpg must exist in the HLS-output bucket after a video-only job.

        Expected GCS path: ``videos/{VIDEO_ID}/thumbnail.jpg`` in the
        HLS-output bucket (``mytube-hls-output`` by default).

        When thumbnail extraction silently fails for video-only input, the
        transcoder must write the standard system placeholder image to this
        path instead of leaving the object absent.
        """
        video_id = video_only_test_run["video_id"]
        job_result = video_only_test_run["job_result"]

        # Only check GCS if the job succeeded.
        if not job_result.success:
            pytest.skip(
                f"Skipping thumbnail check — transcoding job did not succeed "
                f"(exit_code={job_result.exit_code})."
            )

        thumb_object = f"videos/{video_id}/thumbnail.jpg"
        output_objects = transcoder_service.list_output_objects(video_id)

        assert thumb_object in output_objects, (
            f"thumbnail.jpg is absent from the GCS output bucket after "
            f"transcoding a video-only MP4.\n\n"
            f"Expected object: gs://{gcp_config.hls_bucket}/{thumb_object}\n"
            f"Objects actually found under videos/{video_id}/:\n"
            + "\n".join(f"  {o}" for o in output_objects)
            + "\n\n"
            "The system must upload a standard placeholder image as "
            "'thumbnail.jpg' when FFmpeg cannot extract a frame from a "
            "video-only source (MYTUBE-391 Expected Result)."
        )

    def test_thumbnail_jpg_is_valid_jpeg(
        self,
        video_only_test_run: dict,
        transcoder_service: HLSTranscoderService,
        gcp_config: GcpConfig,
        storage_client,
    ) -> None:
        """The thumbnail.jpg file must be a valid JPEG (non-empty, JPEG SOI header).

        Downloads the first 2 bytes of the GCS object and verifies the JPEG
        Start-Of-Image (SOI) magic bytes ``\\xFF\\xD8``.
        """
        video_id = video_only_test_run["video_id"]
        job_result = video_only_test_run["job_result"]

        if not job_result.success:
            pytest.skip("Skipping JPEG validation — job did not succeed.")

        thumb_object = f"videos/{video_id}/thumbnail.jpg"
        output_objects = transcoder_service.list_output_objects(video_id)
        if thumb_object not in output_objects:
            pytest.skip(
                "Skipping JPEG validation — thumbnail.jpg not present in GCS "
                "(see test_thumbnail_jpg_exists_in_gcs)."
            )

        from testing.components.services.gcs_service import GCSService
        from testing.core.config.gcs_config import GCSConfig
        gcs_cfg = GCSConfig()
        gcs_svc = GCSService(
            config=gcs_cfg,
            storage_client=storage_client,
        )
        header_bytes = gcs_svc.download_object_bytes(
            gcp_config.hls_bucket, thumb_object, start=0, end=2
        )

        assert header_bytes == _JPEG_SOI, (
            f"thumbnail.jpg in GCS does not start with the JPEG SOI magic "
            f"bytes (\\xFF\\xD8).\n\n"
            f"Expected first 2 bytes: {_JPEG_SOI!r}\n"
            f"Actual first 2 bytes:   {header_bytes!r}\n\n"
            "The placeholder image must be a valid JPEG file so it can be "
            "displayed by browsers and native apps."
        )
