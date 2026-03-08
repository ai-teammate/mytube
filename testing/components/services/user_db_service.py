"""Service component for user/video database operations via psycopg2."""
from __future__ import annotations

from testing.core.config.db_config import DBConfig


class UserDbService:
    """Encapsulates psycopg2-based DB access for user and video records.

    Usage::

        svc = UserDbService(db_config)
        if svc.connect():
            svc.delete_user_by_firebase_uid(uid)
            row = svc.get_user_by_firebase_uid(uid)
            svc.close()
    """

    def __init__(self, db_config: DBConfig) -> None:
        self._db_config = db_config
        self._conn = None

    def connect(self) -> bool:
        """Open a database connection. Returns True on success, False otherwise."""
        try:
            import psycopg2  # noqa: PLC0415
            self._conn = psycopg2.connect(self._db_config.dsn())
            return True
        except Exception:
            return False

    def delete_user_by_firebase_uid(self, firebase_uid: str) -> None:
        """Delete a user (and their videos) identified by *firebase_uid*.

        Deletes child video rows first to satisfy FK constraints, then removes
        the user row.  Raises if the connection is not open.
        """
        with self._conn:
            with self._conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM videos WHERE user_id = (SELECT id FROM users WHERE firebase_uid = %s)",
                    (firebase_uid,),
                )
                cur.execute(
                    "DELETE FROM users WHERE firebase_uid = %s",
                    (firebase_uid,),
                )

    def get_user_by_firebase_uid(self, firebase_uid: str):
        """Return the ``(id, firebase_uid)`` row for *firebase_uid*, or None."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, firebase_uid FROM users WHERE firebase_uid = %s",
                (firebase_uid,),
            )
            return cur.fetchone()

    def get_video_by_id(self, video_id: str):
        """Return the ``(id, title)`` row for *video_id*, or None."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, title FROM videos WHERE id = %s",
                (video_id,),
            )
            return cur.fetchone()

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
