"""
MYTUBE-180: Retrieve all categories — API returns full list for navigation.

Verifies that GET /api/categories returns a non-empty JSON array where every
element contains the 'id' (integer) and 'name' (string) fields required by the
UI to build category navigation.

Test steps
----------
1. Send GET /api/categories to the deployed API (no auth required).
2. Assert HTTP 200.
3. Assert the response body is a non-empty JSON array.
4. Assert every element contains 'id' (int) and 'name' (non-empty str).

Environment variables
---------------------
- API_BASE_URL : Base URL of the deployed API.
                 Defaults to http://localhost:8080 (via APIConfig).
                 Set to https://mytube-api-80693608388.us-central1.run.app in CI.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.components.services.categories_api_service import (
    CategoriesApiService,
    CategoriesResponse,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    """Return an APIConfig loaded from environment variables."""
    return APIConfig()


@pytest.fixture(scope="module")
def categories_response(api_config: APIConfig) -> CategoriesResponse:
    """Issue GET /api/categories via CategoriesApiService and return the response."""
    return CategoriesApiService(api_config).get_categories()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetCategoriesEndpoint:
    """GET /api/categories must return 200 and a list of id+name objects."""

    def test_status_code_is_200(self, categories_response: CategoriesResponse):
        """The response status must be HTTP 200 OK."""
        assert categories_response.status_code == 200, (
            f"Expected HTTP 200, got {categories_response.status_code}. "
            f"Body: {categories_response.raw_body}"
        )

    def test_response_body_is_json_array(self, categories_response: CategoriesResponse):
        """The response body must be a valid JSON array."""
        assert isinstance(categories_response.categories, list), (
            f"Expected a JSON array, got {type(categories_response.categories).__name__}: "
            f"{categories_response.raw_body}"
        )

    def test_response_is_non_empty(self, categories_response: CategoriesResponse):
        """The categories list must contain at least one category."""
        assert len(categories_response.categories) > 0, (
            "Expected at least one category, but got an empty array."
        )

    def test_every_category_has_id_field(self, categories_response: CategoriesResponse):
        """Every category object must contain an 'id' field."""
        for i, item in enumerate(categories_response.categories):
            assert "id" in item, (
                f"Category at index {i} is missing the 'id' field: {item}"
            )

    def test_every_category_id_is_integer(self, categories_response: CategoriesResponse):
        """The 'id' field of every category must be an integer."""
        for i, item in enumerate(categories_response.categories):
            assert isinstance(item.get("id"), int), (
                f"Category at index {i}: expected 'id' to be int, "
                f"got {type(item.get('id')).__name__}: {item}"
            )

    def test_every_category_has_name_field(self, categories_response: CategoriesResponse):
        """Every category object must contain a 'name' field."""
        for i, item in enumerate(categories_response.categories):
            assert "name" in item, (
                f"Category at index {i} is missing the 'name' field: {item}"
            )

    def test_every_category_name_is_non_empty_string(self, categories_response: CategoriesResponse):
        """The 'name' field of every category must be a non-empty string."""
        for i, item in enumerate(categories_response.categories):
            name = item.get("name")
            assert isinstance(name, str) and name.strip(), (
                f"Category at index {i}: expected 'name' to be a non-empty string, "
                f"got: {name!r}"
            )
