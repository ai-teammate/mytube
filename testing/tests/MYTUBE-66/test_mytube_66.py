"""
MYTUBE-66: Execute search index migration — search and discovery indexes
created successfully.

Verifies that migration 0003_search_indexes.up.sql correctly creates all
required full-text search, tag, and performance indexes on the database tables.

Test strategy
-------------
1. Start from a clean database and apply the initial schema migration (0001).
2. Apply migration 0003_search_indexes.up.sql (the 'up' command for
   search/discovery indexes).
3. Query PostgreSQL's pg_indexes system table for tables 'videos' and
   'video_tags'.
4. Assert all four expected indexes are present with the correct access methods:
   - videos_title_fts     (GIN)
   - video_tags_tag_idx   (B-tree)
   - videos_status_created (B-tree)
   - videos_status_views  (B-tree)

Note: The ticket refers to this migration as '0002_search_indexes'. In the
repository it is numbered 0003_search_indexes.up.sql. The test targets the
actual file on disk.
"""

import os
import sys

import psycopg2
import psycopg2.extras
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)

MIGRATION_01_UP = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")
MIGRATION_SEARCH_UP = os.path.join(_MIGRATIONS_DIR, "0003_search_indexes.up.sql")

# ---------------------------------------------------------------------------
# Expected indexes
# ---------------------------------------------------------------------------

# Each entry: (index_name, table_name, expected_access_method)
EXPECTED_INDEXES = [
    ("videos_title_fts", "videos", "gin"),
    ("video_tags_tag_idx", "video_tags", "btree"),
    ("videos_status_created", "videos", "btree"),
    ("videos_status_views", "videos", "btree"),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """
    Open a connection, drop all public tables, apply migration 0001, then
    apply the search-indexes migration.  Yields the connection; closes it on
    teardown.
    """
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    # --- Clean slate ---
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

    # --- Apply precondition migration: 0001_initial_schema ---
    with open(MIGRATION_01_UP, "r") as fh:
        sql_01 = fh.read()
    with connection.cursor() as cur:
        cur.execute(sql_01)

    # --- Apply the migration under test: 0003_search_indexes ---
    with open(MIGRATION_SEARCH_UP, "r") as fh:
        sql_search = fh.read()
    with connection.cursor() as cur:
        cur.execute(sql_search)

    yield connection

    connection.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_index_info(conn, index_name: str) -> dict | None:
    """
    Query pg_indexes for the given index name.
    Returns a dict with keys: indexname, tablename, indexdef — or None if not found.
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            """
            SELECT indexname, tablename, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
              AND indexname = %s
            """,
            (index_name,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def _get_access_method(conn, index_name: str) -> str | None:
    """
    Return the lowercase access method (e.g. 'gin', 'btree') for the index,
    or None if not found.  Uses pg_am joined through pg_class / pg_index.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT am.amname
            FROM pg_index     idx
            JOIN pg_class     ci  ON ci.oid  = idx.indexrelid
            JOIN pg_am        am  ON am.oid  = ci.relam
            JOIN pg_namespace ns  ON ns.oid  = ci.relnamespace
            WHERE ns.nspname = 'public'
              AND ci.relname = %s
            """,
            (index_name,),
        )
        row = cur.fetchone()
        return row[0].lower() if row else None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchIndexesCreated:
    """After applying 0003_search_indexes.up.sql all four indexes must exist."""

    @pytest.mark.parametrize("index_name,table_name,access_method", EXPECTED_INDEXES)
    def test_index_exists(self, conn, index_name: str, table_name: str, access_method: str):
        """Each expected index must be present in pg_indexes for the correct table."""
        info = _get_index_info(conn, index_name)
        assert info is not None, (
            f"Index '{index_name}' not found in pg_indexes for table '{table_name}'. "
            f"Migration 0003_search_indexes.up.sql may not have been applied."
        )
        assert info["tablename"] == table_name, (
            f"Index '{index_name}' is on table '{info['tablename']}', "
            f"expected '{table_name}'."
        )

    @pytest.mark.parametrize("index_name,table_name,access_method", EXPECTED_INDEXES)
    def test_index_access_method(self, conn, index_name: str, table_name: str, access_method: str):
        """Each index must use the correct access method (GIN or B-tree)."""
        actual_am = _get_access_method(conn, index_name)
        assert actual_am is not None, (
            f"Could not determine access method for index '{index_name}'."
        )
        assert actual_am == access_method, (
            f"Index '{index_name}' uses access method '{actual_am}', "
            f"expected '{access_method}'."
        )


class TestSearchIndexesCount:
    """Exactly four new indexes must be created by the migration on videos and video_tags."""

    MIGRATION_INDEX_NAMES = {row[0] for row in EXPECTED_INDEXES}

    def test_all_four_indexes_present(self, conn):
        """All four expected search/discovery indexes must be present."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename IN ('videos', 'video_tags')
                  AND indexname = ANY(%s)
                """,
                (list(self.MIGRATION_INDEX_NAMES),),
            )
            found = {row[0] for row in cur.fetchall()}

        missing = self.MIGRATION_INDEX_NAMES - found
        assert not missing, (
            f"The following indexes are missing after migration: {sorted(missing)}"
        )


class TestDownMigration:
    """Running the down migration must remove all four search indexes."""

    MIGRATION_SEARCH_DOWN = os.path.join(_MIGRATIONS_DIR, "0003_search_indexes.down.sql")

    def test_down_migration_removes_indexes(self, db_config: DBConfig):
        """
        Apply 0003_search_indexes.down.sql on a separate connection and
        verify none of the four indexes remain.
        """
        probe = psycopg2.connect(db_config.dsn())
        probe.autocommit = True
        try:
            # Apply down migration
            with open(self.MIGRATION_SEARCH_DOWN, "r") as fh:
                sql_down = fh.read()
            with probe.cursor() as cur:
                cur.execute(sql_down)

            # Verify indexes are gone
            with probe.cursor() as cur:
                probe_index_names = [row[0] for row in EXPECTED_INDEXES]
                cur.execute(
                    """
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = 'public'
                      AND indexname = ANY(%s)
                    """,
                    (probe_index_names,),
                )
                remaining = [row[0] for row in cur.fetchall()]

            assert not remaining, (
                f"Down migration did not remove indexes: {remaining}"
            )
        finally:
            probe.close()
