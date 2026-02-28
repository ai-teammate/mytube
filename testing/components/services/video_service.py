"""Service object for inserting and querying video rows."""


class VideoService:
    """Provides video row operations against a live PostgreSQL database."""

    def __init__(self, conn):
        self._conn = conn

    def insert_video(self, uploader_id: str, title: str, status: str):
        """Insert a video row and return (id, status). Raises on constraint violation."""
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO videos (uploader_id, title, status) VALUES (%s, %s, %s) RETURNING id, status",
                (uploader_id, title, status),
            )
            return cur.fetchone()
