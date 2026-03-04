"""Service object for inserting and querying playlist rows."""


class PlaylistService:
    """Provides playlist row operations against a live PostgreSQL database."""

    def __init__(self, conn) -> None:
        self._conn = conn

    def create_playlist(self, owner_id: str, title: str) -> str:
        """Insert a playlist row and return its id as a string."""
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO playlists (owner_id, title) VALUES (%s, %s) RETURNING id",
                (owner_id, title),
            )
            return str(cur.fetchone()[0])

    def add_video(self, playlist_id: str, video_id: str, position: int) -> None:
        """Insert a playlist_videos row with an explicit position."""
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO playlist_videos (playlist_id, video_id, position) "
                "VALUES (%s, %s, %s)",
                (playlist_id, video_id, position),
            )

    def get_video_ids_ordered(self, playlist_id: str) -> list[str]:
        """Return video IDs for the playlist sorted by position ascending."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT video_id FROM playlist_videos "
                "WHERE playlist_id = %s ORDER BY position ASC",
                (playlist_id,),
            )
            return [str(row[0]) for row in cur.fetchall()]
