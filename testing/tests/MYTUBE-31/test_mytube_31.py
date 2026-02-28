"""
MYTUBE-31: Verify initial category seeding — default categories populated in database.

Verifies that running 0001_initial_schema.up.sql followed by
0002_seed_categories.up.sql against a clean PostgreSQL database results in
exactly 5 category rows: Education, Entertainment, Gaming, Music, and Other.
"""
import os
import sys

import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.category_service import CategoryService
from testing.tests.conftest import make_conn_fixture

# ---------------------------------------------------------------------------
# Migration file paths
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "api", "migrations"
)

_SCHEMA_MIGRATION_SQL = os.path.join(_MIGRATIONS_DIR, "0001_initial_schema.up.sql")
_SEED_MIGRATION_SQL = os.path.join(_MIGRATIONS_DIR, "0002_seed_categories.up.sql")

EXPECTED_CATEGORIES = sorted(["Education", "Entertainment", "Gaming", "Music", "Other"])

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Shared connection fixture: drop all → apply schema → apply seed.
conn = make_conn_fixture([_SCHEMA_MIGRATION_SQL, _SEED_MIGRATION_SQL])


@pytest.fixture(scope="module")
def category_service(conn) -> CategoryService:
    return CategoryService(conn)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCategorySeeding:
    """Verify that the seed migration populates exactly the 5 expected categories."""

    def test_exactly_five_categories(self, category_service: CategoryService):
        """SELECT COUNT(*) FROM categories must return 5."""
        count = category_service.get_category_count()
        assert count == 5, (
            f"Expected exactly 5 categories, found {count}."
        )

    def test_category_names_match_expected(self, category_service: CategoryService):
        """SELECT name FROM categories ORDER BY name ASC must return the 5 expected names."""
        actual = category_service.get_category_names()
        assert actual == EXPECTED_CATEGORIES, (
            f"Expected categories {EXPECTED_CATEGORIES}, got {actual}."
        )

    @pytest.mark.parametrize("category_name", EXPECTED_CATEGORIES)
    def test_each_expected_category_exists(
        self, category_service: CategoryService, category_name: str
    ):
        """Each expected category name must be present in the categories table."""
        assert category_service.category_exists(category_name), (
            f"Category '{category_name}' not found in the categories table."
        )

    def test_seed_is_idempotent(self, category_service: CategoryService):
        """Running the seed migration a second time must not create duplicate rows."""
        category_service.apply_seed(_SEED_MIGRATION_SQL)

        count = category_service.get_category_count()
        assert count == 5, (
            f"After re-running seed migration, expected 5 categories, found {count}. "
            "The seed may not be idempotent (ON CONFLICT DO NOTHING is required)."
        )
