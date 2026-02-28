"""
MYTUBE-35: Validate rating stars field — database rejects stars values outside 1-5 range.

Verifies that the CHECK constraint on the 'ratings' table restricts the 'stars'
column to values between 1 and 5 (inclusive).

Steps:
  1. Attempt to insert a record with stars = 0  → must fail (CHECK violation).
  2. Attempt to insert a record with stars = 6  → must fail (CHECK violation).
  3. Attempt to insert a record with stars = 5  → must succeed.
"""
import os
import sys
import uuid

import psycopg2
import psycopg2.errors
import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig

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
    """
    Open a connection, apply the initial schema migration on a clean database,
    insert the minimum prerequisite rows (one user, one video), yield the
    connection, then clean up.
    """
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    # Start from a clean slate.
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

    # Apply the migration.
    with open(MIGRATION_SQL, "r") as fh:
        migration_sql = fh.read()
    with connection.cursor() as cur:
        cur.execute(migration_sql)

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def prerequisite_ids(conn):
    """
    Insert one user and one video so that ratings FK constraints are satisfied.
    Returns (user_id, video_id) as UUID strings.
    """
    user_id = str(uuid.uuid4())
    video_id = str(uuid.uuid4())

    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (id, firebase_uid, username)
            VALUES (%s, %s, %s)
            """,
            (user_id, "uid_test_35", "testuser35"),
        )
        cur.execute(
            """
            INSERT INTO videos (id, uploader_id, title, status)
            VALUES (%s, %s, %s, 'ready')
            """,
            (video_id, user_id, "Test Video 35"),
        )

    return user_id, video_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRatingsStarsConstraint:
    """CHECK (stars BETWEEN 1 AND 5) on the ratings table."""

    def test_stars_zero_rejected(self, conn, prerequisite_ids):
        """Inserting stars = 0 must raise a CHECK constraint violation."""
        user_id, video_id = prerequisite_ids
        with pytest.raises(psycopg2.errors.CheckViolation):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ratings (video_id, user_id, stars) VALUES (%s, %s, %s)",
                    (video_id, user_id, 0),
                )

    def test_stars_six_rejected(self, conn, prerequisite_ids):
        """Inserting stars = 6 must raise a CHECK constraint violation."""
        user_id, video_id = prerequisite_ids
        # The connection may be in an aborted state after the previous failure;
        # roll back before attempting the next statement.
        conn.rollback()
        with pytest.raises(psycopg2.errors.CheckViolation):
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO ratings (video_id, user_id, stars) VALUES (%s, %s, %s)",
                    (video_id, user_id, 6),
                )

    def test_stars_five_accepted(self, conn, prerequisite_ids):
        """Inserting stars = 5 must succeed."""
        user_id, video_id = prerequisite_ids
        # Ensure connection is clean after previous failed transactions.
        conn.rollback()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ratings (video_id, user_id, stars) VALUES (%s, %s, %s)",
                (video_id, user_id, 5),
            )
        # Verify the row was actually stored.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT stars FROM ratings WHERE video_id = %s AND user_id = %s",
                (video_id, user_id),
            )
            row = cur.fetchone()
        assert row is not None, "Rating row not found after successful insert"
        assert row[0] == 5, f"Expected stars = 5, got {row[0]}"
