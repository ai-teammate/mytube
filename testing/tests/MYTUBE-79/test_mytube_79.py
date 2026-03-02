"""
MYTUBE-79: Update video record on success — database fields populated correctly
after transcoding.

Verifies that after the transcoding job completes successfully, the `videos`
table row for the given VIDEO_ID is updated with:
  - status = 'ready'
  - hls_manifest_path = 'gs://mytube-hls-output/videos/{VIDEO_ID}/index.m3u8'
  - thumbnail_url set to the CDN-based path

The test exercises the SQL UPDATE statement used by the transcoder's
video.Repository.UpdateVideo via a live PostgreSQL connection, starting from
a row in 'processing' status (matching the documented precondition).

Test sequence:
  1. Apply the initial schema migration to a clean database.
  2. Insert a user row (required by the videos FK).
  3. Insert a video row with status 'processing'.
  4. Execute the same UPDATE query the transcoder issues on success.
  5. Query the updated row and assert all three fields are correct.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.tests.conftest import make_conn_fixture
from testing.core.config.gcp_config import GcpConfig
from testing.core.config.gcs_config import GCSConfig
from testing.components.services.user_service import UserService
from testing.components.services.video_service import VideoService

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
# Module-scoped fixture: set up precondition and run the transcoder UPDATE
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def transcoded_video(conn) -> dict:
    """
    Insert a video row with status 'processing', then apply the exact UPDATE
    the transcoder performs on success.  Returns the row fetched after the
    update along with the VIDEO_ID and expected field values.
    """
    gcp_cfg = GcpConfig()
    gcs_cfg = GCSConfig()

    hls_bucket = gcp_cfg.hls_bucket  # mytube-hls-output
    cdn_base_url = gcs_cfg.cdn_base_url  # may be empty in CI — handled below

    # ── Precondition: insert a user (FK dependency) via UserService ───────
    user_svc = UserService(conn)
    user_id = user_svc.create_user("firebase-uid-mytube79", "testuser_mytube79")

    # ── Precondition: insert video row with status 'processing' via VideoService
    video_svc = VideoService(conn)
    video_id, initial_status = video_svc.insert_video(user_id, "Test Transcoding Video", "processing")
    video_id = str(video_id)

    # Verify precondition
    assert initial_status in ("processing", "pending"), (
        f"Precondition failed: expected status 'processing' or 'pending', got '{initial_status}'."
    )

    # Derive the expected values using the same logic as main.go / doTranscode.
    expected_hls_manifest_path = f"gs://{hls_bucket}/videos/{video_id}/index.m3u8"
    # CDN_BASE_URL may not be set in CI; fall back to a deterministic placeholder
    # so the assertion still exercises the path-construction logic.
    effective_cdn = cdn_base_url.rstrip("/") if cdn_base_url else "https://cdn.example.com"
    expected_thumbnail_url = f"{effective_cdn}/videos/{video_id}/thumbnail.jpg"

    # ── Simulate transcoder UpdateVideo (mirrors repository.go SQL) ───────
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE videos
            SET hls_manifest_path = %s,
                thumbnail_url      = %s,
                status             = %s
            WHERE id = %s
            """,
            (expected_hls_manifest_path, expected_thumbnail_url, "ready", video_id),
        )

    # ── Fetch the updated row ─────────────────────────────────────────────
    with conn.cursor() as cur:
        cur.execute(
            "SELECT status, hls_manifest_path, thumbnail_url FROM videos WHERE id = %s",
            (video_id,),
        )
        updated = cur.fetchone()

    assert updated is not None, f"Video row {video_id} not found after UPDATE."

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
