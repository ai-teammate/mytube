"""Service object for inserting and querying comment rows."""
from datetime import datetime, timedelta, timezone
from typing import Optional


class CommentService:
    """Provides comment row operations against a live PostgreSQL database."""

    def __init__(self, conn):
        self._conn = conn

    def insert_comment(
        self,
        video_id: str,
        author_id: str,
        body: str,
        created_at: Optional[datetime] = None,
    ) -> str:
        """Insert a comment row and return its id as a string."""
        with self._conn.cursor() as cur:
            if created_at is not None:
                cur.execute(
                    "INSERT INTO comments (video_id, author_id, body, created_at) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (video_id, author_id, body, created_at),
                )
            else:
                cur.execute(
                    "INSERT INTO comments (video_id, author_id, body) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (video_id, author_id, body),
                )
            return str(cur.fetchone()[0])

    def insert_bulk_comments(
        self,
        video_id: str,
        author_id: str,
        count: int,
        base_time: datetime,
    ) -> list[str]:
        """Insert *count* comments with 1-second-apart timestamps starting at *base_time*.

        Returns the list of inserted comment ids in insertion order
        (index 0 = oldest, index count-1 = newest).
        """
        ids = []
        for i in range(count):
            ts = base_time + timedelta(seconds=i)
            comment_id = self.insert_comment(video_id, author_id, f"Comment number {i}", ts)
            ids.append(comment_id)
        return ids
