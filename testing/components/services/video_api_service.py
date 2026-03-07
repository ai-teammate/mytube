"""HTTP API service for querying video and user resources."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Optional

from testing.core.config.api_config import APIConfig


class VideoApiService:
    """Provides HTTP-level queries against the MyTube REST API.

    Used by tests that need to discover video metadata (id, status,
    hls_manifest_url) without direct database access.

    Usage::

        svc = VideoApiService(api_config)
        result = svc.find_ready_video(override_id="...")
        if result is None:
            pytest.skip("No ready video found.")
        video_id, hls_url = result
    """

    _CANDIDATE_USERNAMES = ["tester", "testuser", "alice", "admin"]

    def __init__(self, api_config: APIConfig) -> None:
        self._base_url = api_config.base_url.rstrip("/")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_video(self, video_id: str) -> Optional[dict]:
        """Return the video detail dict for *video_id*, or None on error."""
        return self._fetch_json(f"{self._base_url}/api/videos/{video_id}")

    def get_user(self, username: str) -> Optional[dict]:
        """Return the user detail dict for *username*, or None on error."""
        return self._fetch_json(f"{self._base_url}/api/users/{username}")

    def find_ready_video(
        self, override_id: str = ""
    ) -> tuple[str, Optional[str]] | None:
        """Return (video_id, hls_manifest_url) for the first ready video found, or None.

        Strategy:
        1. If *override_id* is provided, fetch that video directly and return it
           if its status is 'ready'.  Returns None otherwise.
        2. Otherwise, query a set of known CI usernames and return the first
           video whose status is 'ready'.  Returns None if none found.

        The caller (fixture layer) is responsible for calling pytest.skip()
        when this returns None.
        """
        if override_id:
            data = self.get_video(override_id)
            if data and data.get("status") == "ready":
                return data["id"], data.get("hls_manifest_url")
            return None

        for username in self._CANDIDATE_USERNAMES:
            user = self.get_user(username)
            if not user:
                continue
            for v in user.get("videos", []):
                vid_id = v.get("id") or v.get("video_id")
                if not vid_id:
                    continue
                detail = self.get_video(vid_id)
                if detail and detail.get("status") == "ready":
                    return detail["id"], detail.get("hls_manifest_url")

        return None

    def get_video_detail(self, video_id: str) -> tuple[int, dict | None]:
        """GET /api/videos/:id and return (status_code, body_dict).

        Returns (200, dict) on success.
        Returns (status_code, None) when the response is not a JSON object.
        Returns (0, None) when the host is unreachable.
        """
        url = f"{self._base_url}/api/videos/{video_id}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = resp.read().decode()
                data = json.loads(body)
                return resp.status, data if isinstance(data, dict) else None
        except urllib.error.HTTPError as exc:
            return exc.code, None
        except Exception:
            return 0, None

    def find_video_without_category(self) -> str | None:
        """Return the ID of the first video whose category_id is null, or None.

        Strategy:
        1. Fetch recent videos (up to 50) and retrieve full detail for each to
           inspect category_id.
        2. Fall back to iterating known CI usernames if no suitable video is
           found in recent results.

        The caller is responsible for calling pytest.skip() when this returns None.
        """
        # Try recent videos first
        _, recent = self.get_recent_videos(limit=50)
        if recent:
            for item in recent:
                vid_id = item.get("id") or item.get("video_id")
                if not vid_id:
                    continue
                _status, detail = self.get_video_detail(vid_id)
                if detail is not None and detail.get("category_id") is None:
                    return vid_id

        # Fallback: iterate known CI usernames
        for username in self._CANDIDATE_USERNAMES:
            user = self.get_user(username)
            if not user:
                continue
            for v in user.get("videos", []):
                vid_id = v.get("id") or v.get("video_id")
                if not vid_id:
                    continue
                _status, detail = self.get_video_detail(vid_id)
                if detail is not None and detail.get("category_id") is None:
                    return vid_id

        return None

    def get_recent_videos(self, limit: int = 20) -> tuple[int, list[dict] | None]:
        """GET /api/videos/recent?limit=*limit* and return (status_code, videos).

        Returns (0, []) when the host is unreachable.
        Returns (status_code, None) when the response is not a JSON array.
        """
        url = f"{self._base_url}/api/videos/recent?limit={limit}"
        return self._fetch_list(url)

    def get_popular_videos(self, limit: int = 20) -> tuple[int, list[dict] | None]:
        """GET /api/videos/popular?limit=*limit* and return (status_code, videos).

        Returns (0, []) when the host is unreachable.
        Returns (status_code, None) when the response is not a JSON array.
        """
        url = f"{self._base_url}/api/videos/popular?limit={limit}"
        return self._fetch_list(url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_json(self, url: str) -> Optional[dict]:
        """GET *url* and return parsed JSON body, or None on any error."""
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                return json.loads(resp.read().decode())
        except Exception:
            return None

    def _fetch_list(self, url: str) -> tuple[int, list[dict] | None]:
        """GET *url* and return (status_code, parsed_json_list).

        Returns (status_code, None) when the response is not a JSON array.
        Returns (status_code, []) on HTTP error or JSON parse failure.
        Returns (0, []) when the host is unreachable.
        """
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                body = resp.read().decode()
                data = json.loads(body)
                return resp.status, data if isinstance(data, list) else None
        except urllib.error.HTTPError as exc:
            return exc.code, []
        except Exception:
            return 0, []
