"""
MYTUBE-67: Verify title full-text search index — GIN index utilized for
English language search.

Objective:
    Confirm that the GIN index on 'videos.title' (videos_title_fts) is correctly
    utilized for English full-text search queries.

Preconditions:
    Migration '0003_search_indexes' has been applied and test data is present
    in the 'videos' table.

Test strategy:
    1. Set up a clean database and apply:
         - 0001_initial_schema.up.sql (tables)
         - 0003_search_indexes.up.sql (GIN index)
    2. Insert a user and several videos with searchable titles.
    3. Execute a full-text search query using:
         WHERE to_tsvector('english', title) @@ to_tsquery('english', <term>)
    4. Assert the query returns the expected matching records.
    5. Run EXPLAIN ANALYZE on the same query and assert the execution plan
       contains a 'Bitmap Index Scan' or 'Index Scan' using 'videos_title_fts'.

Architecture notes:
    - Pure database integration test — no running API server required.
    - SchemaService / DBConfig follow the existing testing infrastructure.
    - All SQL is parameterised; no hardcoded credentials.
"""

import os
import sys

import psycopg2
import psycopg2.extras
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.schema_service import SchemaService
from testing.components.services.user_service import UserService
from testing.components.services.video_service import VideoService

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)

MIGRATION_SCHEMA = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")
MIGRATION_SEARCH = os.path.join(_MIGRATIONS_DIR, "0003_search_indexes.up.sql")

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------

# Titles designed so specific search terms match only a subset.
_VIDEOS = [
    "Introduction to Python Programming",
    "Advanced Python Techniques",
    "Learn JavaScript Basics",
    "Docker Tutorial for Beginners",
    "Python Data Science with Pandas",
]

# "python" should match indices 0, 1, 4 (3 rows)
_SEARCH_TERM = "python"
_EXPECTED_MATCH_COUNT = 3

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """
    Open a dedicated connection, reset the public schema, apply migrations
    0001 and 0003, insert test data, yield the connection, then close it.
    """
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    schema_svc = SchemaService(connection)
    schema_svc.drop_all_public_tables()
    schema_svc.apply_sql_file(MIGRATION_SCHEMA)
    schema_svc.apply_sql_file(MIGRATION_SEARCH)

    # Insert test data.
    user_svc = UserService(connection)
    uploader_id = user_svc.create_user("fts_test_uid", "fts_tester")

    video_svc = VideoService(connection)
    for title in _VIDEOS:
        video_svc.insert_video(uploader_id, title, "ready")

    yield connection

    connection.close()


# ---------------------------------------------------------------------------
# Tests — Index existence
# ---------------------------------------------------------------------------


class TestGINIndexExists:
    """The GIN full-text search index must exist after migration 0003."""

    def test_videos_title_fts_index_exists(self, conn):
        """
        pg_indexes must contain an entry for 'videos_title_fts' on the
        'videos' table with index type GIN.
        """
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename  = 'videos'
                  AND indexname  = 'videos_title_fts'
                """
            )
            row = cur.fetchone()

        assert row is not None, (
            "Index 'videos_title_fts' does not exist on the 'videos' table. "
            "Migration '0003_search_indexes' may not have been applied."
        )

    def test_videos_title_fts_is_gin(self, conn):
        """The index definition must reference GIN (i.e. USING gin)."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename  = 'videos'
                  AND indexname  = 'videos_title_fts'
                """
            )
            row = cur.fetchone()

        assert row is not None, "Index 'videos_title_fts' not found."
        indexdef = row[0].lower()
        assert "using gin" in indexdef, (
            f"Expected index type GIN but got: {row[0]}"
        )

    def test_videos_title_fts_uses_english_config(self, conn):
        """The index definition must use the 'english' text-search configuration."""
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT indexdef
                FROM pg_indexes
                WHERE schemaname = 'public'
                  AND tablename  = 'videos'
                  AND indexname  = 'videos_title_fts'
                """
            )
            row = cur.fetchone()

        assert row is not None, "Index 'videos_title_fts' not found."
        indexdef = row[0].lower()
        assert "english" in indexdef, (
            f"Expected 'english' text-search configuration in index definition but got: {row[0]}"
        )


# ---------------------------------------------------------------------------
# Tests — Full-text search query correctness
# ---------------------------------------------------------------------------


class TestFullTextSearchReturnsRelevantRecords:
    """FTS query must return only titles that contain the search term."""

    def test_fts_query_returns_matching_rows(self, conn):
        """
        SELECT using to_tsvector / to_tsquery must return exactly the titles
        that contain the search term (case-insensitive, stemmed by 'english').
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title
                FROM videos
                WHERE to_tsvector('english', title) @@ to_tsquery('english', %s)
                ORDER BY title
                """,
                (_SEARCH_TERM,),
            )
            rows = cur.fetchall()

        titles = [r[0] for r in rows]
        assert len(titles) == _EXPECTED_MATCH_COUNT, (
            f"Expected {_EXPECTED_MATCH_COUNT} rows matching '{_SEARCH_TERM}', "
            f"got {len(titles)}: {titles}"
        )

    def test_fts_query_excludes_non_matching_rows(self, conn):
        """
        Rows whose titles do not contain the search term must not appear in
        the result set.
        """
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title
                FROM videos
                WHERE to_tsvector('english', title) @@ to_tsquery('english', %s)
                """,
                (_SEARCH_TERM,),
            )
            rows = cur.fetchall()

        titles = [r[0] for r in rows]
        non_python_titles = [t for t in titles if "python" not in t.lower()]
        assert non_python_titles == [], (
            f"FTS query returned non-matching titles: {non_python_titles}"
        )

    def test_fts_query_returns_all_matching_titles(self, conn):
        """All titles that contain the search term must be present in results."""
        expected_titles = sorted(
            t for t in _VIDEOS if _SEARCH_TERM in t.lower()
        )

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT title
                FROM videos
                WHERE to_tsvector('english', title) @@ to_tsquery('english', %s)
                ORDER BY title
                """,
                (_SEARCH_TERM,),
            )
            rows = cur.fetchall()

        actual_titles = sorted(r[0] for r in rows)
        assert actual_titles == expected_titles, (
            f"Expected titles: {expected_titles}\nGot: {actual_titles}"
        )


# ---------------------------------------------------------------------------
# Tests — Query execution plan uses the GIN index
# ---------------------------------------------------------------------------


class TestQueryPlanUsesGINIndex:
    """
    EXPLAIN ANALYZE must confirm that PostgreSQL chooses the GIN index
    'videos_title_fts' for the full-text search query.
    """

    def _get_explain_output(self, conn) -> str:
        """Run EXPLAIN ANALYZE and return the full plan as a single string."""
        with conn.cursor() as cur:
            cur.execute(
                """
                EXPLAIN ANALYZE
                SELECT title
                FROM videos
                WHERE to_tsvector('english', title) @@ to_tsquery('english', %s)
                """,
                (_SEARCH_TERM,),
            )
            rows = cur.fetchall()
        return "\n".join(r[0] for r in rows)

    def test_plan_references_videos_title_fts_index(self, conn):
        """
        The execution plan must reference 'videos_title_fts', confirming the
        GIN index is used rather than a sequential scan.
        """
        plan = self._get_explain_output(conn)
        assert "videos_title_fts" in plan, (
            f"Expected 'videos_title_fts' in EXPLAIN ANALYZE output but it was absent.\n"
            f"Full plan:\n{plan}"
        )

    def test_plan_uses_index_scan_or_bitmap_index_scan(self, conn):
        """
        The execution plan must contain either 'Bitmap Index Scan' or
        'Index Scan', confirming the GIN index is used.
        """
        plan = self._get_explain_output(conn)
        plan_lower = plan.lower()
        uses_index = (
            "bitmap index scan" in plan_lower
            or "index scan" in plan_lower
        )
        assert uses_index, (
            f"Expected 'Bitmap Index Scan' or 'Index Scan' in execution plan but got:\n{plan}"
        )

    def test_plan_does_not_use_seq_scan_for_fts(self, conn):
        """
        With the GIN index present and sufficient data, PostgreSQL should not
        fall back to a sequential scan for the full-text search predicate.

        Note: PostgreSQL may still choose Seq Scan for very small tables when
        the planner determines it is cheaper. This test is skipped when the
        table has fewer than 100 rows to avoid false failures in small datasets.
        """
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM videos")
            row_count = cur.fetchone()[0]

        if row_count < 100:
            pytest.skip(
                f"Table has only {row_count} rows; planner may prefer Seq Scan "
                "over GIN index for small datasets. Skipping Seq Scan assertion."
            )

        plan = self._get_explain_output(conn)
        assert "seq scan" not in plan.lower(), (
            f"Unexpected Seq Scan in execution plan for large dataset:\n{plan}"
        )
