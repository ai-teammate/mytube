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

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.schema_service import SchemaService

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)

MIGRATION_01_UP = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")
MIGRATION_SEARCH_UP = os.path.join(_MIGRATIONS_DIR, "0003_search_indexes.up.sql")
MIGRATION_SEARCH_DOWN = os.path.join(_MIGRATIONS_DIR, "0003_search_indexes.down.sql")

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
def schema(db_config: DBConfig) -> SchemaService:
    """
    Instantiate SchemaService from DBConfig, drop all public tables for a clean
    slate, apply the precondition migration (0001), then apply the search-indexes
    migration under test (0003). Yields the SchemaService; closes it on teardown.
    """
    svc = SchemaService(db_config)
    svc.drop_all_public_tables()
    svc.apply_sql_file(MIGRATION_01_UP)
    svc.apply_sql_file(MIGRATION_SEARCH_UP)
    yield svc
    svc.close()


@pytest.fixture(scope="class")
def schema_after_down(db_config: DBConfig) -> SchemaService:
    """
    Instantiate a fresh SchemaService and apply the down migration to verify
    index removal. Yields the SchemaService; closes it on teardown.
    """
    svc = SchemaService(db_config)
    svc.apply_sql_file(MIGRATION_SEARCH_DOWN)
    yield svc
    svc.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchIndexesCreated:
    """After applying 0003_search_indexes.up.sql all four indexes must exist."""

    @pytest.mark.parametrize("index_name,table_name,access_method", EXPECTED_INDEXES)
    def test_index_exists(self, schema: SchemaService, index_name: str, table_name: str, access_method: str):
        """Each expected index must be present in pg_indexes for the correct table."""
        assert schema.index_exists(index_name, table_name), (
            f"Index '{index_name}' not found in pg_indexes for table '{table_name}'. "
            f"Migration 0003_search_indexes.up.sql may not have been applied."
        )

    @pytest.mark.parametrize("index_name,table_name,access_method", EXPECTED_INDEXES)
    def test_index_access_method(self, schema: SchemaService, index_name: str, table_name: str, access_method: str):
        """Each index must use the correct access method (GIN or B-tree)."""
        actual_am = schema.index_access_method(index_name)
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

    def test_all_four_indexes_present(self, schema: SchemaService):
        """All four expected search/discovery indexes must be present."""
        missing = [
            name for name in self.MIGRATION_INDEX_NAMES
            if not schema.index_exists(name)
        ]
        assert not missing, (
            f"The following indexes are missing after migration: {sorted(missing)}"
        )


class TestDownMigration:
    """Running the down migration must remove all four search indexes."""

    def test_down_migration_removes_indexes(self, schema_after_down: SchemaService):
        """
        After applying 0003_search_indexes.down.sql verify none of the four
        indexes remain.
        """
        for index_name, _, _ in EXPECTED_INDEXES:
            assert not schema_after_down.index_exists(index_name), (
                f"Down migration did not remove index: {index_name}"
            )
