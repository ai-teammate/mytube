"""Service object for querying the categories table."""


class CategoryService:
    """Provides category-related query methods against a live PostgreSQL database."""

    def __init__(self, conn):
        self._conn = conn

    def get_category_count(self) -> int:
        """Return the total number of rows in the categories table."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM categories;")
            return cur.fetchone()[0]

    def get_category_names(self) -> list[str]:
        """Return category names ordered alphabetically."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT name FROM categories ORDER BY name ASC;")
            return [row[0] for row in cur.fetchall()]

    def category_exists(self, name: str) -> bool:
        """Return True if a category with the given name exists."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM categories WHERE name = %s;",
                (name,),
            )
            return cur.fetchone()[0] == 1

    def get_first_id(self) -> int | None:
        """Return the id of the first category row, or None if the table is empty."""
        with self._conn.cursor() as cur:
            cur.execute("SELECT id FROM categories ORDER BY id LIMIT 1")
            row = cur.fetchone()
        return row[0] if row else None

    def insert_category(self, name: str) -> int:
        """Insert a new category and return its id."""
        with self._conn.cursor() as cur:
            cur.execute(
                "INSERT INTO categories (name) VALUES (%s) RETURNING id",
                (name,),
            )
            return cur.fetchone()[0]

    def apply_seed(self, sql_path: str) -> None:
        """Execute a seed SQL file against the database."""
        with open(sql_path, "r") as fh:
            sql = fh.read()
        with self._conn.cursor() as cur:
            cur.execute(sql)
