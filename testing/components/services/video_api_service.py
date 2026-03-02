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
        video_id, hls_url = svc.find_ready_video(override_id="...")
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
    ) -> tuple[str, Optional[str]]:
        """Return (video_id, hls_manifest_url) for the first ready video found.

        Strategy:
        1. If *override_id* is provided, fetch that video directly and return it
           if its status is 'ready'.  Raises ``pytest.skip`` otherwise.
        2. Otherwise, query a set of known CI usernames and return the first
           video whose status is 'ready'.  Raises ``pytest.skip`` if none found.
        """
        import pytest  # imported here to keep the service pytest-agnostic at module level

        if override_id:
            data = self.get_video(override_id)
            if data and data.get("status") == "ready":
                return data["id"], data.get("hls_manifest_url")
            pytest.skip(
                f"Video ID {override_id!r} not found or not ready. Response: {data}"
            )

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

        pytest.skip(
            "No ready video found via API. "
            "Set MYTUBE_146_VIDEO_ID to a valid video UUID with status='ready', "
            "or ensure a ready video exists for a known test user."
        )

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
