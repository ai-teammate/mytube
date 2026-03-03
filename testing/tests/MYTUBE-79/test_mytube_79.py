"""
MYTUBE-79: Update video record on success — database fields populated correctly
after transcoding.

Verifies that after the transcoding Cloud Run Job completes successfully, the
`videos` table row for the given VIDEO_ID is updated with:
  - status = 'ready'
  - hls_manifest_path = 'gs://mytube-hls-output/videos/{VIDEO_ID}/index.m3u8'
  - thumbnail_url set to the CDN-based path

Test sequence:
  1. Apply the initial schema migration to a clean database.
  2. Insert a user row (required by the videos FK) via UserService.
  3. Insert a video row with status 'processing' via VideoService.
  4. Execute the Cloud Run Job via HLSTranscoderService (the actual transcoder).
  5. Query the `videos` table and assert that the transcoder updated all three
     fields correctly.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.tests.conftest import make_conn_fixture
from testing.core.config.db_config import DBConfig
from testing.core.config.gcp_config import GcpConfig
from testing.components.services.user_service import UserService
from testing.components.services.video_service import VideoService
from testing.components.services.hls_transcoder_service import HLSTranscoderService

# ---------------------------------------------------------------------------
# Migration path
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)

_INITIAL_SCHEMA = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")

# Module-scoped DB connection fixture — wipes schema and re-applies migration.
conn = make_conn_fixture([_INITIAL_SCHEMA])


# ---------------------------------------------------------------------------
# Environment-driven fixtures (skip when vars are absent)
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
def raw_object_path() -> str:
    value = os.environ.get("RAW_OBJECT_PATH", "")
    if not value:
        pytest.skip("RAW_OBJECT_PATH is not set — skipping transcoder integration test.")
    return value


@pytest.fixture(scope="module")
def db_dsn() -> str:
    value = os.environ.get("DB_DSN", "")
    if not value:
        # Fall back to building a DSN from the individual DB_* env vars used by conftest.
        db_cfg = DBConfig()
        dsn = db_cfg.dsn()
        return dsn
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


# ---------------------------------------------------------------------------
# Module-scoped fixture: set up precondition and run the actual transcoder
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def transcoded_video(
    conn,
    gcp_config: GcpConfig,
    transcoder_service: HLSTranscoderService,
    raw_object_path: str,
    db_dsn: str,
) -> dict:
    """
    Insert a video row with status 'processing', trigger the real Cloud Run
    transcoding job for that video, then return the row the transcoder updated.

    The returned dict contains:
      - video_id
      - status           (as written by the transcoder)
      - hls_manifest_path (as written by the transcoder)
      - thumbnail_url    (as written by the transcoder)
      - expected_hls_manifest_path (derived from config for comparison)
      - expected_thumbnail_url     (derived from config for comparison)
    """
    gcp_cfg = gcp_config

    # ── Precondition: insert a user (FK dependency) via UserService ───────
    user_svc = UserService(conn)
    user_id = user_svc.create_user("firebase-uid-mytube79", "testuser_mytube79")

    # ── Precondition: insert video row with status 'processing' via VideoService
    video_svc = VideoService(conn)
    video_id, initial_status = video_svc.insert_video(user_id, "Test Transcoding Video", "processing")
    video_id = str(video_id)

    assert initial_status in ("processing", "pending"), (
        f"Precondition failed: expected status 'processing' or 'pending', got '{initial_status}'."
    )

    # ── Step 1 (ticket): Run the Cloud Run transcoding job ────────────────
    job_result = transcoder_service.run_transcoding_job(
        video_id=video_id,
        raw_object_path=raw_object_path,
        db_dsn=db_dsn,
    )

    assert job_result.success, (
        f"Cloud Run Job failed with exit code {job_result.exit_code}.\n"
        f"STDOUT: {job_result.stdout}\n"
        f"STDERR: {job_result.stderr}\n"
        f"Error: {job_result.error_message}"
    )

    # ── Step 2 (ticket): Query the videos table for the updated record ────
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, hls_manifest_path, thumbnail_url FROM videos WHERE id = %s",
            (video_id,),
        )
        updated = cur.fetchone()

    assert updated is not None, f"Video row {video_id} not found after transcoding job."

    # Derive the expected values from config (same logic as the transcoder)
    # These are used as the expected side of the assertions, but the actual
    # values are whatever the transcoder wrote — not pre-computed by the test.
    expected_hls_manifest_path = f"gs://{gcp_cfg.hls_bucket}/videos/{video_id}/index.m3u8"
    expected_thumbnail_url = f"{gcp_cfg.cdn_base_url}/videos/{video_id}/thumbnail.jpg"

    return {
        "video_id": video_id,
        "status": updated[0],
        "hls_manifest_path": updated[1],
        "thumbnail_url": updated[2],
        "expected_hls_manifest_path": expected_hls_manifest_path,
        "expected_thumbnail_url": expected_thumbnail_url,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVideoRecordUpdatedOnSuccess:
    """The videos row must reflect a successful transcoding run."""

    def test_status_is_ready(self, transcoded_video: dict):
        assert transcoded_video["status"] == "ready", (
            f"Expected status 'ready', got '{transcoded_video['status']}'."
        )

    def test_hls_manifest_path_matches_expected_pattern(self, transcoded_video: dict):
        """hls_manifest_path must be gs://<hls_bucket>/videos/<VIDEO_ID>/index.m3u8."""
        actual = transcoded_video["hls_manifest_path"]
        expected = transcoded_video["expected_hls_manifest_path"]
        assert actual == expected, (
            f"hls_manifest_path mismatch:\n  actual:   {actual}\n  expected: {expected}"
        )

    def test_hls_manifest_path_contains_video_id(self, transcoded_video: dict):
        """The manifest path must embed the video's own UUID."""
        actual = transcoded_video["hls_manifest_path"]
        video_id = transcoded_video["video_id"]
        assert video_id in actual, (
            f"VIDEO_ID '{video_id}' not found in hls_manifest_path '{actual}'."
        )

    def test_hls_manifest_path_ends_with_index_m3u8(self, transcoded_video: dict):
        """The manifest path must end with /index.m3u8."""
        actual = transcoded_video["hls_manifest_path"]
        assert actual.endswith("/index.m3u8"), (
            f"hls_manifest_path '{actual}' does not end with '/index.m3u8'."
        )

    def test_thumbnail_url_matches_cdn_path(self, transcoded_video: dict):
        """thumbnail_url must be the CDN-based path for the video's thumbnail."""
        actual = transcoded_video["thumbnail_url"]
        expected = transcoded_video["expected_thumbnail_url"]
        assert actual == expected, (
            f"thumbnail_url mismatch:\n  actual:   {actual}\n  expected: {expected}"
        )

    def test_thumbnail_url_contains_video_id(self, transcoded_video: dict):
        """The thumbnail URL must embed the video's own UUID."""
        actual = transcoded_video["thumbnail_url"]
        video_id = transcoded_video["video_id"]
        assert video_id in actual, (
            f"VIDEO_ID '{video_id}' not found in thumbnail_url '{actual}'."
        )

    def test_thumbnail_url_ends_with_thumbnail_jpg(self, transcoded_video: dict):
        """The thumbnail URL must end with /thumbnail.jpg."""
        actual = transcoded_video["thumbnail_url"]
        assert actual.endswith("/thumbnail.jpg"), (
            f"thumbnail_url '{actual}' does not end with '/thumbnail.jpg'."
        )
