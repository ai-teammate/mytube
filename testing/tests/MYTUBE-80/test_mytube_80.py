"""
MYTUBE-80: Handle transcoding failure — database status set to failed
and job exits with non-zero code.

Objective:
    Verify that when the Cloud Run transcoder job encounters a processing
    failure (e.g. corrupted file or FFmpeg error), it:
      1. Sets videos.status = 'failed' for the corresponding VIDEO_ID row.
      2. Exits with a non-zero exit code so Cloud Run retries / marks the
         task as failed.

Test strategy — two layers:

  Layer A — Go unit tests (subprocess):
    Run the existing Go tests in api/cmd/transcoder/main_test.go that
    exercise the failure path with stub dependencies:
      - TestTranscode_DownloadError_MarksVideoFailed
      - TestTranscode_TranscodeHLSError_MarksVideoFailed
      - TestTranscode_UpdateVideoError_MarksVideoFailed
      - TestTranscode_DownloadError_ReturnsError
      - TestTranscode_TranscodeHLSError_ReturnsError
      - TestTranscode_ThumbnailError_ReturnsError
    These tests confirm:
      * repo.MarkFailed() is called on any pipeline error.
      * transcode() returns a non-nil error (which causes main() to call
        os.Exit(1), producing a non-zero exit code for the Cloud Run job).

  Layer B — Database integration test (psycopg2):
    Connect to a real PostgreSQL database, set up the schema, insert a
    video row with status = 'processing', then apply the exact SQL UPDATE
    performed by video.Repository.MarkFailed():
        UPDATE videos SET status = 'failed' WHERE id = ?
    Then assert that the row status reads 'failed'.
    This confirms the DB contract at the SQL level, independent of Go code.

Architecture:
    - Python orchestrates both layers via pytest.
    - Go layer uses subprocess to call `go test`.
    - DB layer uses psycopg2 with DBConfig from core/config.
    - Migrations from api/migrations/ are applied to a clean test database.
"""

import os
import subprocess
import sys
import uuid

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.schema_service import SchemaService

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")
_TRANSCODER_PKG = "./cmd/transcoder"

_MIGRATIONS_DIR = os.path.join(_API_DIR, "migrations")
_MIGRATION_SCHEMA = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")


# ---------------------------------------------------------------------------
# DB fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """Open a fresh connection and rebuild the schema for this test module."""
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    svc = SchemaService(connection)
    svc.drop_all_public_tables()
    svc.apply_sql_file(_MIGRATION_SCHEMA)

    yield connection

    connection.close()


# ---------------------------------------------------------------------------
# Layer A — Go unit tests
# ---------------------------------------------------------------------------


class TestTranscodingFailureExitCode:
    """
    The transcoder function must return a non-nil error on any pipeline
    failure, which causes main() to call os.Exit(1) — a non-zero exit code.

    These tests run the existing Go unit tests from main_test.go via
    `go test -run <name>` and assert zero exit code from the go toolchain
    (meaning the Go test passed — not a test failure).
    """

    def test_transcoder_package_compiles(self):
        """The transcoder package must compile cleanly before running tests."""
        result = subprocess.run(
            ["go", "build", _TRANSCODER_PKG],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"go build {_TRANSCODER_PKG} failed.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

    def test_download_error_returns_non_nil_error(self):
        """
        When the downloader fails, transcode() must return a non-nil error.
        A non-nil error propagates to main() which calls os.Exit(1).
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_DownloadError_ReturnsError",
                _TRANSCODER_PKG,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_DownloadError_ReturnsError FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_ffmpeg_error_returns_non_nil_error(self):
        """
        When FFmpeg (HLS transcoding) fails, transcode() must return a
        non-nil error, ensuring a non-zero exit code from the job.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_TranscodeHLSError_ReturnsError",
                _TRANSCODER_PKG,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_TranscodeHLSError_ReturnsError FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_thumbnail_error_returns_non_nil_error(self):
        """
        When thumbnail extraction fails, transcode() returns a non-nil error.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_ThumbnailError_ReturnsError",
                _TRANSCODER_PKG,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_ThumbnailError_ReturnsError FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout


class TestTranscodingFailureMarksDBFailed:
    """
    On any pipeline failure, MarkFailed must be called so the database
    row transitions to status = 'failed'.
    """

    def test_download_failure_calls_mark_failed(self):
        """
        A download error (e.g. corrupted/missing file in GCS) must trigger
        a MarkFailed call on the video repository.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_DownloadError_MarksVideoFailed",
                _TRANSCODER_PKG,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_DownloadError_MarksVideoFailed FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_ffmpeg_failure_calls_mark_failed(self):
        """
        An FFmpeg / HLS transcoding error must trigger a MarkFailed call,
        ensuring the DB status transitions to 'failed'.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_TranscodeHLSError_MarksVideoFailed",
                _TRANSCODER_PKG,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_TranscodeHLSError_MarksVideoFailed FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_db_update_failure_calls_mark_failed(self):
        """
        Even when the final DB update step fails, MarkFailed is still
        invoked — ensuring the status is always written as 'failed'.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_UpdateVideoError_MarksVideoFailed",
                _TRANSCODER_PKG,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"TestTranscode_UpdateVideoError_MarksVideoFailed FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_full_failure_test_suite_passes(self):
        """
        All failure-path Go tests in main_test.go must pass as a collective
        gate for the transcoding failure handling contract.
        """
        result = subprocess.run(
            [
                "go", "test", "-v", "-count=1",
                "-run", "TestTranscode_(Download|TranscodeHLS|Thumbnail|UploadDir|UploadFile|UpdateVideo)Error",
                _TRANSCODER_PKG,
            ],
            cwd=_API_DIR,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Transcoder failure-path test suite FAILED.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        pass_count = result.stdout.count("--- PASS")
        assert pass_count >= 6, (
            f"Expected at least 6 failure-path tests to pass, got {pass_count}.\n"
            f"STDOUT:\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# Layer B — Database integration
# ---------------------------------------------------------------------------


class TestMarkFailedSQLContract:
    """
    Verifies the exact SQL UPDATE used by video.Repository.MarkFailed at
    the database level.

    Inserts a video row with status 'processing', executes the MarkFailed
    UPDATE directly, and asserts the status becomes 'failed'.
    """

    def test_mark_failed_sets_status_to_failed(self, conn):
        """
        The MarkFailed SQL update must change videos.status from any prior
        value to 'failed' for the given VIDEO_ID.
        """
        # Insert a user to satisfy the FK constraint on videos.uploader_id.
        user_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, firebase_uid, username) VALUES (%s, %s, %s)",
                (user_id, f"firebase_uid_mytube80_{user_id[:8]}", "testuser_mytube80"),
            )

        # Insert a video row with status = 'processing' (simulates a job in flight).
        video_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO videos (id, uploader_id, title, status)
                VALUES (%s, %s, %s, 'processing')
                """,
                (video_id, user_id, "Corrupted Upload Test Video"),
            )

        # Verify precondition: status is 'processing'.
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM videos WHERE id = %s", (video_id,))
            row = cur.fetchone()
        assert row is not None, f"Pre-condition: video {video_id} not found in DB."
        assert row[0] == "processing", (
            f"Pre-condition: expected status 'processing', got '{row[0]}'."
        )

        # Execute the exact MarkFailed SQL from video/repository.go.
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE videos SET status = $1 WHERE id = $2",
                ("failed", video_id),
            )

        # Assert: status must now be 'failed'.
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM videos WHERE id = %s", (video_id,))
            row = cur.fetchone()
        assert row is not None, f"Video {video_id} not found after MarkFailed update."
        assert row[0] == "failed", (
            f"Expected status 'failed' after MarkFailed, got '{row[0]}'."
        )

    def test_failed_status_accepted_by_check_constraint(self, conn):
        """
        The 'failed' value must be accepted by the status CHECK constraint
        (status IN ('pending','processing','ready','failed')).

        A constraint violation would raise an IntegrityError; no exception
        means the value is valid.
        """
        user_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, firebase_uid, username) VALUES (%s, %s, %s)",
                (user_id, f"firebase_uid_check_{user_id[:8]}", "testuser_check_mytube80"),
            )

        video_id = str(uuid.uuid4())
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO videos (id, uploader_id, title, status)
                    VALUES (%s, %s, %s, 'failed')
                    """,
                    (video_id, user_id, "Check Constraint Test Video"),
                )
        except psycopg2.errors.CheckViolation as exc:
            pytest.fail(
                f"CHECK constraint rejected status='failed': {exc}. "
                "The 'failed' status must be in the allowed values list."
            )

        with conn.cursor() as cur:
            cur.execute("SELECT status FROM videos WHERE id = %s", (video_id,))
            row = cur.fetchone()
        assert row is not None
        assert row[0] == "failed"

    def test_mark_failed_does_not_affect_other_rows(self, conn):
        """
        MarkFailed must only update the targeted VIDEO_ID row.
        Other rows must remain unchanged.
        """
        user_id = str(uuid.uuid4())
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (id, firebase_uid, username) VALUES (%s, %s, %s)",
                (user_id, f"firebase_uid_iso_{user_id[:8]}", "testuser_iso_mytube80"),
            )

        # Target video to fail.
        target_id = str(uuid.uuid4())
        # Sibling video that must remain untouched.
        sibling_id = str(uuid.uuid4())

        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO videos (id, uploader_id, title, status) VALUES (%s, %s, %s, 'processing')",
                (target_id, user_id, "Target Video"),
            )
            cur.execute(
                "INSERT INTO videos (id, uploader_id, title, status) VALUES (%s, %s, %s, 'ready')",
                (sibling_id, user_id, "Sibling Video"),
            )

        # Apply MarkFailed only to target.
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE videos SET status = $1 WHERE id = $2",
                ("failed", target_id),
            )

        # Target must be 'failed'.
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM videos WHERE id = %s", (target_id,))
            assert cur.fetchone()[0] == "failed"

        # Sibling must remain 'ready'.
        with conn.cursor() as cur:
            cur.execute("SELECT status FROM videos WHERE id = %s", (sibling_id,))
            assert cur.fetchone()[0] == "ready", (
                "MarkFailed must not affect sibling rows."
            )
