"""HTTP service for querying the category browse API endpoint."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional

from testing.core.config.api_config import APIConfig


@dataclass
class VideoCard:
    """Represents a video card returned by the browse/search API."""

    id: str
    title: str
    thumbnail_url: Optional[str]
    view_count: int
    uploader_username: str
    created_at: str


@dataclass
class CategoryBrowseResponse:
    """Result of a GET /api/videos?category_id=<id> request."""

    status_code: int
    videos: list[VideoCard]
    raw_body: str
    error_message: Optional[str]


@dataclass
class CategoryInfo:
    """Represents a category from GET /api/categories."""

    id: int
    name: str


class CategoryBrowseService:
    """Queries the category browse endpoint and /api/categories.

    Usage::

        svc = CategoryBrowseService(api_config)
        result = svc.get_videos_by_category(category_id=3, limit=20)
        categories = svc.get_all_categories()
    """

    def __init__(self, api_config: APIConfig) -> None:
        self._base_url = api_config.base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_videos_by_category(
        self, category_id: int, limit: int = 20, offset: int = 0
    ) -> CategoryBrowseResponse:
        """GET /api/videos?category_id=<id>&limit=<limit>&offset=<offset>.

        Returns a :class:`CategoryBrowseResponse` with the parsed list of
        video cards (or an error).  Never raises; errors are captured in the
        response object.
        """
        url = (
            f"{self._base_url}/api/videos"
            f"?category_id={category_id}&limit={limit}&offset={offset}"
        )
        return self._fetch_browse(url)

    def get_videos_no_category(self) -> CategoryBrowseResponse:
        """GET /api/videos without category_id — expects 400."""
        url = f"{self._base_url}/api/videos"
        return self._fetch_browse(url)

    def get_videos_with_invalid_category(self, invalid_id: str) -> CategoryBrowseResponse:
        """GET /api/videos?category_id=<invalid> — expects 400."""
        url = f"{self._base_url}/api/videos?category_id={invalid_id}"
        return self._fetch_browse(url)

    def get_all_categories(self) -> list[CategoryInfo]:
        """GET /api/categories and return parsed list of categories."""
        url = f"{self._base_url}/api/categories"
        raw = self._fetch_raw(url)
        if raw is None:
            return []
        try:
            data = json.loads(raw)
            return [CategoryInfo(id=c["id"], name=c["name"]) for c in data]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_browse(self, url: str) -> CategoryBrowseResponse:
        """Issue GET *url* and parse the VideoCard array response."""
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=15) as resp:
                status_code: int = resp.status
                raw_body = resp.read().decode()
        except urllib.error.HTTPError as exc:
            raw_body = exc.read().decode() if exc.fp else ""
            try:
                err_data = json.loads(raw_body)
                error_message = err_data.get("error", raw_body)
            except Exception:
                error_message = raw_body
            return CategoryBrowseResponse(
                status_code=exc.code,
                videos=[],
                raw_body=raw_body,
                error_message=error_message,
            )
        except Exception as exc:
            return CategoryBrowseResponse(
                status_code=0,
                videos=[],
                raw_body="",
                error_message=str(exc),
            )

        try:
            data = json.loads(raw_body)
            videos = [
                VideoCard(
                    id=v["id"],
                    title=v["title"],
                    thumbnail_url=v.get("thumbnail_url"),
                    view_count=v.get("view_count", 0),
                    uploader_username=v.get("uploader_username", ""),
                    created_at=v.get("created_at", ""),
                )
                for v in data
            ]
            return CategoryBrowseResponse(
                status_code=status_code,
                videos=videos,
                raw_body=raw_body,
                error_message=None,
            )
        except Exception as exc:
            return CategoryBrowseResponse(
                status_code=status_code,
                videos=[],
                raw_body=raw_body,
                error_message=f"Failed to parse response: {exc}",
            )

    def _fetch_raw(self, url: str) -> Optional[str]:
        """GET *url* and return raw response body, or None on error."""
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                return resp.read().decode()
        except Exception:
            return None
