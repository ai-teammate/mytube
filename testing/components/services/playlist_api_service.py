"""Service object for playlist-related HTTP operations against the MyTube REST API."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PlaylistVideo:
    """A video entry within a playlist, as returned by GET /api/playlists/:id."""

    id: str
    title: str
    thumbnail_url: Optional[str]
    position: int


@dataclass
class PlaylistDetail:
    """Full playlist with videos, as returned by GET /api/playlists/:id."""

    id: str
    title: str
    owner_username: str
    videos: list[PlaylistVideo] = field(default_factory=list)

    @property
    def max_position(self) -> int:
        """Return the maximum position value across all videos, or 0 if empty."""
        if not self.videos:
            return 0
        return max(v.position for v in self.videos)


class PlaylistApiService:
    """Provides HTTP operations for the /api/playlists endpoints.

    Encapsulates playlist creation, video management, and retrieval with
    Bearer token authentication where required.

    Usage::

        svc = PlaylistApiService(
            base_url="https://mytube-api-80693608388.us-central1.run.app",
            token=os.getenv("FIREBASE_TEST_TOKEN"),
        )
        status, body = svc.create_playlist("My Test Playlist")
        assert status == 201
    """

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    # -------------------------------------------------------------------------
    # Authenticated mutations
    # -------------------------------------------------------------------------

    def create_playlist(self, title: str) -> tuple[int, str]:
        """POST /api/playlists — create a new playlist owned by the authenticated user.

        Returns (status_code, raw_body).
        """
        url = f"{self._base_url}/api/playlists"
        payload = json.dumps({"title": title}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def add_video(self, playlist_id: str, video_id: str) -> tuple[int, str]:
        """POST /api/playlists/:id/videos — add a video to the playlist.

        The system appends the video at position max(current_positions) + 1.
        Returns (status_code, raw_body).
        """
        url = f"{self._base_url}/api/playlists/{playlist_id}/videos"
        payload = json.dumps({"video_id": video_id}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def delete_playlist(self, playlist_id: str) -> tuple[int, str]:
        """DELETE /api/playlists/:id — remove the playlist (owner only).

        Returns (status_code, raw_body).
        """
        url = f"{self._base_url}/api/playlists/{playlist_id}"
        headers = {"Authorization": f"Bearer {self._token}"}
        req = urllib.request.Request(url, method="DELETE", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    # -------------------------------------------------------------------------
    # Public reads (no token required)
    # -------------------------------------------------------------------------

    def get_playlist(self, playlist_id: str) -> tuple[int, Optional[PlaylistDetail]]:
        """GET /api/playlists/:id — fetch a playlist with its videos.

        Returns (status_code, PlaylistDetail) on success, or (status_code, None) on error.
        """
        url = f"{self._base_url}/api/playlists/{playlist_id}"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode()
                data = json.loads(body)
                return resp.status, self._parse_detail(data)
        except urllib.error.HTTPError as exc:
            return exc.code, None
        except (json.JSONDecodeError, KeyError, TypeError):
            return 0, None

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_detail(data: dict) -> PlaylistDetail:
        """Parse a raw dict into a PlaylistDetail dataclass."""
        videos = [
            PlaylistVideo(
                id=v["id"],
                title=v["title"],
                thumbnail_url=v.get("thumbnail_url"),
                position=v["position"],
            )
            for v in data.get("videos", [])
        ]
        return PlaylistDetail(
            id=data["id"],
            title=data["title"],
            owner_username=data["owner_username"],
            videos=videos,
        )
