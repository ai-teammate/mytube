"""
MYTUBE-68: Verify sorting and tag indexes — indexes utilized for discovery and filtering.

Verifies that the composite indexes on status/recency/popularity and the tag index
are actually selected by the PostgreSQL query planner for their respective discovery
queries:

  - videos_status_created  →  SELECT … WHERE status = ? ORDER BY created_at DESC
  - videos_status_views    →  SELECT … WHERE status = ? ORDER BY view_count DESC
  - video_tags_tag_idx     →  SELECT … FROM video_tags WHERE tag = ?

The test applies migrations 0001 (schema) and 0003 (search indexes), inserts enough
rows to give the planner useful statistics, then inspects EXPLAIN output to confirm
each index is selected.

For the composite indexes on the videos table the planner will choose a sequential
scan on small datasets because random I/O is more expensive than sequential I/O.
This is correct planner behaviour.  To verify that each index is *structurally
eligible* for its query (i.e. the planner would use it on a larger dataset), the
tests temporarily disable sequential scans via ``SET enable_seqscan = off`` for the
duration of the EXPLAIN call.  This is the standard PostgreSQL technique for
confirming index applicability.
"""
import os
import sys
import uuid

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.schema_service import SchemaService

# ---------------------------------------------------------------------------
# Migration paths
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)

MIGRATION_SCHEMA = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")
MIGRATION_INDEXES = os.path.join(_MIGRATIONS_DIR, "0003_search_indexes.up.sql")

# Number of rows to insert so the planner has meaningful statistics.
_ROW_COUNT = 500


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """
    Open a connection, rebuild the schema from scratch with both migrations,
    seed rows, yield the connection, then close.
    """
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    svc = SchemaService(connection)
    svc.drop_all_public_tables()
    svc.apply_sql_file(MIGRATION_SCHEMA)
    svc.apply_sql_file(MIGRATION_INDEXES)

    # Seed a user to satisfy the FK on videos.uploader_id.
    user_id = str(uuid.uuid4())
    with connection.cursor() as cur:
        cur.execute(
            "INSERT INTO users (id, firebase_uid, username) VALUES (%s, %s, %s)",
            (user_id, "firebase-uid-68", "testuser68"),
        )

    # Insert video rows (mix of 'ready' and 'pending') for planner statistics.
    with connection.cursor() as cur:
        for i in range(_ROW_COUNT):
            status = "ready" if i % 5 != 0 else "pending"
            cur.execute(
                """
                INSERT INTO videos (id, uploader_id, title, status, view_count)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (str(uuid.uuid4()), user_id, f"Video title {i}", status, i * 10),
            )

    # Insert video_tag rows for the tag index to be exercised.
    with connection.cursor() as cur:
        for i in range(_ROW_COUNT):
            video_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT INTO videos (id, uploader_id, title, status)
                VALUES (%s, %s, %s, 'ready')
                """,
                (video_id, user_id, f"Tagged video {i}"),
            )
            tag = "python" if i % 10 == 0 else f"tag_{i}"
            cur.execute(
                "INSERT INTO video_tags (video_id, tag) VALUES (%s, %s)",
                (video_id, tag),
            )

    # Update planner statistics so EXPLAIN reflects the seeded data.
    with connection.cursor() as cur:
        cur.execute("ANALYZE videos;")
        cur.execute("ANALYZE video_tags;")

    yield connection

    connection.close()


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _explain_with_index_scan(connection, query: str, params: tuple) -> str:
    """
    Return EXPLAIN (FORMAT TEXT) output with sequential scans disabled so that
    the planner is forced to consider index paths.  This is the standard
    PostgreSQL technique for verifying index applicability.

    The ``enable_seqscan`` session parameter is restored to ``on`` after the
    EXPLAIN call so other queries in the session are not affected.
    """
    with connection.cursor() as cur:
        cur.execute("SET enable_seqscan = off;")
        cur.execute(f"EXPLAIN (FORMAT TEXT) {query}", params)
        rows = cur.fetchall()
        cur.execute("SET enable_seqscan = on;")
    return "\n".join(row[0] for row in rows)


def _explain_default(connection, query: str, params: tuple) -> str:
    """Return EXPLAIN (FORMAT TEXT) output with default planner settings."""
    with connection.cursor() as cur:
        cur.execute(f"EXPLAIN (FORMAT TEXT) {query}", params)
        rows = cur.fetchall()
    return "\n".join(row[0] for row in rows)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSortingAndTagIndexes:
    """
    Composite and tag indexes must be selected by the planner for their
    respective discovery queries.
    """

    def test_status_created_index_used_for_recency_query(self, conn):
        """
        The index 'videos_status_created' must be chosen for the
        status+created_at recency query when sequential scans are disabled.

        With small datasets the planner correctly prefers seq-scan; disabling
        seq-scan confirms the index is structurally eligible and will be used
        on production-scale data.
        """
        plan = _explain_with_index_scan(
            conn,
            "SELECT id, title, created_at FROM videos WHERE status = %s ORDER BY created_at DESC",
            ("ready",),
        )
        assert "videos_status_created" in plan, (
            "Expected index 'videos_status_created' in EXPLAIN plan for "
            f"status+created_at query.\nActual plan:\n{plan}"
        )

    def test_status_views_index_used_for_popularity_query(self, conn):
        """
        The index 'videos_status_views' must be chosen for the
        status+view_count popularity query when sequential scans are disabled.
        """
        plan = _explain_with_index_scan(
            conn,
            "SELECT id, title, view_count FROM videos WHERE status = %s ORDER BY view_count DESC",
            ("ready",),
        )
        assert "videos_status_views" in plan, (
            "Expected index 'videos_status_views' in EXPLAIN plan for "
            f"status+view_count query.\nActual plan:\n{plan}"
        )

    def test_tag_index_used_for_tag_filter_query(self, conn):
        """
        The index 'video_tags_tag_idx' must be chosen for a tag equality filter
        query.  The tag table is small enough that the planner may or may not
        use it by default; seq-scan is disabled to confirm eligibility.
        """
        plan = _explain_with_index_scan(
            conn,
            "SELECT video_id FROM video_tags WHERE tag = %s",
            ("python",),
        )
        assert "video_tags_tag_idx" in plan, (
            "Expected index 'video_tags_tag_idx' in EXPLAIN plan for "
            f"tag filter query.\nActual plan:\n{plan}"
        )
