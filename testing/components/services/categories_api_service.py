"""Service object for querying the /api/categories endpoint."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import List

from testing.core.config.api_config import APIConfig


@dataclass
class CategoriesResponse:
    """Represents the HTTP response from GET /api/categories."""

    status_code: int
    categories: List[dict] = field(default_factory=list)
    raw_body: str = ""


class CategoriesApiService:
    """Provides methods to query the GET /api/categories endpoint.

    Encapsulates all HTTP-level concerns; tests depend only on the
    high-level ``get_categories`` interface, not on raw urllib calls.

    Usage::

        svc = CategoriesApiService(api_config)
        resp = svc.get_categories()
        assert resp.status_code == 200
        assert len(resp.categories) > 0
    """

    def __init__(self, config: APIConfig) -> None:
        self._base_url = config.base_url.rstrip("/")

    def get_categories(self) -> CategoriesResponse:
        """Issue GET /api/categories and return a CategoriesResponse.

        On network errors the test is skipped via ``pytest.skip``.
        On HTTP errors the response object is returned with the error
        status code and an empty categories list.
        """
        url = f"{self._base_url}/api/categories"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode()
                try:
                    data = json.loads(body)
                    categories = data if isinstance(data, list) else []
                except json.JSONDecodeError:
                    categories = []
                return CategoriesResponse(
                    status_code=resp.status,
                    categories=categories,
                    raw_body=body,
                )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            return CategoriesResponse(
                status_code=exc.code,
                categories=[],
                raw_body=body,
            )
        except urllib.error.URLError as exc:
            import pytest  # imported here to keep the service pytest-agnostic at module level

            pytest.skip(f"API unreachable at {url}: {exc.reason}")
