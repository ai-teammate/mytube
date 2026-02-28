"""Service object for querying PostgreSQL schema metadata."""
from typing import Optional
import psycopg2
import psycopg2.extras


class SchemaService:
    """Provides schema inspection methods against a live PostgreSQL database."""

    def __init__(self, conn):
        self._conn = conn

    def table_exists(self, table_name: str) -> bool:
        """Return True if the named table exists in the public schema."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = %s
                )
                """,
                (table_name,),
            )
            return cur.fetchone()[0]

    def get_columns(self, table_name: str) -> list[dict]:
        """Return column metadata for the given table."""
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    column_name,
                    data_type,
                    udt_name,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_column(self, table_name: str, column_name: str) -> Optional[dict]:
        """Return metadata for a single column, or None if not found."""
        cols = self.get_columns(table_name)
        for col in cols:
            if col["column_name"] == column_name:
                return col
        return None

    def get_primary_keys(self, table_name: str) -> list[str]:
        """Return the list of column names that form the primary key."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema   = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema    = 'public'
                  AND tc.table_name      = %s
                ORDER BY kcu.ordinal_position
                """,
                (table_name,),
            )
            return [row[0] for row in cur.fetchall()]

    def get_foreign_keys(self, table_name: str) -> list[dict]:
        """Return FK metadata for the given table."""
        with self._conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT
                    kcu.column_name          AS column_name,
                    ccu.table_name           AS foreign_table,
                    ccu.column_name          AS foreign_column,
                    rc.delete_rule           AS on_delete
                FROM information_schema.table_constraints        tc
                JOIN information_schema.key_column_usage         kcu
                    ON tc.constraint_name = kcu.constraint_name
                   AND tc.table_schema   = kcu.table_schema
                JOIN information_schema.referential_constraints  rc
                    ON tc.constraint_name = rc.constraint_name
                   AND tc.table_schema   = rc.constraint_schema
                JOIN information_schema.constraint_column_usage  ccu
                    ON rc.unique_constraint_name   = ccu.constraint_name
                   AND rc.unique_constraint_schema = ccu.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema    = 'public'
                  AND tc.table_name      = %s
                ORDER BY kcu.column_name
                """,
                (table_name,),
            )
            return [dict(row) for row in cur.fetchall()]

    def column_default_contains(self, table_name: str, column_name: str, substring: str) -> bool:
        """Return True if the column's DEFAULT expression contains the given substring."""
        col = self.get_column(table_name, column_name)
        if col is None or col.get("column_default") is None:
            return False
        return substring.lower() in col["column_default"].lower()
