"""Shared pytest fixtures for all test modules under testing/tests/."""
import os
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from testing.core.config.db_config import DBConfig


def _drop_all(connection) -> None:
    """Drop all public tables and the set_updated_at trigger function."""
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


def _apply_sql(connection, path: str) -> None:
    """Read a SQL file and execute it against the given connection."""
    with open(path, "r") as fh:
        sql = fh.read()
    with connection.cursor() as cur:
        cur.execute(sql)


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


def make_conn_fixture(migration_files: list[str]):
    """
    Factory that returns a module-scoped ``conn`` fixture applying the given
    migration files in order after wiping the database clean.

    Usage in a test module::

        from testing.tests.conftest import make_conn_fixture

        MIGRATIONS = [
            "/abs/path/to/0001_initial_schema.up.sql",
            "/abs/path/to/0002_seed_categories.up.sql",
        ]

        conn = make_conn_fixture(MIGRATIONS)
    """

    @pytest.fixture(scope="module")
    def conn(db_config: DBConfig):
        connection = psycopg2.connect(db_config.dsn())
        connection.autocommit = True
        _drop_all(connection)
        for path in migration_files:
            _apply_sql(connection, path)
        yield connection
        connection.close()

    return conn
