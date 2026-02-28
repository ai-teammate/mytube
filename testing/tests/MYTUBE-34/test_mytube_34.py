"""
MYTUBE-34: Validate video status field — database rejects status values not
in the defined list.

Verifies that the CHECK constraint on videos.status correctly:
 - Rejects INSERT of a row with status = 'archived' (not in allowed list).
 - Accepts INSERT of a row with status = 'pending' (in allowed list).

Allowed values defined in the migration:
    CHECK (status IN ('pending','processing','ready','failed'))
"""
import os
import sys
import pytest
import psycopg2
import psycopg2.errors

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.video_service import VideoService

MIGRATION_SQL = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "api",
    "migrations",
    "0001_initial_schema.up.sql",
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """Connect, apply a clean migration, yield the connection, then tear down."""
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    # Drop all tables to guarantee a clean slate.
    with connection.cursor() as cur:
        cur.execute(
            """
            DO $$ DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
            """
        )
        cur.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE;")

    with open(MIGRATION_SQL, "r") as f:
        migration_sql = f.read()
    with connection.cursor() as cur:
        cur.execute(migration_sql)

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def video_service(conn) -> VideoService:
    return VideoService(conn)


@pytest.fixture(scope="module")
def uploader_id(conn) -> str:
    """Insert a single user and return its id for use as uploader_id."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) RETURNING id",
            ("test-firebase-uid-34", "testuser34"),
        )
        return str(cur.fetchone()[0])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVideoStatusCheckConstraint:
    """videos.status CHECK constraint must enforce the allowed-values list."""

    def test_invalid_status_archived_is_rejected(self, video_service: VideoService, uploader_id: str):
        """INSERT with status='archived' must raise a check-constraint violation."""
        with pytest.raises(psycopg2.errors.CheckViolation) as exc_info:
            video_service.insert_video(uploader_id, "Test video – invalid status", "archived")
        assert "check" in str(exc_info.value).lower() or "violates" in str(exc_info.value).lower(), (
            f"Expected a CHECK constraint violation, got: {exc_info.value}"
        )

    def test_valid_status_pending_is_accepted(self, video_service: VideoService, uploader_id: str):
        """INSERT with status='pending' must succeed."""
        row = video_service.insert_video(uploader_id, "Test video – valid status", "pending")
        assert row is not None, "INSERT with status='pending' returned no row"
        assert row[1] == "pending", (
            f"Expected returned status 'pending', got '{row[1]}'"
        )
