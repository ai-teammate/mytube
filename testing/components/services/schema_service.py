"""Service object for querying PostgreSQL schema metadata."""
from typing import Optional, Union
import psycopg2
import psycopg2.extras
from psycopg2 import sql


class SchemaService:
    """Provides schema inspection methods against a live PostgreSQL database.

    Can be instantiated with either a live connection object or a ``DBConfig``
    instance.  When a ``DBConfig`` is supplied the service opens and owns the
    connection; call :meth:`close` (or use it as a context manager) to release
    it when done.
    """

    def __init__(self, conn_or_config):
        # Lazy import to avoid a hard dependency in callers that already hold a
        # connection.
        from testing.core.config.db_config import DBConfig  # noqa: PLC0415

        if isinstance(conn_or_config, DBConfig):
            self._conn = psycopg2.connect(conn_or_config.dsn())
            self._conn.autocommit = True
            self._owns_connection = True
        else:
            self._conn = conn_or_config
            self._owns_connection = False

    # ------------------------------------------------------------------
    # Context-manager support
    # ------------------------------------------------------------------

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        """Close the underlying connection if this service owns it."""
        if self._owns_connection and not self._conn.closed:
            self._conn.close()

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

    def function_exists(self, function_name: str, schema: str = "public") -> bool:
        """Return True if a function with *function_name* exists in *schema*."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = %s
                      AND p.proname = %s
                )
                """,
                (schema, function_name),
            )
            return cur.fetchone()[0]

    def public_table_count(self) -> int:
        """Return the number of user-defined tables in the public schema."""
        with self._conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM pg_tables WHERE schemaname = 'public'"
            )
            return cur.fetchone()[0]

    def drop_all_public_tables(self) -> None:
        """Drop all user-defined tables in the public schema and the set_updated_at function."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                DO $$ DECLARE
                    r RECORD;
                BEGIN
                    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                        EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                    END LOOP;
                END $$;
                """
            )
            cur.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE;")

    def get_index_access_method(self, index_name: str) -> Optional[str]:
        """Return the access method name (e.g. 'gin', 'btree') for *index_name*, or None."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT am.amname
                FROM pg_indexes pi
                JOIN pg_class c ON c.relname = pi.indexname
                JOIN pg_am    am ON am.oid    = c.relam
                WHERE pi.indexname = %s
                """,
                (index_name,),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def apply_sql_file(self, path: str) -> None:
        """Read and execute a SQL file against the database."""
        with open(path, "r") as f:
            sql = f.read()
        with self._conn.cursor() as cur:
            cur.execute(sql)

    def index_exists(self, index_name: str, table_name: str | None = None) -> bool:
        """Return True if the named index exists in the public schema."""
        with self._conn.cursor() as cur:
            if table_name:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname = %s AND tablename = %s)",
                    (index_name, table_name),
                )
            else:
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_indexes "
                    "WHERE schemaname = 'public' AND indexname = %s)",
                    (index_name,),
                )
            return cur.fetchone()[0]

    def index_access_method(self, index_name: str) -> str | None:
        """Return the lowercase access method (e.g. 'gin', 'btree') for the index."""
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT am.amname
                FROM pg_index idx
                JOIN pg_class ci ON ci.oid = idx.indexrelid
                JOIN pg_am    am ON am.oid = ci.relam
                JOIN pg_namespace ns ON ns.oid = ci.relnamespace
                WHERE ns.nspname = 'public' AND ci.relname = %s
                """,
                (index_name,),
            )
            row = cur.fetchone()
            return row[0].lower() if row else None

    def count_rows(self, table_name: str) -> int:
        """Return the number of rows in the given table."""
        with self._conn.cursor() as cur:
            cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(table_name)))
            return cur.fetchone()[0]
