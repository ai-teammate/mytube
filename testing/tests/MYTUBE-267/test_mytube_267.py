"""
MYTUBE-267: API request with invalid category_id format — 400 Bad Request returned.

Objective
---------
Verify that the API returns an error when the category_id parameter is provided in an
incorrect format.

Preconditions
-------------
- The API is deployed and reachable at API_BASE_URL.

Test steps
----------
1. Send a GET request to /api/videos?category_id=not-a-valid-id&limit=20.
2. Inspect the HTTP response code and body.

Expected Result
---------------
The API returns a 400 Bad Request status code and a clear error message indicating
the invalid parameter format.

Architecture notes
------------------
- The API is expected to be deployed and reachable at API_BASE_URL.
- Plain HTTP requests with error handling.
- If the API is unreachable, the test skips gracefully.

Environment variables
---------------------
API_BASE_URL : Base URL of the deployed API (default: http://localhost:8080).
API_HOST     : API host (used to construct base_url if API_BASE_URL is absent).
API_PORT     : API port (used to construct base_url if API_BASE_URL is absent).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUEST_TIMEOUT = 10.0

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


def _make_request(url: str, timeout: float = _REQUEST_TIMEOUT) -> tuple[int, str]:
    """Make a GET request and return (status_code, body).

    Returns (0, "") if the host is unreachable.
    """
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode()
            return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else ""
        return exc.code, body
    except Exception:
        return 0, ""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInvalidCategoryIdFormat:
    """MYTUBE-267: API request with invalid category_id format — 400 Bad Request returned."""

    def test_invalid_category_id_returns_400(self, api_config: APIConfig) -> None:
        """Sending an invalid category_id parameter must return HTTP 400 Bad Request."""
        url = f"{api_config.base_url}/api/videos?category_id=not-a-valid-id&limit=20"
        status_code, body = _make_request(url)

        if status_code == 0:
            pytest.skip("API is not reachable — set API_BASE_URL to the deployed instance.")

        assert status_code == 400, (
            f"Expected HTTP 400 Bad Request for invalid category_id, "
            f"but got HTTP {status_code} instead.\n"
            f"Response body: {body!r}"
        )

    def test_invalid_category_id_error_message(self, api_config: APIConfig) -> None:
        """The error response must include a message about invalid category_id format."""
        url = f"{api_config.base_url}/api/videos?category_id=not-a-valid-id&limit=20"
        status_code, body = _make_request(url)

        if status_code == 0:
            pytest.skip("API is not reachable — set API_BASE_URL to the deployed instance.")

        if status_code != 400:
            pytest.fail(
                f"Expected HTTP 400 Bad Request, but got HTTP {status_code}.\n"
                f"Response body: {body!r}"
            )

        # Try to parse as JSON
        try:
            error_json = json.loads(body)
        except json.JSONDecodeError:
            pytest.fail(
                f"Expected JSON error response, but response was not valid JSON:\n{body!r}"
            )

        # Check for error message (could be in "message" or "error" field)
        error_message = error_json.get("message") or error_json.get("error") or ""
        assert error_message, (
            f"Expected error response to contain a 'message' or 'error' field, "
            f"but got: {error_json!r}"
        )

        # Check that the message mentions category_id or invalid
        assert (
            "category_id" in error_message.lower()
            or "invalid" in error_message.lower()
        ), (
            f"Expected error message to mention 'category_id' or 'invalid', "
            f"but got: {error_message!r}"
        )
