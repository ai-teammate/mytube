"""Service object for playlist-related HTTP operations against the MyTube REST API."""
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


# Alias — PlaylistVideo is the name used by some tests.
PlaylistVideo = PlaylistVideoItem


@dataclass
class PlaylistDetailResponse:
    """Structured result of GET /api/playlists/:id.

    Supports both attribute-style access and tuple-style unpacking::

        # Attribute access (MYTUBE-235 style):
        result = svc.get_playlist(pid)
        assert result.status_code == 200
        assert video_id not in result.video_ids

        # Tuple unpacking (MYTUBE-228 style):
        status, detail = svc.get_playlist(pid)
        assert status == 200
        assert detail is not None
    """

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

    @property
    def max_position(self) -> int:
        """Return the maximum position across all videos, or 0 if the playlist is empty."""
        if not self.videos:
            return 0
        return max(v.position for v in self.videos)

    def __iter__(self):
        """Support tuple-style unpacking: ``status, detail = svc.get_playlist(id)``.

        Yields (status_code, self) when the playlist was successfully parsed
        (i.e. ``self.id`` is non-empty), or (status_code, None) otherwise,
        matching the behaviour of the previous ``(int, Optional[PlaylistDetail])``
        return signature.
        """
        yield self.status_code
        yield self if self.id else None


# Backward-compatible alias used by tests that import PlaylistDetail.
PlaylistDetail = PlaylistDetailResponse


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

    # -------------------------------------------------------------------------
    # Authenticated mutations
    # -------------------------------------------------------------------------

    def create_playlist(self, title: str) -> tuple[int, str]:
        """Send POST /api/playlists with {title} and Bearer auth.

        Returns (status_code, raw_body).
        """
        url = f"{self._base_url}/api/playlists"
        payload = json.dumps({"title": title}).encode("utf-8")
        headers: dict = {"Content-Type": "application/json"}
        headers.update(self._auth_headers())
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
        headers: dict = {"Content-Type": "application/json"}
        headers.update(self._auth_headers())
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
        req = urllib.request.Request(url, method="DELETE", headers=self._auth_headers())
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

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

    # -------------------------------------------------------------------------
    # Public reads (no token required)
    # -------------------------------------------------------------------------

    def get_playlist(self, playlist_id: str) -> PlaylistDetailResponse:
        """GET /api/playlists/:id — returns a PlaylistDetailResponse.

        This is a public endpoint; no auth token is required.

        The return value supports both attribute access and tuple unpacking::

            # Attribute access:
            result = svc.get_playlist(pid)
            result.status_code, result.video_ids

            # Tuple unpacking (backward compat with MYTUBE-228 style):
            status, detail = svc.get_playlist(pid)  # detail is self or None
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

    def is_reachable(self, timeout: int = 5) -> bool:
        """Return True if the API server responds to the health endpoint."""
        health_url = f"{self._base_url}/health"
        try:
            with urllib.request.urlopen(health_url, timeout=timeout):
                return True
        except Exception:
            return False

    def get_with_origin_header(
        self, playlist_id: str, origin: str, timeout: int = 15
    ) -> tuple[int, dict]:
        """GET /api/playlists/:id with an Origin header for CORS verification.

        Returns (status_code, response_headers) where all header names are
        lower-cased for case-insensitive comparison.
        """
        url = f"{self._base_url}/api/playlists/{playlist_id}"
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"Origin": origin},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return resp.status, headers
        except urllib.error.HTTPError as exc:
            headers = {k.lower(): v for k, v in exc.headers.items()}
            return exc.code, headers

    def get_user_playlists(self, username: str) -> tuple[int, list]:
        """GET /api/users/<username>/playlists — fetch public playlists for a user.

        No authentication token is required for this endpoint.

        Returns (status_code, playlists) where playlists is a list of playlist
        dicts (possibly empty for a user with no public playlists).
        Returns (http_error_code, []) on HTTP errors, or (0, []) on network failure.
        """
        url = f"{self._base_url}/api/users/{username}/playlists"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                return resp.status, (data if isinstance(data, list) else [])
        except urllib.error.HTTPError as exc:
            return exc.code, []
        except Exception:
            return 0, []

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

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
