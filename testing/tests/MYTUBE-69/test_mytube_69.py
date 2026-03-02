"""
MYTUBE-69: Execute search migration twice — IF NOT EXISTS logic prevents SQL exceptions.

Verifies the idempotency of 0003_search_indexes.up.sql by ensuring that
CREATE INDEX IF NOT EXISTS clauses allow the migration to be applied more than
once without raising "index already exists" errors, and that all four indexes
remain intact after the second application.
"""
import os
import sys
import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.schema_service import SchemaService

# conn and db_config fixtures are provided by testing/tests/conftest.py.
# The conftest conn fixture applies 0001_initial_schema.up.sql on a clean DB,
# giving us a ready base schema to build on.

SEARCH_INDEXES_SQL = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "api",
    "migrations",
    "0003_search_indexes.up.sql",
)

EXPECTED_INDEXES = [
    "videos_title_fts",
    "video_tags_tag_idx",
    "videos_status_created",
    "videos_status_views",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def schema(conn) -> SchemaService:
    """SchemaService wrapping the module-scoped connection."""
    return SchemaService(conn)


@pytest.fixture(scope="module")
def indexes_applied_twice(conn, schema):
    """
    Apply 0003_search_indexes.up.sql twice in succession.

    The first call creates the indexes; the second call must not raise any
    exception because every statement uses CREATE INDEX IF NOT EXISTS.
    If either execution raises an exception the fixture re-raises it so the
    depending tests fail with a meaningful error.
    """
    schema.apply_sql_file(SEARCH_INDEXES_SQL)   # first application
    schema.apply_sql_file(SEARCH_INDEXES_SQL)   # second application — must be silent
    return True                                  # signals success to tests


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchMigrationIdempotency:
    """Applying 0003_search_indexes.up.sql twice must succeed without errors."""

    def test_first_and_second_application_raise_no_exception(
        self, indexes_applied_twice
    ):
        """The fixture itself fails if either SQL execution raises an exception."""
        assert indexes_applied_twice is True, (
            "Migration could not be applied twice without errors."
        )


class TestSearchIndexesExistAfterDoubleApplication:
    """All four search indexes must be present after two migration runs."""

    @pytest.mark.parametrize("index_name", EXPECTED_INDEXES)
    def test_index_exists(self, schema: SchemaService, indexes_applied_twice, index_name: str):
        assert schema.index_exists(index_name), (
            f"Index '{index_name}' is missing after double migration application."
        )


class TestSearchIndexProperties:
    """Spot-check key properties of the created indexes."""

    def test_videos_title_fts_is_gin(self, schema: SchemaService, indexes_applied_twice):
        """videos_title_fts must be a GIN index (used for full-text search)."""
        assert schema.get_index_access_method("videos_title_fts") == "gin", (
            f"Expected 'videos_title_fts' to be GIN, "
            f"got '{schema.get_index_access_method('videos_title_fts')}'."
        )

    def test_video_tags_tag_idx_is_btree(self, schema: SchemaService, indexes_applied_twice):
        """video_tags_tag_idx must be a B-tree index."""
        assert schema.get_index_access_method("video_tags_tag_idx") == "btree", (
            f"Expected 'video_tags_tag_idx' to be btree, "
            f"got '{schema.get_index_access_method('video_tags_tag_idx')}'."
        )

    def test_videos_status_created_is_btree(self, schema: SchemaService, indexes_applied_twice):
        """videos_status_created must be a B-tree composite index."""
        assert schema.get_index_access_method("videos_status_created") == "btree", (
            f"Expected 'videos_status_created' to be btree, "
            f"got '{schema.get_index_access_method('videos_status_created')}'."
        )

    def test_videos_status_views_is_btree(self, schema: SchemaService, indexes_applied_twice):
        """videos_status_views must be a B-tree composite index."""
        assert schema.get_index_access_method("videos_status_views") == "btree", (
            f"Expected 'videos_status_views' to be btree, "
            f"got '{schema.get_index_access_method('videos_status_views')}'."
        )
