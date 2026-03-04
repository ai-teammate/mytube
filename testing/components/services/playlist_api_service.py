"""Service object for the /api/playlists endpoints."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlaylistVideoItem:
    """A single video entry inside a playlist detail response."""

    id: str
    title: str
    thumbnail_url: Optional[str]
    position: int


@dataclass
class PlaylistDetailResponse:
    """Structured result of GET /api/playlists/:id."""

    status_code: int
    raw_body: str
    id: str = ""
    title: str = ""
    owner_username: str = ""
    videos: list[PlaylistVideoItem] = field(default_factory=list)

    @property
    def video_ids(self) -> list[str]:
        """Return the list of video IDs in the playlist."""
        return [v.id for v in self.videos]


class PlaylistApiService:
    """Provides HTTP operations for the /api/playlists endpoints.

    All HTTP-level concerns (headers, error handling) are encapsulated here.
    Tests interact only with high-level action methods and typed responses.

    Usage::

        svc = PlaylistApiService(
            base_url="https://mytube-api-80693608388.us-central1.run.app",
            token=os.getenv("FIREBASE_TEST_TOKEN"),
        )
        status, body = svc.remove_video(playlist_id, video_id)
        response = svc.get_playlist(playlist_id)
    """

    def __init__(self, base_url: str, token: Optional[str] = None) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    def _auth_headers(self) -> dict:
        headers: dict = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def get_playlist(self, playlist_id: str) -> PlaylistDetailResponse:
        """GET /api/playlists/:id — returns a PlaylistDetailResponse.

        This is a public endpoint; no auth token is required.
        """
        url = f"{self._base_url}/api/playlists/{playlist_id}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                body = resp.read().decode()
                return self._parse_detail(resp.status, body)
        except urllib.error.HTTPError as exc:
            return PlaylistDetailResponse(
                status_code=exc.code,
                raw_body=exc.read().decode(),
            )

    def remove_video(self, playlist_id: str, video_id: str) -> tuple[int, str]:
        """DELETE /api/playlists/:id/videos/:video_id with Bearer auth.

        Returns (status_code, response_body).
        Expects HTTP 200 or 204 on success.
        """
        url = f"{self._base_url}/api/playlists/{playlist_id}/videos/{video_id}"
        req = urllib.request.Request(
            url, method="DELETE", headers=self._auth_headers()
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_detail(status_code: int, body: str) -> PlaylistDetailResponse:
        """Parse a GET /api/playlists/:id JSON response."""
        try:
            data = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return PlaylistDetailResponse(status_code=status_code, raw_body=body)

        if not isinstance(data, dict):
            return PlaylistDetailResponse(status_code=status_code, raw_body=body)

        videos: list[PlaylistVideoItem] = []
        for v in data.get("videos") or []:
            if isinstance(v, dict):
                videos.append(
                    PlaylistVideoItem(
                        id=v.get("id", ""),
                        title=v.get("title", ""),
                        thumbnail_url=v.get("thumbnail_url"),
                        position=v.get("position", 0),
                    )
                )

        return PlaylistDetailResponse(
            status_code=status_code,
            raw_body=body,
            id=data.get("id", ""),
            title=data.get("title", ""),
            owner_username=data.get("owner_username", ""),
            videos=videos,
        )
