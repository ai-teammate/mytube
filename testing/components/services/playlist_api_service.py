"""Service object for interacting with the /api/playlists/* endpoints."""
from testing.components.services.auth_service import AuthService


class PlaylistApiService:
    """Provides high-level methods for the playlist API endpoints.

    Authentication is delegated to the injected AuthService so that the
    caller controls which token is used without this class knowing about
    Firebase or environment variables.

    Usage::

        auth = AuthService(base_url="http://localhost:8080", token=token)
        svc = PlaylistApiService(auth)
        status, body = svc.delete_playlist("some-uuid")
    """

    def __init__(self, auth_service: AuthService) -> None:
        self._auth = auth_service

    def create_playlist(self, title: str) -> tuple[int, str]:
        """POST /api/playlists — create a new playlist."""
        return self._auth.post("/api/playlists", {"title": title})

    def get_playlist(self, playlist_id: str) -> tuple[int, str]:
        """GET /api/playlists/:id — fetch playlist details."""
        return self._auth.get(f"/api/playlists/{playlist_id}")

    def delete_playlist(self, playlist_id: str) -> tuple[int, str]:
        """DELETE /api/playlists/:id — delete a playlist (owner only)."""
        return self._auth.delete(f"/api/playlists/{playlist_id}")
