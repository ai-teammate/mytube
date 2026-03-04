"""Service object for the /api/playlists endpoints."""
import json
import urllib.request
import urllib.error
from typing import Optional


class PlaylistApiService:
    """Provides helpers for interacting with the playlists API.

    All HTTP details (headers, error handling) are encapsulated here.
    Tests receive only high-level action methods and typed return values.

    Usage::

        svc = PlaylistApiService(base_url="https://...", token=token)
        status, body = svc.create_playlist("My Workout Mix")
    """

    def __init__(self, base_url: str, token: Optional[str] = None):
        self._base_url = base_url.rstrip("/")
        self._token = token

    def create_playlist(self, title: str) -> tuple[int, str]:
        """Send POST /api/playlists with {title} and Bearer auth.

        Returns (status_code, response_body).
        """
        url = f"{self._base_url}/api/playlists"
        payload = json.dumps({"title": title}).encode("utf-8")
        headers: dict = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()
