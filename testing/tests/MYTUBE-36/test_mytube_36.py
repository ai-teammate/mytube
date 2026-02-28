"""
MYTUBE-36: Perform migration rollback — down scripts remove all schema objects
successfully.

Verifies that running 0001_initial_schema.down.sql against a database that has
had 0001_initial_schema.up.sql applied drops all 8 core tables and leaves the
schema in its pre-migration state (no tables, no trigger function).
"""
import os
import sys
import pytest
import psycopg2

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.schema_service import SchemaService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MIGRATION_UP_SQL = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "api",
    "migrations",
    "0001_initial_schema.up.sql",
)

MIGRATION_DOWN_SQL = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "..",
    "api",
    "migrations",
    "0001_initial_schema.down.sql",
)

TABLES_CREATED_BY_UP = [
    "users",
    "videos",
    "categories",
    "video_tags",
    "playlists",
    "playlist_videos",
    "comments",
    "ratings",
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
    Open a connection to the test database, apply the UP migration to
    establish a known good state, then run the DOWN migration, and yield
    the connection for assertions.
    """
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    # Start from a clean slate — drop everything that might exist from a
    # previous run.
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

    # Apply UP migration so the schema is in the expected post-migration state.
    with open(MIGRATION_UP_SQL, "r") as f:
        up_sql = f.read()
    with connection.cursor() as cur:
        cur.execute(up_sql)

    # Apply DOWN migration — this is what we are testing.
    with open(MIGRATION_DOWN_SQL, "r") as f:
        down_sql = f.read()
    with connection.cursor() as cur:
        cur.execute(down_sql)

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def schema(conn) -> SchemaService:
    return SchemaService(conn)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAllTablesDropped:
    """All 8 tables created by the UP migration must be absent after rollback."""

    @pytest.mark.parametrize("table_name", TABLES_CREATED_BY_UP)
    def test_table_does_not_exist(self, schema: SchemaService, table_name: str):
        assert not schema.table_exists(table_name), (
            f"Table '{table_name}' still exists after running the DOWN migration."
        )


class TestTriggerFunctionDropped:
    """The set_updated_at() trigger function must be removed by the DOWN migration."""

    def test_set_updated_at_function_dropped(self, conn):
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public'
                      AND p.proname = 'set_updated_at'
                )
                """
            )
            exists = cur.fetchone()[0]
        assert not exists, (
            "Trigger function 'set_updated_at' still exists after running the DOWN migration."
        )


class TestNoPublicTablesRemain:
    """After rollback the public schema must contain zero user-defined tables."""

    def test_schema_is_empty(self, conn):
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'"
            )
            count = cur.fetchone()[0]
        assert count == 0, (
            f"Expected 0 tables in public schema after DOWN migration, found {count}."
        )
