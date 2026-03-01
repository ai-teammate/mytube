"""Service component for inserting and querying rows in the ratings table."""
from typing import Optional

import psycopg2.errors


class RatingsService:
    """Encapsulates all SQL operations against the 'ratings' table."""

    def __init__(self, conn):
        self._conn = conn

    def insert_rating(self, video_id: str, user_id: str, stars: int) -> None:
        """Insert a row into the ratings table.

        Raises psycopg2.errors.CheckViolation if *stars* violates the
        CHECK (stars BETWEEN 1 AND 5) constraint.
        """
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO ratings (video_id, user_id, stars) VALUES (%s, %s, %s)",
                (video_id, user_id, stars),
            )

    def get_rating(self, video_id: str, user_id: str) -> Optional[int]:
        """Return the stars value for the given (video_id, user_id) pair, or None."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT stars FROM ratings WHERE video_id = %s AND user_id = %s",
                (video_id, user_id),
            )
            row = cur.fetchone()
        return row[0] if row is not None else None
