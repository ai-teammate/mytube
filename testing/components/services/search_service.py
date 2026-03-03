"""Service object for querying the search API endpoint."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class SearchResult:
    """Represents a single video card returned by the search API."""

    id: str
    title: str
    thumbnail_url: Optional[str]
    view_count: int
    uploader_username: str
    created_at: str


@dataclass
class SearchResponse:
    """Represents the full HTTP response from GET /api/search."""

    status_code: int
    items: list[SearchResult] = field(default_factory=list)
    raw_body: str = ""


class SearchService:
    """Provides helpers for querying the /api/search endpoint.

    Encapsulates all HTTP-level concerns; tests depend only on the high-level
    search/paginate interface, not on raw urllib calls.

    Usage::

        svc = SearchService(base_url="http://127.0.0.1:18077")
        resp = svc.search(q="tutorial", limit=20, offset=0)
        assert resp.status_code == 200
        assert len(resp.items) == 20
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def search(
        self,
        q: str = "",
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> SearchResponse:
        """Issue GET /api/search with the given parameters.

        Returns a SearchResponse with status_code and parsed items list.
        On non-2xx responses, items will be empty and raw_body will contain
        the error payload.
        """
        params: list[str] = []
        if q:
            params.append(f"q={urllib.parse.quote(q)}")
        if limit is not None:
            params.append(f"limit={limit}")
        if offset is not None:
            params.append(f"offset={offset}")

        query_string = "&".join(params)
        url = f"{self._base_url}/api/search"
        if query_string:
            url = f"{url}?{query_string}"

        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                body = resp.read().decode()
                items = self._parse_items(body)
                return SearchResponse(
                    status_code=resp.status,
                    items=items,
                    raw_body=body,
                )
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            return SearchResponse(
                status_code=exc.code,
                items=[],
                raw_body=body,
            )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_items(body: str) -> list[SearchResult]:
        """Parse a JSON array of video cards into SearchResult objects."""
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        results = []
        for item in data:
            if not isinstance(item, dict):
                continue
            results.append(
                SearchResult(
                    id=item.get("id", ""),
                    title=item.get("title", ""),
                    thumbnail_url=item.get("thumbnail_url"),
                    view_count=item.get("view_count", 0),
                    uploader_username=item.get("uploader_username", ""),
                    created_at=item.get("created_at", ""),
                )
            )
        return results


# urllib.parse is used in search(); import at module level to avoid repeated lookups.
import urllib.parse  # noqa: E402 (import not at top of file — intentional grouping)
