"""
MYTUBE-70: Rollback search index migration — indexes removed cleanly without
affecting table data.

Verifies that the 'down' script for migration 0003_search_indexes successfully
removes the four search-specific indexes while leaving the 'videos' and
'video_tags' tables — and their data — completely intact.

Test sequence:
  1. Start from a clean schema (initial migration applied by conftest).
  2. Apply 0003_search_indexes.up.sql — indexes created.
  3. Insert data into 'videos' and 'video_tags'.
  4. Apply 0003_search_indexes.down.sql — indexes dropped.
  5. Assert all four indexes are gone.
  6. Assert table record counts are unchanged.
  7. Assert both tables still exist.
"""
import os
import sys
import uuid

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.schema_service import SchemaService

# Fixtures conn and db_config are provided by testing/tests/conftest.py.

# ---------------------------------------------------------------------------
# Paths to migration SQL files
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)

SEARCH_INDEXES_UP = os.path.join(_MIGRATIONS_DIR, "0003_search_indexes.up.sql")
SEARCH_INDEXES_DOWN = os.path.join(_MIGRATIONS_DIR, "0003_search_indexes.down.sql")

# The four indexes defined in 0003_search_indexes.up.sql
SEARCH_INDEXES = [
    "videos_title_fts",
    "video_tags_tag_idx",
    "videos_status_created",
    "videos_status_views",
]


# ---------------------------------------------------------------------------
# Module-scoped fixture: apply up, seed data, apply down
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def rollback_state(conn) -> dict:
    """Apply the search-indexes migration, seed data, then roll it back.

    Returns a dict with the row counts captured *after* rollback and the
    SchemaService used for index inspection.
    """
    schema = SchemaService(conn)

    # Step 1: Apply the up migration so indexes exist.
    schema.apply_sql_file(SEARCH_INDEXES_UP)

    # Step 2: Verify indexes exist before rollback (sanity check).
    for idx in SEARCH_INDEXES:
        assert schema.index_exists(idx), (
            f"Pre-condition failed: index '{idx}' not found after applying up migration."
        )

    # Step 3: Seed a user (required by the videos FK).
    user_id = str(uuid.uuid4())
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (id, firebase_uid, username)
            VALUES (%s, %s, %s)
            """,
            (user_id, "firebase_uid_mytube70", "testuser_mytube70"),
        )

    # Step 4: Seed rows into videos.
    video_ids = [str(uuid.uuid4()), str(uuid.uuid4())]
    with conn.cursor() as cur:
        for vid_id in video_ids:
            cur.execute(
                """
                INSERT INTO videos (id, uploader_id, title, status)
                VALUES (%s, %s, %s, 'ready')
                """,
                (vid_id, user_id, f"Test Video {vid_id[:8]}"),
            )

    # Step 5: Seed rows into video_tags.
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO video_tags (video_id, tag) VALUES (%s, %s)",
            (video_ids[0], "python"),
        )
        cur.execute(
            "INSERT INTO video_tags (video_id, tag) VALUES (%s, %s)",
            (video_ids[1], "testing"),
        )

    videos_count_before = schema.count_rows("videos")
    tags_count_before = schema.count_rows("video_tags")

    # Step 6: Apply the down migration — rollback.
    schema.apply_sql_file(SEARCH_INDEXES_DOWN)

    return {
        "schema": schema,
        "videos_count_before": videos_count_before,
        "tags_count_before": tags_count_before,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSearchIndexesDropped:
    """All four search indexes must be absent after the down migration."""

    @pytest.mark.parametrize("index_name", SEARCH_INDEXES)
    def test_index_is_dropped(self, rollback_state: dict, index_name: str):
        schema: SchemaService = rollback_state["schema"]
        assert not schema.index_exists(index_name), (
            f"Index '{index_name}' still exists after running the down migration."
        )


class TestTableDataPreserved:
    """videos and video_tags tables and their rows must survive the rollback."""

    def test_videos_table_still_exists(self, rollback_state: dict):
        schema: SchemaService = rollback_state["schema"]
        assert schema.table_exists("videos"), (
            "Table 'videos' was dropped during index rollback."
        )

    def test_video_tags_table_still_exists(self, rollback_state: dict):
        schema: SchemaService = rollback_state["schema"]
        assert schema.table_exists("video_tags"), (
            "Table 'video_tags' was dropped during index rollback."
        )

    def test_videos_row_count_unchanged(self, rollback_state: dict):
        schema: SchemaService = rollback_state["schema"]
        count_after = schema.count_rows("videos")
        assert count_after == rollback_state["videos_count_before"], (
            f"videos row count changed: was {rollback_state['videos_count_before']}, "
            f"now {count_after}."
        )

    def test_video_tags_row_count_unchanged(self, rollback_state: dict):
        schema: SchemaService = rollback_state["schema"]
        count_after = schema.count_rows("video_tags")
        assert count_after == rollback_state["tags_count_before"], (
            f"video_tags row count changed: was {rollback_state['tags_count_before']}, "
            f"now {count_after}."
        )
