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

    def find_by_firebase_uid(self, firebase_uid: str) -> dict | None:
        """Return a dict with id, firebase_uid, and username for the given UID, or None."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT id, firebase_uid, username FROM users WHERE firebase_uid = %s",
                (firebase_uid,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        return {"id": str(row[0]), "firebase_uid": row[1], "username": row[2]}
