"""
MYTUBE-31: Verify initial category seeding — default categories populated in database.

Verifies that running 0001_initial_schema.up.sql followed by
0002_seed_categories.up.sql against a clean PostgreSQL database results in
exactly 5 category rows: Education, Entertainment, Gaming, Music, and Other.
"""
import os
import sys
import pytest
import psycopg2

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig

# ---------------------------------------------------------------------------
# Migration file paths
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)

SCHEMA_MIGRATION_SQL = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")
SEED_MIGRATION_SQL = os.path.join(_MIGRATIONS_DIR, "0002_seed_categories.up.sql")

EXPECTED_CATEGORIES = sorted(["Education", "Entertainment", "Gaming", "Music", "Other"])

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """Open a connection, drop all tables, apply both migrations, yield, then close."""
    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    # Drop all tables so we start from a clean state.
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

    # Apply schema migration.
    with open(SCHEMA_MIGRATION_SQL, "r") as f:
        schema_sql = f.read()
    with connection.cursor() as cur:
        cur.execute(schema_sql)

    # Apply seed migration.
    with open(SEED_MIGRATION_SQL, "r") as f:
        seed_sql = f.read()
    with connection.cursor() as cur:
        cur.execute(seed_sql)

    yield connection

    connection.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCategorySeeding:
    """Verify that the seed migration populates exactly the 5 expected categories."""

    def test_exactly_five_categories(self, conn):
        """SELECT COUNT(*) FROM categories must return 5."""
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM categories;")
            count = cur.fetchone()[0]
        assert count == 5, (
            f"Expected exactly 5 categories, found {count}."
        )

    def test_category_names_match_expected(self, conn):
        """SELECT name FROM categories ORDER BY name ASC must return the 5 expected names."""
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM categories ORDER BY name ASC;")
            rows = cur.fetchall()
        actual = [row[0] for row in rows]
        assert actual == EXPECTED_CATEGORIES, (
            f"Expected categories {EXPECTED_CATEGORIES}, got {actual}."
        )

    @pytest.mark.parametrize("category_name", EXPECTED_CATEGORIES)
    def test_each_expected_category_exists(self, conn, category_name: str):
        """Each expected category name must be present in the categories table."""
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM categories WHERE name = %s;",
                (category_name,),
            )
            count = cur.fetchone()[0]
        assert count == 1, (
            f"Category '{category_name}' not found in the categories table."
        )

    def test_seed_is_idempotent(self, conn):
        """Running the seed migration a second time must not create duplicate rows."""
        with open(SEED_MIGRATION_SQL, "r") as f:
            seed_sql = f.read()
        with conn.cursor() as cur:
            cur.execute(seed_sql)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM categories;")
            count = cur.fetchone()[0]
        assert count == 5, (
            f"After re-running seed migration, expected 5 categories, found {count}. "
            "The seed may not be idempotent (ON CONFLICT DO NOTHING is required)."
        )
