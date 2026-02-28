"""Service object for inserting and querying user rows."""


class UserService:
    """Provides user row operations against a live PostgreSQL database."""

    def __init__(self, conn):
        self._conn = conn

    def create_user(self, firebase_uid: str, username: str) -> str:
        """Insert a user row and return its id as a string."""
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) RETURNING id",
                (firebase_uid, username),
            )
            return str(cur.fetchone()[0])
