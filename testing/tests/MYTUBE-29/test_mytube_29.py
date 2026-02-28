"""
MYTUBE-29: Execute initial schema migration — core tables created with correct
data types and constraints.

Verifies that running 0001_initial_schema.up.sql against a clean PostgreSQL
database produces all 8 required tables with the correct columns, types,
primary keys, foreign keys, and default values.
"""
import os
import sys
import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.schema_service import SchemaService

# conn and db_config fixtures are provided by testing/tests/conftest.py

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REQUIRED_TABLES = [
    "users",
    "videos",
    "categories",
    "video_tags",
    "playlists",
    "playlist_videos",
    "comments",
    "ratings",
]


@pytest.fixture(scope="module")
def schema(conn) -> SchemaService:
    return SchemaService(conn)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAllTablesExist:
    """All 8 required tables must be present after migration."""

    @pytest.mark.parametrize("table_name", REQUIRED_TABLES)
    def test_table_exists(self, schema: SchemaService, table_name: str):
        assert schema.table_exists(table_name), (
            f"Table '{table_name}' does not exist after migration."
        )


class TestUsersTable:
    """users table structure."""

    def test_id_is_uuid(self, schema: SchemaService):
        col = schema.get_column("users", "id")
        assert col is not None, "Column 'id' missing from 'users'"
        assert col["udt_name"] == "uuid", (
            f"Expected users.id to be UUID, got {col['udt_name']}"
        )

    def test_id_is_primary_key(self, schema: SchemaService):
        pks = schema.get_primary_keys("users")
        assert "id" in pks, "users.id is not a primary key"

    def test_created_at_is_timestamptz(self, schema: SchemaService):
        col = schema.get_column("users", "created_at")
        assert col is not None, "Column 'created_at' missing from 'users'"
        assert col["udt_name"] == "timestamptz", (
            f"Expected users.created_at to be TIMESTAMPTZ, got {col['udt_name']}"
        )

    def test_created_at_default_now(self, schema: SchemaService):
        assert schema.column_default_contains("users", "created_at", "now"), (
            "users.created_at should have DEFAULT now()"
        )

    def test_firebase_uid_not_null_unique(self, schema: SchemaService):
        col = schema.get_column("users", "firebase_uid")
        assert col is not None, "Column 'firebase_uid' missing from 'users'"
        assert col["is_nullable"] == "NO", "users.firebase_uid must be NOT NULL"


class TestVideosTable:
    """videos table structure and FK."""

    def test_id_is_uuid_pk(self, schema: SchemaService):
        col = schema.get_column("videos", "id")
        assert col is not None
        assert col["udt_name"] == "uuid"
        assert "id" in schema.get_primary_keys("videos")

    def test_created_at_is_timestamptz_with_default(self, schema: SchemaService):
        col = schema.get_column("videos", "created_at")
        assert col is not None
        assert col["udt_name"] == "timestamptz"
        assert schema.column_default_contains("videos", "created_at", "now")

    def test_uploader_id_fk_to_users(self, schema: SchemaService):
        fks = schema.get_foreign_keys("videos")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "uploader_id" in fk_map, "videos.uploader_id FK not found"
        fk = fk_map["uploader_id"]
        assert fk["foreign_table"] == "users", (
            f"Expected FK target table 'users', got '{fk['foreign_table']}'"
        )
        assert fk["foreign_column"] == "id", (
            f"Expected FK target column 'id', got '{fk['foreign_column']}'"
        )

    def test_uploader_id_fk_on_delete_restrict(self, schema: SchemaService):
        fks = schema.get_foreign_keys("videos")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "uploader_id" in fk_map
        assert fk_map["uploader_id"]["on_delete"] == "RESTRICT", (
            "videos.uploader_id FK should be ON DELETE RESTRICT"
        )


class TestCategoriesTable:
    """categories table structure."""

    def test_id_is_serial_pk(self, schema: SchemaService):
        col = schema.get_column("categories", "id")
        assert col is not None
        # SERIAL resolves to integer at the column level.
        assert col["udt_name"] == "int4", (
            f"Expected categories.id to be integer (SERIAL), got {col['udt_name']}"
        )
        assert "id" in schema.get_primary_keys("categories")

    def test_name_not_null(self, schema: SchemaService):
        col = schema.get_column("categories", "name")
        assert col is not None
        assert col["is_nullable"] == "NO", "categories.name must be NOT NULL"


class TestVideoTagsTable:
    """video_tags table structure and FK."""

    def test_composite_pk(self, schema: SchemaService):
        pks = schema.get_primary_keys("video_tags")
        assert set(pks) == {"video_id", "tag"}, (
            f"Expected composite PK (video_id, tag), got {pks}"
        )

    def test_video_id_fk_to_videos(self, schema: SchemaService):
        fks = schema.get_foreign_keys("video_tags")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "video_id" in fk_map
        assert fk_map["video_id"]["foreign_table"] == "videos"
        assert fk_map["video_id"]["foreign_column"] == "id"


class TestPlaylistsTable:
    """playlists table structure and FK."""

    def test_id_is_uuid_pk(self, schema: SchemaService):
        col = schema.get_column("playlists", "id")
        assert col is not None
        assert col["udt_name"] == "uuid"
        assert "id" in schema.get_primary_keys("playlists")

    def test_owner_id_fk_to_users(self, schema: SchemaService):
        fks = schema.get_foreign_keys("playlists")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "owner_id" in fk_map
        assert fk_map["owner_id"]["foreign_table"] == "users"
        assert fk_map["owner_id"]["foreign_column"] == "id"

    def test_created_at_is_timestamptz_with_default(self, schema: SchemaService):
        col = schema.get_column("playlists", "created_at")
        assert col is not None
        assert col["udt_name"] == "timestamptz"
        assert schema.column_default_contains("playlists", "created_at", "now")


class TestPlaylistVideosTable:
    """playlist_videos table structure."""

    def test_composite_pk(self, schema: SchemaService):
        pks = schema.get_primary_keys("playlist_videos")
        assert set(pks) == {"playlist_id", "video_id"}, (
            f"Expected composite PK (playlist_id, video_id), got {pks}"
        )

    def test_playlist_id_fk_to_playlists(self, schema: SchemaService):
        fks = schema.get_foreign_keys("playlist_videos")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "playlist_id" in fk_map
        assert fk_map["playlist_id"]["foreign_table"] == "playlists"

    def test_video_id_fk_to_videos(self, schema: SchemaService):
        fks = schema.get_foreign_keys("playlist_videos")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "video_id" in fk_map
        assert fk_map["video_id"]["foreign_table"] == "videos"


class TestCommentsTable:
    """comments table structure and FKs."""

    def test_id_is_uuid_pk(self, schema: SchemaService):
        col = schema.get_column("comments", "id")
        assert col is not None
        assert col["udt_name"] == "uuid"
        assert "id" in schema.get_primary_keys("comments")

    def test_created_at_is_timestamptz_with_default(self, schema: SchemaService):
        col = schema.get_column("comments", "created_at")
        assert col is not None
        assert col["udt_name"] == "timestamptz"
        assert schema.column_default_contains("comments", "created_at", "now")

    def test_video_id_fk_to_videos(self, schema: SchemaService):
        fks = schema.get_foreign_keys("comments")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "video_id" in fk_map
        assert fk_map["video_id"]["foreign_table"] == "videos"

    def test_author_id_fk_to_users(self, schema: SchemaService):
        fks = schema.get_foreign_keys("comments")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "author_id" in fk_map
        assert fk_map["author_id"]["foreign_table"] == "users"
        assert fk_map["author_id"]["on_delete"] == "RESTRICT"


class TestRatingsTable:
    """ratings table structure and FKs."""

    def test_composite_pk(self, schema: SchemaService):
        pks = schema.get_primary_keys("ratings")
        assert set(pks) == {"video_id", "user_id"}, (
            f"Expected composite PK (video_id, user_id), got {pks}"
        )

    def test_video_id_fk_to_videos(self, schema: SchemaService):
        fks = schema.get_foreign_keys("ratings")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "video_id" in fk_map
        assert fk_map["video_id"]["foreign_table"] == "videos"

    def test_user_id_fk_to_users(self, schema: SchemaService):
        fks = schema.get_foreign_keys("ratings")
        fk_map = {fk["column_name"]: fk for fk in fks}
        assert "user_id" in fk_map
        assert fk_map["user_id"]["foreign_table"] == "users"
        assert fk_map["user_id"]["on_delete"] == "RESTRICT"
