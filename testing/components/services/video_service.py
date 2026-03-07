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

    def insert_video_with_details(
        self,
        uploader_id: str,
        title: str,
        description: str,
        status: str,
        tags: list[str],
    ) -> str:
        """Insert a video with description and tags; return the video id as a string."""
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO videos (uploader_id, title, description, status) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (uploader_id, title, description, status),
            )
            video_id = str(cur.fetchone()[0])
        for tag in tags:
            with self._conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO video_tags (video_id, tag) VALUES (%s, %s)",
                    (video_id, tag),
                )
        return video_id

    def get_video_by_id(self, video_id: str) -> dict | None:
        """Return status, hls_manifest_path, and thumbnail_url for a video row."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT status, hls_manifest_path, thumbnail_url FROM videos WHERE id = %s",
                (video_id,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {"status": row[0], "hls_manifest_path": row[1], "thumbnail_url": row[2]}

    def count_ready_videos(self, uploader_id: str) -> int:
        """Return the number of videos with status 'ready' for the given uploader."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM videos WHERE uploader_id = %s AND status = 'ready'",
                (uploader_id,),
            )
            return cur.fetchone()[0]
