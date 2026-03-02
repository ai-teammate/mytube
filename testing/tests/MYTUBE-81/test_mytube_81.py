"""
MYTUBE-81: Generate video thumbnail — thumbnail extracted at the 5-second mark.

Objective:
    Verify that a JPEG thumbnail is correctly extracted from the source video at
    the 5-second timestamp and uploaded to the correct GCS path.

Test structure:
    Part A — Local contract tests (always run, no GCP required):
        Run the Go unit-test suite for `api/cmd/transcoder` via subprocess to
        confirm that:
        1. The transcoder binary builds without errors.
        2. The unit tests pass (all stub-based tests confirming pipeline behaviour).
        3. ExtractThumbnail is called with offset = 5 seconds.
        4. The thumbnail is uploaded to `videos/{VIDEO_ID}/thumbnail.jpg`.
        5. The thumbnail URL written to the DB uses the CDN base URL pattern
           `{CDN_BASE_URL}/videos/{VIDEO_ID}/thumbnail.jpg`.

    Part B — Infrastructure smoke tests (skipped when GCP credentials absent):
        Use the google-cloud-storage SDK to verify, against the live HLS output
        bucket, that:
        1. The `mytube-hls-output` bucket exists and is accessible.
        2. A `thumbnail.jpg` object exists at
           `videos/{VIDEO_ID}/thumbnail.jpg` for a known, transcoded video.
        3. The object is a valid JPEG (magic bytes FF D8 FF).
"""

import os
import subprocess
import sys

import pytest

# Make the testing root importable regardless of invocation directory.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TRANSCODER_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "api", "cmd", "transcoder")
)

# JPEG magic bytes: every valid JPEG starts with FF D8 FF.
JPEG_MAGIC = b"\xff\xd8\xff"

# GCS path template for thumbnails.
THUMBNAIL_OBJECT_TEMPLATE = "videos/{video_id}/thumbnail.jpg"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    """GCP configuration from environment variables."""
    return GcpConfig()


@pytest.fixture(scope="module")
def gcp_project(gcp_config: GcpConfig) -> str:
    """GCP project ID.  Skips Part B when not set."""
    if not gcp_config.project_id:
        pytest.skip("GCP_PROJECT_ID not set — infrastructure tests skipped")
    return gcp_config.project_id


@pytest.fixture(scope="module")
def hls_bucket(gcp_config: GcpConfig) -> str:
    """HLS output bucket name."""
    return gcp_config.hls_bucket


@pytest.fixture(scope="module")
def video_id_for_smoke_test() -> str:
    """
    VIDEO_ID of a previously transcoded video to check in the live bucket.

    If not set the infrastructure tests are skipped — there is no value in
    asserting a random path exists without a known, transcoded video.
    """
    video_id = os.environ.get("TEST_VIDEO_ID", "")
    if not video_id:
        pytest.skip(
            "TEST_VIDEO_ID not set — skipping live bucket thumbnail verification"
        )
    return video_id


@pytest.fixture(scope="module")
def gcs_client(gcp_project):
    """Authenticated google-cloud-storage Client."""
    try:
        from google.cloud import storage as gcs

        return gcs.Client(project=gcp_project)
    except ImportError:
        pytest.skip("google-cloud-storage not installed")


# ---------------------------------------------------------------------------
# Part A — Local contract tests (always run, no GCP required)
# ---------------------------------------------------------------------------


class TestTranscoderThumbnailContract:
    """
    Verifies the thumbnail generation contract by running the Go unit-test
    suite for `api/cmd/transcoder`.

    These tests exercise all thumbnail-related code paths using in-process
    stubs, without requiring FFmpeg, GCS, or a database.  A passing suite
    confirms that:
      - ExtractThumbnail is invoked with offsetSeconds = 5.
      - The thumbnail local path is `<workDir>/thumbnail.jpg`.
      - The thumbnail is uploaded to `videos/<VIDEO_ID>/thumbnail.jpg`.
      - The ThumbnailURL written to the DB follows the CDN pattern.
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

    def test_transcoder_unit_tests_pass(self):
        """
        The full transcoder unit-test suite must pass.

        This is the primary automated verification that the thumbnail pipeline
        is wired correctly end-to-end within the Go test infrastructure.
        """
        result = subprocess.run(
            ["go", "test", "-v", "-count=1", "./..."],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"go test ./... failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    def test_extract_thumbnail_called_with_5_second_offset(self):
        """
        The pipeline must call ExtractThumbnail with offsetSeconds = 5.

        Verified by TestTranscode_HappyPath_CallsAllSteps, which uses a
        stubTranscoder that records calls.  The go test suite confirms the
        offset value via TestTranscode_HappyPath_UpdatesDBWithCorrectPaths.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1", "-run",
                "TestTranscode_HappyPath_CallsAllSteps",
                ".",
            ],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_HappyPath_CallsAllSteps failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout, (
            f"Expected PASS in output.\nSTDOUT:\n{result.stdout}"
        )

    def test_thumbnail_uploaded_to_correct_gcs_path(self):
        """
        The pipeline must upload the thumbnail to
        `videos/{VIDEO_ID}/thumbnail.jpg` in the HLS output bucket.

        Verified by TestTranscode_HappyPath_UploadsHLSAndThumbnail.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1", "-run",
                "TestTranscode_HappyPath_UploadsHLSAndThumbnail",
                ".",
            ],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_HappyPath_UploadsHLSAndThumbnail failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout, (
            f"Expected PASS in output.\nSTDOUT:\n{result.stdout}"
        )

    def test_thumbnail_url_written_to_db_with_cdn_pattern(self):
        """
        The DB update must store ThumbnailURL as
        `{CDN_BASE_URL}/videos/{VIDEO_ID}/thumbnail.jpg`.

        Verified by TestTranscode_HappyPath_UpdatesDBWithCorrectPaths.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1", "-run",
                "TestTranscode_HappyPath_UpdatesDBWithCorrectPaths",
                ".",
            ],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_HappyPath_UpdatesDBWithCorrectPaths failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout, (
            f"Expected PASS in output.\nSTDOUT:\n{result.stdout}"
        )

    def test_ffmpeg_thumbnail_extraction_unit_tests_pass(self):
        """
        The FFmpeg runner unit tests for thumbnail extraction must pass.

        These tests verify the exact FFmpeg arguments used to extract a frame
        at an offset (including offset = 5) from the source video.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "./internal/ffmpeg/",
            ],
            cwd=TRANSCODER_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"ffmpeg unit tests failed.\n"
            f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Part B — Infrastructure smoke tests (require GCP credentials + TEST_VIDEO_ID)
# ---------------------------------------------------------------------------


class TestThumbnailInfrastructure:
    """
    Smoke tests that verify a thumbnail exists in the live HLS output bucket
    for a known, already-transcoded video.

    All tests in this class are skipped when GCP_PROJECT_ID or TEST_VIDEO_ID
    environment variables are not set.
    """

    def test_hls_bucket_is_accessible(self, gcs_client, hls_bucket):
        """
        The `mytube-hls-output` GCS bucket must be accessible to the
        authenticated caller.
        """
        bucket = gcs_client.bucket(hls_bucket)
        assert bucket.exists(), (
            f"HLS output bucket '{hls_bucket}' does not exist or is not accessible. "
            "Ensure the bucket is provisioned and credentials are valid."
        )

    def test_thumbnail_object_exists_in_bucket(
        self, gcs_client, hls_bucket, video_id_for_smoke_test
    ):
        """
        A `thumbnail.jpg` must exist at
        `videos/{VIDEO_ID}/thumbnail.jpg` in the HLS output bucket.

        This confirms the transcoder uploaded the thumbnail after processing
        the video identified by TEST_VIDEO_ID.
        """
        object_path = THUMBNAIL_OBJECT_TEMPLATE.format(
            video_id=video_id_for_smoke_test
        )
        blob = gcs_client.bucket(hls_bucket).blob(object_path)
        assert blob.exists(), (
            f"Thumbnail not found at gs://{hls_bucket}/{object_path}. "
            "The transcoder may not have run, or the VIDEO_ID is incorrect."
        )

    def test_thumbnail_is_valid_jpeg(
        self, gcs_client, hls_bucket, video_id_for_smoke_test
    ):
        """
        The thumbnail object must be a valid JPEG file.

        Reads the first 3 bytes of the GCS object and checks for the JPEG
        magic number (FF D8 FF).  This confirms FFmpeg produced a real JPEG
        and not a zero-byte or corrupted file.
        """
        object_path = THUMBNAIL_OBJECT_TEMPLATE.format(
            video_id=video_id_for_smoke_test
        )
        blob = gcs_client.bucket(hls_bucket).blob(object_path)
        # Download only the first 3 bytes to avoid unnecessary data transfer.
        first_bytes = blob.download_as_bytes(start=0, end=2)
        assert first_bytes == JPEG_MAGIC, (
            f"Thumbnail at gs://{hls_bucket}/{object_path} is not a valid JPEG. "
            f"First 3 bytes: {first_bytes!r}, expected: {JPEG_MAGIC!r}. "
            "The transcoder may have written a corrupt file."
        )
