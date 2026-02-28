"""
Shared pytest fixtures for all database integration tests under testing/tests/.

The ``conn`` fixture provides a module-scoped psycopg2 connection that:
  1. Drops every public table (clean slate).
  2. Applies the initial schema migration.
  3. Yields the connection to the test module.
  4. Closes the connection on teardown.

Each test module gets its own isolated schema state because the fixture is
module-scoped — pytest creates one instance per module.
"""
import os
import sys

import psycopg2
import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from testing.core.config.db_config import DBConfig

MIGRATION_SQL = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "api",
    "migrations",
    "0001_initial_schema.up.sql",
)


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """Open a connection, rebuild the schema from scratch, yield, then close."""
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    # Drop all public tables so we start from a clean state.
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
