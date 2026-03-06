"""Service object for user-related HTTP operations against the MyTube REST API."""
from __future__ import annotations

import json
import urllib.request

from testing.core.config.api_config import APIConfig


class UserApiService:
    """Provides unauthenticated HTTP queries for user resources.

    Usage::

        svc = UserApiService(api_config)
        playlists = svc.get_user_playlists("tester")
    """

    def __init__(self, api_config: APIConfig) -> None:
        self._base_url = api_config.base_url.rstrip("/")

    def get_user_playlists(self, username: str) -> list:
        """Return public playlists for *username* via GET /api/users/:username/playlists.

        Returns an empty list on any HTTP error or malformed response.
        """
        url = f"{self._base_url}/api/users/{username}/playlists"
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
                data = json.loads(resp.read().decode())
                return data if isinstance(data, list) else []
        except Exception:
            return []
