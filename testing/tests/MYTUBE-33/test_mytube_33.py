"""
MYTUBE-33: Execute migration multiple times — subsequent runs skip existing
migrations without error.

Verifies the idempotency of the migration system:
- golang-migrate tracks applied versions in the `schema_migrations` table.
- On a second startup the DB is already at the latest version, so
  `RunMigrations` receives `migrate.ErrNoChange` which it silently discards.
- The schema and data are left completely unchanged.

Test strategy
-------------
1. Start from a clean database and apply all migrations (first run).
2. Capture the schema state: table names, schema_migrations version.
3. Simulate a second migration run:
   a. Prove that re-applying the raw SQL would fail (tables already exist),
      confirming that the golang-migrate version tracker is the idempotency guard.
   b. Confirm the schema_migrations version is unchanged.
   c. Confirm all tables are still present with the same count.
   d. Confirm seeded category data is still intact.
"""

import os
import sys
import pytest
import psycopg2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.schema_service import SchemaService

# ---------------------------------------------------------------------------
# Paths to the migration SQL files
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)

MIGRATION_01_UP = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")
MIGRATION_02_UP = os.path.join(_MIGRATIONS_DIR, "0002_seed_categories.up.sql")

# The highest migration version number the production code would apply.
LATEST_MIGRATION_VERSION = 2

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

SEEDED_CATEGORIES = {"Education", "Entertainment", "Gaming", "Music", "Other"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """
    Open a connection to the test database, perform a clean reset, apply all
    migrations once (first run), then yield the connection.

    This mirrors what `RunMigrations` does on first API startup:
    - golang-migrate creates the `schema_migrations` table if absent.
    - It applies each numbered *.up.sql file in order.
    - It records the final version in `schema_migrations`.

    We replicate this at the SQL level using psycopg2 so the test does not
    require a running Go binary.
    """
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    with connection.cursor() as cur:
        # Drop all user tables from a previous test run.
        cur.execute(
            """
            DO $$ DECLARE r RECORD; BEGIN
                FOR r IN (
                    SELECT tablename FROM pg_tables
                    WHERE schemaname = 'public'
                      AND tablename != 'schema_migrations'
                ) LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
            """
        )
        cur.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE;")

        # Drop and recreate the schema_migrations table so we start with a
        # clean migration history (simulates a brand-new database).
        cur.execute("DROP TABLE IF EXISTS schema_migrations;")
        cur.execute(
            """
            CREATE TABLE schema_migrations (
                version BIGINT NOT NULL PRIMARY KEY,
                dirty   BOOLEAN NOT NULL
            );
            """
        )

    # --- First migration run ---
    # Apply migration 0001.
    with open(MIGRATION_01_UP) as f:
        sql_01 = f.read()
    with connection.cursor() as cur:
        cur.execute(sql_01)
        cur.execute(
            "INSERT INTO schema_migrations (version, dirty) VALUES (1, false) "
            "ON CONFLICT (version) DO UPDATE SET dirty = false;"
        )

    # Apply migration 0002.
    with open(MIGRATION_02_UP) as f:
        sql_02 = f.read()
    with connection.cursor() as cur:
        cur.execute(sql_02)
        cur.execute(
            "INSERT INTO schema_migrations (version, dirty) VALUES (2, false) "
            "ON CONFLICT (version) DO UPDATE SET dirty = false;"
        )

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def schema(conn) -> SchemaService:
    return SchemaService(conn)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _get_schema_migrations_row(conn) -> dict:
    """Return the highest-version row from schema_migrations."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT version, dirty FROM schema_migrations ORDER BY version DESC LIMIT 1;"
        )
        row = cur.fetchone()
        assert row is not None, "schema_migrations table is empty"
        return {"version": row[0], "dirty": row[1]}


def _count_public_tables(conn) -> int:
    """Return the number of tables in the public schema (excluding schema_migrations)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) FROM pg_tables
            WHERE schemaname = 'public'
              AND tablename != 'schema_migrations'
            """
        )
        return cur.fetchone()[0]


def _get_category_names(conn) -> set:
    """Return the set of category names currently in the categories table."""
    with conn.cursor() as cur:
        cur.execute("SELECT name FROM categories;")
        return {row[0] for row in cur.fetchall()}


# ---------------------------------------------------------------------------
# Tests — First-run state
# ---------------------------------------------------------------------------


class TestFirstRunState:
    """After the first migration run the version tracker must be in a clean state."""

    def test_schema_migrations_table_exists(self, schema: SchemaService):
        """golang-migrate creates schema_migrations to track applied versions."""
        assert schema.table_exists("schema_migrations"), (
            "schema_migrations table does not exist — migration version tracking is broken"
        )

    def test_schema_migrations_version_is_latest(self, conn):
        """The recorded version must equal the number of migration files."""
        row = _get_schema_migrations_row(conn)
        assert row["version"] == LATEST_MIGRATION_VERSION, (
            f"Expected schema_migrations.version = {LATEST_MIGRATION_VERSION}, "
            f"got {row['version']}"
        )

    def test_schema_migrations_not_dirty(self, conn):
        """A clean first run must leave dirty = false (no partial migration)."""
        row = _get_schema_migrations_row(conn)
        assert row["dirty"] is False, (
            "schema_migrations.dirty is True after first run — "
            "migration may have failed mid-execution"
        )

    @pytest.mark.parametrize("table_name", REQUIRED_TABLES)
    def test_all_tables_present(self, schema: SchemaService, table_name: str):
        """All 8 core application tables must exist after the first run."""
        assert schema.table_exists(table_name), (
            f"Table '{table_name}' is missing after first migration run"
        )


# ---------------------------------------------------------------------------
# Tests — Second-run idempotency
# ---------------------------------------------------------------------------


class TestSecondRunIdempotency:
    """
    Verify that running migrations again (as happens on API restart) is a no-op:
    no errors, no schema changes, no data loss.
    """

    def test_reapply_schema_sql_fails_without_tracker(self, db_config):
        """
        Directly re-executing the raw CREATE TABLE SQL raises an error because
        the tables already exist.  This proves that it is the golang-migrate
        version tracker (schema_migrations) that makes the second run safe —
        the SQL itself is NOT idempotent.

        A dedicated connection is used so the shared module fixture is not
        left in an aborted-transaction state.
        """
        with open(MIGRATION_01_UP) as f:
            sql = f.read()

        probe = psycopg2.connect(db_config.dsn())
        probe.autocommit = False
        raised = False
        try:
            with probe.cursor() as cur:
                cur.execute("SAVEPOINT before_reapply;")
                try:
                    cur.execute(sql)
                except psycopg2.DatabaseError:
                    raised = True
                    cur.execute("ROLLBACK TO SAVEPOINT before_reapply;")
                    cur.execute("RELEASE SAVEPOINT before_reapply;")
                else:
                    cur.execute("RELEASE SAVEPOINT before_reapply;")
            probe.commit()
        finally:
            probe.close()

        assert raised, (
            "Re-applying 0001_initial_schema.up.sql did not raise an error. "
            "The SQL should fail because tables/objects already exist."
        )

    def test_schema_migrations_version_unchanged_after_second_run(self, conn):
        """
        After the failed re-apply attempt the schema_migrations version must
        still equal LATEST_MIGRATION_VERSION.  golang-migrate would check this
        first and return ErrNoChange without attempting to re-run the SQL.
        """
        row = _get_schema_migrations_row(conn)
        assert row["version"] == LATEST_MIGRATION_VERSION, (
            f"schema_migrations.version changed after second run attempt: "
            f"expected {LATEST_MIGRATION_VERSION}, got {row['version']}"
        )

    def test_table_count_unchanged_after_second_run(self, conn):
        """No tables must be added or removed by a second migration run."""
        assert _count_public_tables(conn) == len(REQUIRED_TABLES), (
            f"Expected {len(REQUIRED_TABLES)} application tables, "
            f"got {_count_public_tables(conn)}"
        )

    def test_categories_data_unchanged_after_second_run(self, conn):
        """
        Seeded category data must survive the second run unchanged.
        Migration 0002 uses ON CONFLICT DO NOTHING, so re-running it would be
        safe — but golang-migrate never re-runs it, and data must remain intact.
        """
        categories = _get_category_names(conn)
        assert categories == SEEDED_CATEGORIES, (
            f"Category data changed after second run. "
            f"Expected: {SEEDED_CATEGORIES}, got: {categories}"
        )
