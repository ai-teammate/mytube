"""
MYTUBE-78: Transcode raw video to HLS — job produces required HLS renditions
and master playlist.

Verifies that the Cloud Run Job correctly transcodes a raw video file into the
specified multi-bitrate HLS renditions.

Steps:
  1. Execute the Cloud Run Job for a specific VIDEO_ID.
  2. Inspect the ``mytube-hls-output`` bucket under ``videos/{VIDEO_ID}/``.
  3. Download and inspect the ``index.m3u8`` master playlist file.

Expected Result:
  The output bucket contains the master playlist, and the playlist defines at
  minimum three streams: 360p (500k), 720p (1500k), and 1080p (3000k) with
  their respective segment files.

Prerequisites (environment variables):
  - GCP_PROJECT_ID         — GCP project containing the Cloud Run Job
  - GCP_REGION             — region of the Cloud Run Job (default: us-central1)
  - GCP_HLS_BUCKET         — HLS output bucket (default: mytube-hls-output)
  - VIDEO_ID               — ID of the video to transcode
  - RAW_OBJECT_PATH        — GCS path to the raw video (e.g. raw/<uuid>.mp4)
  - DB_DSN                 — PostgreSQL DSN for the job
  - GOOGLE_APPLICATION_CREDENTIALS (or ADC) with sufficient GCP permissions
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.gcp_config import GcpConfig
from testing.components.services.hls_transcoder_service import (
    HLSMasterPlaylist,
    HLSTranscoderService,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    return GcpConfig()


@pytest.fixture(scope="module")
def video_id() -> str:
    value = os.environ.get("VIDEO_ID", "")
    if not value:
        pytest.skip("VIDEO_ID is not set — skipping HLS transcoding test.")
    return value


@pytest.fixture(scope="module")
def raw_object_path() -> str:
    value = os.environ.get("RAW_OBJECT_PATH", "")
    if not value:
        pytest.skip("RAW_OBJECT_PATH is not set — skipping HLS transcoding test.")
    return value


@pytest.fixture(scope="module")
def db_dsn() -> str:
    value = os.environ.get("DB_DSN", "")
    if not value:
        pytest.skip("DB_DSN is not set — skipping HLS transcoding test.")
    return value


@pytest.fixture(scope="module")
def storage_client(gcp_config: GcpConfig):
    """Create an authenticated GCS client; skip if credentials are unavailable."""
    try:
        from google.cloud import storage as gcs_storage
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        pytest.skip("google-cloud-storage is not installed")

    if not gcp_config.project_id:
        pytest.skip(
            "GCP_PROJECT_ID is not set — cannot authenticate with GCS. "
            "Set GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS to run this test."
        )

    try:
        client = gcs_storage.Client(project=gcp_config.project_id)
    except DefaultCredentialsError as exc:
        pytest.skip(
            f"GCP credentials not available: {exc}. "
            "Configure GOOGLE_APPLICATION_CREDENTIALS or Application Default Credentials."
        )

    return client


@pytest.fixture(scope="module")
def transcoder_service(gcp_config: GcpConfig, storage_client) -> HLSTranscoderService:
    return HLSTranscoderService(config=gcp_config, storage_client=storage_client)


@pytest.fixture(scope="module")
def job_result(
    transcoder_service: HLSTranscoderService,
    video_id: str,
    raw_object_path: str,
    db_dsn: str,
):
    """Execute the transcoding Cloud Run Job once for the entire test module."""
    return transcoder_service.run_transcoding_job(
        video_id=video_id,
        raw_object_path=raw_object_path,
        db_dsn=db_dsn,
    )


@pytest.fixture(scope="module")
def master_playlist(
    transcoder_service: HLSTranscoderService,
    job_result,
    video_id: str,
) -> HLSMasterPlaylist:
    """Download and parse the master playlist produced by the job."""
    raw_content = transcoder_service.download_master_playlist(video_id)
    assert raw_content is not None, (
        f"Master playlist 'videos/{video_id}/index.m3u8' not found in bucket "
        f"'{transcoder_service._config.hls_bucket}' after job execution."
    )
    return transcoder_service.parse_master_playlist(raw_content)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHLSTranscoding:
    """Cloud Run Job must produce required HLS renditions and master playlist."""

    # ---- Step 1: Job execution ----------------------------------------

    def test_job_executes_successfully(self, job_result):
        """Step 1 — Cloud Run Job must complete without error."""
        assert job_result.success, (
            f"Cloud Run Job failed with exit code {job_result.exit_code}.\n"
            f"STDOUT: {job_result.stdout}\n"
            f"STDERR: {job_result.stderr}\n"
            f"Error: {job_result.error_message}"
        )

    # ---- Step 2: Output bucket inspection ----------------------------

    def test_output_bucket_contains_video_folder(
        self, transcoder_service: HLSTranscoderService, job_result, video_id: str
    ):
        """Step 2 — HLS output bucket must contain objects under videos/{VIDEO_ID}/."""
        objects = transcoder_service.list_output_objects(video_id)
        assert len(objects) > 0, (
            f"No objects found under 'videos/{video_id}/' in bucket "
            f"'{transcoder_service._config.hls_bucket}'. "
            "The transcoding job may not have produced any output."
        )

    def test_master_playlist_exists(
        self, transcoder_service: HLSTranscoderService, job_result, video_id: str
    ):
        """Step 2 — Master playlist index.m3u8 must be present in the output folder."""
        raw_content = transcoder_service.download_master_playlist(video_id)
        assert raw_content is not None, (
            f"Master playlist 'videos/{video_id}/index.m3u8' not found in bucket "
            f"'{transcoder_service._config.hls_bucket}'."
        )

    def test_segment_files_exist(
        self, transcoder_service: HLSTranscoderService, job_result, video_id: str
    ):
        """Step 2 — At least one .ts or .m3u8 segment/rendition file must be present."""
        objects = transcoder_service.list_output_objects(video_id)
        segment_files = [
            o for o in objects
            if o.endswith(".ts") or (o.endswith(".m3u8") and not o.endswith("index.m3u8"))
        ]
        assert len(segment_files) > 0, (
            f"No segment (.ts) or rendition playlist (.m3u8) files found under "
            f"'videos/{video_id}/' in bucket '{transcoder_service._config.hls_bucket}'. "
            f"Objects present: {objects}"
        )

    # ---- Step 3: Master playlist content -----------------------------

    def test_master_playlist_has_hls_header(self, master_playlist: HLSMasterPlaylist):
        """Step 3 — Master playlist must start with #EXTM3U."""
        assert master_playlist.raw_content.strip().startswith("#EXTM3U"), (
            "Master playlist does not begin with '#EXTM3U'. "
            f"Content starts with: {master_playlist.raw_content[:100]!r}"
        )

    def test_master_playlist_contains_stream_inf_tags(self, master_playlist: HLSMasterPlaylist):
        """Step 3 — Master playlist must contain at least one #EXT-X-STREAM-INF tag."""
        assert len(master_playlist.renditions) >= 1, (
            "No #EXT-X-STREAM-INF entries found in the master playlist. "
            f"Playlist content:\n{master_playlist.raw_content}"
        )

    @pytest.mark.parametrize("label", ["360p", "720p", "1080p"])
    def test_master_playlist_has_required_rendition(
        self,
        label: str,
        transcoder_service: HLSTranscoderService,
        master_playlist: HLSMasterPlaylist,
    ):
        """Step 3 — Master playlist must define 360p (500k), 720p (1500k), and 1080p (3000k) streams."""
        present = transcoder_service.has_required_renditions(master_playlist)
        bandwidths = {r.bandwidth for r in master_playlist.renditions}
        assert present[label], (
            f"Required rendition '{label}' not found in master playlist. "
            f"Renditions detected (by BANDWIDTH): {sorted(bandwidths)} bps.\n"
            f"Expected bandwidth ranges:\n"
            f"  360p:  400k–600k bps\n"
            f"  720p:  1200k–1800k bps\n"
            f"  1080p: 2400k–3600k bps\n"
            f"Playlist content:\n{master_playlist.raw_content}"
        )
