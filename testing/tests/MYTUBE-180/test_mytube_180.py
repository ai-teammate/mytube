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
                 Defaults to https://mytube-api-80693608388.us-central1.run.app
                 Test is skipped when explicitly set to an empty string.
"""
import json
import os
import sys
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_API_BASE_URL = "https://mytube-api-80693608388.us-central1.run.app"
_API_BASE_URL = os.getenv("API_BASE_URL", _DEFAULT_API_BASE_URL).rstrip("/")

_CATEGORIES_PATH = "/api/categories"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def categories_response() -> dict:
    """Issue GET /api/categories and return a dict with status_code and body."""
    url = f"{_API_BASE_URL}{_CATEGORIES_PATH}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return {"status_code": resp.status, "body": resp.read().decode()}
    except urllib.error.HTTPError as exc:
        return {"status_code": exc.code, "body": exc.read().decode()}
    except urllib.error.URLError as exc:
        pytest.skip(f"API unreachable at {url}: {exc.reason}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetCategoriesEndpoint:
    """GET /api/categories must return 200 and a list of id+name objects."""

    def test_status_code_is_200(self, categories_response):
        """The response status must be HTTP 200 OK."""
        assert categories_response["status_code"] == 200, (
            f"Expected HTTP 200, got {categories_response['status_code']}. "
            f"Body: {categories_response['body']}"
        )

    def test_response_body_is_json_array(self, categories_response):
        """The response body must be a valid JSON array."""
        try:
            data = json.loads(categories_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(f"Response body is not valid JSON: {exc}\nBody: {categories_response['body']}")
        assert isinstance(data, list), (
            f"Expected a JSON array, got {type(data).__name__}: {categories_response['body']}"
        )

    def test_response_is_non_empty(self, categories_response):
        """The categories list must contain at least one category."""
        data = json.loads(categories_response["body"])
        assert len(data) > 0, "Expected at least one category, but got an empty array."

    def test_every_category_has_id_field(self, categories_response):
        """Every category object must contain an 'id' field."""
        data = json.loads(categories_response["body"])
        for i, item in enumerate(data):
            assert "id" in item, (
                f"Category at index {i} is missing the 'id' field: {item}"
            )

    def test_every_category_id_is_integer(self, categories_response):
        """The 'id' field of every category must be an integer."""
        data = json.loads(categories_response["body"])
        for i, item in enumerate(data):
            assert isinstance(item.get("id"), int), (
                f"Category at index {i}: expected 'id' to be int, got {type(item.get('id')).__name__}: {item}"
            )

    def test_every_category_has_name_field(self, categories_response):
        """Every category object must contain a 'name' field."""
        data = json.loads(categories_response["body"])
        for i, item in enumerate(data):
            assert "name" in item, (
                f"Category at index {i} is missing the 'name' field: {item}"
            )

    def test_every_category_name_is_non_empty_string(self, categories_response):
        """The 'name' field of every category must be a non-empty string."""
        data = json.loads(categories_response["body"])
        for i, item in enumerate(data):
            name = item.get("name")
            assert isinstance(name, str) and name.strip(), (
                f"Category at index {i}: expected 'name' to be a non-empty string, got: {name!r}"
            )

    def test_no_extra_unexpected_fields(self, categories_response):
        """Each category object must contain exactly 'id' and 'name' (no extra fields)."""
        data = json.loads(categories_response["body"])
        expected_keys = {"id", "name"}
        for i, item in enumerate(data):
            extra = set(item.keys()) - expected_keys
            assert not extra, (
                f"Category at index {i} has unexpected fields {extra}: {item}"
            )
