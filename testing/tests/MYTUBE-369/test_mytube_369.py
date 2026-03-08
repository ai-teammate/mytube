"""
MYTUBE-369: Transcode video with no audio — job exits with code 0 and produces HLS output.

Objective
---------
Verify that the transcoder correctly handles video files without audio streams,
producing valid HLS output instead of failing with an FFmpeg map error.

Preconditions
-------------
A video file containing only a video stream (no audio) is available for testing.

Steps
-----
1. Upload the silent video file to the raw uploads bucket.
2. Trigger the Cloud Run transcoding job for this specific video ID.
3. Monitor the job execution logs and exit code.
4. Inspect the output bucket `mytube-hls-output` under `videos/{VIDEO_ID}/`
   for the generated files.

Expected Result
---------------
The Cloud Run job exits with code 0. A master HLS manifest (`index.m3u8`),
all rendition sub-playlists, and segments are successfully generated in the
output bucket.

Environment variables
---------------------
- GCP_PROJECT_ID                  : GCP project containing the Cloud Run Job (required).
- GCP_REGION                      : Region of the Cloud Run Job (default: us-central1).
- GCP_RAW_BUCKET                  : Raw uploads bucket (default: mytube-raw-uploads).
- GCP_HLS_BUCKET                  : HLS output bucket (default: mytube-hls-output).
- GCP_TRANSCODER_JOB              : Cloud Run Job name (default: mytube-transcoder).
- DB_DSN                          : PostgreSQL DSN passed to the transcoder job.
- CDN_BASE_URL                    : CDN base URL passed to the transcoder job.
- GOOGLE_APPLICATION_CREDENTIALS  : Path to a GCP service account key (or use ADC).

Architecture
------------
- HLSTranscoderService triggers the Cloud Run Job and inspects GCS output.
- UserService / VideoService insert DB precondition rows required by the job.
- A video-only MP4 (no audio) is generated via FFmpeg, uploaded to GCS, and
  passed to the transcoder so that the no-audio code path is exercised.
"""
from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.tests.conftest import make_conn_fixture
from testing.core.config.db_config import DBConfig
from testing.core.config.gcp_config import GcpConfig
from testing.components.services.user_service import UserService
from testing.components.services.video_service import VideoService
from testing.components.services.hls_transcoder_service import (
    HLSMasterPlaylist,
    HLSTranscoderService,
)

# ---------------------------------------------------------------------------
# Migration path
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)
_INITIAL_SCHEMA = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")

conn = make_conn_fixture(
    [_INITIAL_SCHEMA],
    test_usernames=["testuser_mytube369"],
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def gcp_config() -> GcpConfig:
    cfg = GcpConfig()
    if not cfg.project_id:
        pytest.skip(
            "GCP_PROJECT_ID is not set — cannot run Cloud Run Job. "
            "Set GCP_PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS to run this test."
        )
    return cfg


@pytest.fixture(scope="module")
def db_dsn() -> str:
    value = os.environ.get("DB_DSN", "")
    if not value:
        db_cfg = DBConfig()
        return db_cfg.dsn()
    return value


@pytest.fixture(scope="module")
def storage_client(gcp_config: GcpConfig):
    """Create an authenticated GCS client; skip if credentials are unavailable."""
    try:
        from google.cloud import storage as gcs_storage
        from google.auth.exceptions import DefaultCredentialsError
    except ImportError:
        pytest.skip("google-cloud-storage is not installed")

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
def transcoded_silent_video(
    conn,
    gcp_config: GcpConfig,
    transcoder_service: HLSTranscoderService,
    storage_client,
    db_dsn: str,
) -> dict:
    """
    Insert a video row, generate a video-only MP4 (no audio), upload it to
    the raw bucket, run the Cloud Run transcoder, and return the outcome.

    Yields a dict with:
      - video_id          : UUID of the video row inserted into the DB
      - job_result        : JobExecutionResult from the Cloud Run job
      - output_objects    : list of GCS object names under videos/{video_id}/
    """
    # ── Precondition: insert user (FK) and video rows ─────────────────────
    user_svc = UserService(conn)
    user_id = user_svc.create_user("firebase-uid-mytube369", "testuser_mytube369")

    video_svc = VideoService(conn)
    video_id, _ = video_svc.insert_video(user_id, "Silent Video Test MYTUBE-369", "processing")
    video_id = str(video_id)

    # ── Step 1: Generate a video-only MP4 (no audio stream) ──────────────
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name

    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "color=c=black:s=1280x720:d=5",
            "-c:v", "libx264",
            "-an",          # explicitly disable audio — this is the key for the test
            "-t", "5",
            "-movflags", "+faststart",
            tmp_path,
        ],
        check=True,
        capture_output=True,
    )

    # ── Step 1 (ticket): Upload the silent video to the raw uploads bucket ─
    raw_object_key = f"test-videos/{video_id}/input.mp4"
    raw_bucket = storage_client.bucket(gcp_config.raw_bucket)
    raw_blob = raw_bucket.blob(raw_object_key)
    raw_blob.upload_from_filename(tmp_path)
    pathlib.Path(tmp_path).unlink(missing_ok=True)

    # ── Step 2 (ticket): Trigger the Cloud Run transcoding job ────────────
    job_result = transcoder_service.run_transcoding_job(
        video_id=video_id,
        raw_object_path=raw_object_key,
        db_dsn=db_dsn,
    )

    # ── Step 4 (ticket): Collect output objects for assertions ────────────
    output_objects: list[str] = []
    if job_result.success:
        output_objects = transcoder_service.list_output_objects(video_id)

    yield {
        "video_id": video_id,
        "job_result": job_result,
        "output_objects": output_objects,
    }

    # ── Teardown: remove the raw GCS object (best-effort) ─────────────────
    try:
        raw_bucket.blob(raw_object_key).delete()
    except Exception:
        pass

    # ── Teardown: best-effort cleanup of HLS output objects under videos/{video_id}/
    try:
        hls_bucket = storage_client.bucket(gcp_config.hls_bucket)
        prefix = f"videos/{video_id}/"
        # list_blobs returns an iterator; convert to list to avoid generator issues
        blobs = list(hls_bucket.list_blobs(prefix=prefix))
        for blob in blobs:
            try:
                blob.delete()
            except Exception:
                # ignore individual delete failures
                pass
    except Exception:
        # ignore failures during cleanup
        pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSilentVideoTranscoding:
    """MYTUBE-369: Transcoding a video with no audio must succeed and produce HLS output."""

    # ---- Step 2–3: Job execution and exit code --------------------------

    def test_job_exits_with_code_zero(self, transcoded_silent_video: dict) -> None:
        """Step 2–3 — Cloud Run Job must complete with exit code 0."""
        result = transcoded_silent_video["job_result"]
        assert result.success, (
            f"Cloud Run Job failed with exit code {result.exit_code} "
            f"when processing a video-only (no audio) file.\n"
            f"STDOUT: {result.stdout}\n"
            f"STDERR: {result.stderr}\n"
            f"Error:  {result.error_message}\n"
            "This may indicate an FFmpeg '-map' error when audio streams are absent. "
            "The transcoder should use '-map 0:v' and '-map 0:a?' (optional audio) "
            "to handle silent videos gracefully."
        )

    # ---- Step 4: Output bucket inspection --------------------------------

    def test_output_folder_is_not_empty(self, transcoded_silent_video: dict) -> None:
        """Step 4 — Output bucket must contain at least one file under videos/{VIDEO_ID}/."""
        video_id = transcoded_silent_video["video_id"]
        objects = transcoded_silent_video["output_objects"]
        assert len(objects) > 0, (
            f"No objects found under 'videos/{video_id}/' in the HLS output bucket "
            "after transcoding a silent (no-audio) video. "
            "The transcoder may have exited before writing any output."
        )

    def test_master_manifest_exists(
        self,
        transcoded_silent_video: dict,
        transcoder_service: HLSTranscoderService,
        gcp_config: GcpConfig,
    ) -> None:
        """Step 4 — Master HLS manifest index.m3u8 must be present."""
        video_id = transcoded_silent_video["video_id"]
        raw_content = transcoder_service.download_master_playlist(video_id)
        assert raw_content is not None, (
            f"Master playlist 'videos/{video_id}/index.m3u8' not found in bucket "
            f"'{gcp_config.hls_bucket}' after transcoding a silent video."
        )

    def test_master_manifest_is_valid_hls(
        self,
        transcoded_silent_video: dict,
        transcoder_service: HLSTranscoderService,
    ) -> None:
        """Step 4 — Master manifest must be a valid HLS playlist (starts with #EXTM3U)."""
        video_id = transcoded_silent_video["video_id"]
        raw_content = transcoder_service.download_master_playlist(video_id)
        if raw_content is None:
            pytest.skip("index.m3u8 not present — covered by test_master_manifest_exists")
        assert raw_content.strip().startswith("#EXTM3U"), (
            "Master playlist does not begin with '#EXTM3U'. "
            f"Content starts with: {raw_content[:120]!r}"
        )

    def test_master_manifest_contains_renditions(
        self,
        transcoded_silent_video: dict,
        transcoder_service: HLSTranscoderService,
    ) -> None:
        """Step 4 — Master manifest must reference at least one rendition stream."""
        video_id = transcoded_silent_video["video_id"]
        raw_content = transcoder_service.download_master_playlist(video_id)
        if raw_content is None:
            pytest.skip("index.m3u8 not present — covered by test_master_manifest_exists")
        playlist = transcoder_service.parse_master_playlist(raw_content)
        assert len(playlist.renditions) >= 1, (
            "No #EXT-X-STREAM-INF entries found in the master playlist for a "
            "silent (no-audio) video. "
            f"Playlist content:\n{raw_content}"
        )

    def test_segment_files_exist(self, transcoded_silent_video: dict) -> None:
        """Step 4 — At least one .ts segment or rendition .m3u8 sub-playlist must be present."""
        video_id = transcoded_silent_video["video_id"]
        objects = transcoded_silent_video["output_objects"]
        segment_files = [
            o for o in objects
            if o.endswith(".ts") or (o.endswith(".m3u8") and not o.endswith("index.m3u8"))
        ]
        assert len(segment_files) > 0, (
            f"No .ts segment or rendition playlist files found under "
            f"'videos/{video_id}/' for a silent (no-audio) video. "
            f"Objects present: {objects}"
        )

    @pytest.mark.parametrize("label", ["360p", "720p", "1080p"])
    def test_required_rendition_present(
        self,
        label: str,
        transcoded_silent_video: dict,
        transcoder_service: HLSTranscoderService,
    ) -> None:
        """Step 4 — All three required renditions (360p, 720p, 1080p) must be present."""
        video_id = transcoded_silent_video["video_id"]
        raw_content = transcoder_service.download_master_playlist(video_id)
        if raw_content is None:
            pytest.skip("index.m3u8 not present — covered by test_master_manifest_exists")
        playlist = transcoder_service.parse_master_playlist(raw_content)
        present = transcoder_service.has_required_renditions(playlist)
        bandwidths = {r.bandwidth for r in playlist.renditions}
        assert present[label], (
            f"Required rendition '{label}' not found in master playlist for a "
            f"silent (no-audio) video. "
            f"Detected BANDWIDTH values: {sorted(bandwidths)} bps.\n"
            f"Expected bandwidth ranges:\n"
            f"  360p:  400k–600k bps\n"
            f"  720p:  1200k–1800k bps\n"
            f"  1080p: 2400k–3600k bps\n"
            f"Playlist content:\n{raw_content}"
        )
