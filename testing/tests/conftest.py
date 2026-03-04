"""Shared pytest fixtures for all test modules under testing/tests/."""
import os
import sys
from typing import List, Optional

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from testing.core.config.db_config import DBConfig


def _cleanup_users(connection, usernames: List[str]) -> None:
    """Delete test data for the given usernames only.

    Deletes in FK-safe order (RESTRICT on uploader_id requires videos to be
    removed before the user row can be dropped):
      ratings, comments, video_tags → videos → playlists, playlist_videos → users

    Safe to call even if the tables or users do not yet exist.
    """
    if not usernames:
        return
    with connection.cursor() as cur:
        # Resolve user IDs first so we can use them across all owned tables.
        placeholders = ",".join(["%s"] * len(usernames))
        cur.execute(
            f"SELECT id FROM users WHERE username IN ({placeholders})",
            usernames,
        )
        user_ids = [row[0] for row in cur.fetchall()]
        if not user_ids:
            return

        id_placeholders = ",".join(["%s"] * len(user_ids))

        # Delete child rows that reference videos (FK CASCADE would handle
        # these if the FK were CASCADE, but we're being explicit).
        cur.execute(
            f"DELETE FROM ratings WHERE user_id IN ({id_placeholders})",
            user_ids,
        )
        cur.execute(
            f"DELETE FROM comments WHERE author_id IN ({id_placeholders})",
            user_ids,
        )
        # Delete ratings/comments on videos *owned* by these users too.
        cur.execute(
            f"""DELETE FROM ratings WHERE video_id IN (
                SELECT id FROM videos WHERE uploader_id IN ({id_placeholders})
            )""",
            user_ids,
        )
        cur.execute(
            f"""DELETE FROM comments WHERE video_id IN (
                SELECT id FROM videos WHERE uploader_id IN ({id_placeholders})
            )""",
            user_ids,
        )
        cur.execute(
            f"""DELETE FROM video_tags WHERE video_id IN (
                SELECT id FROM videos WHERE uploader_id IN ({id_placeholders})
            )""",
            user_ids,
        )
        cur.execute(
            f"""DELETE FROM playlist_videos WHERE playlist_id IN (
                SELECT id FROM playlists WHERE owner_id IN ({id_placeholders})
            )""",
            user_ids,
        )
        # Now it is safe to remove videos and playlists.
        cur.execute(
            f"DELETE FROM videos WHERE uploader_id IN ({id_placeholders})",
            user_ids,
        )
        cur.execute(
            f"DELETE FROM playlists WHERE owner_id IN ({id_placeholders})",
            user_ids,
        )
        # Finally remove the users themselves.
        cur.execute(
            f"DELETE FROM users WHERE id IN ({id_placeholders})",
            user_ids,
        )


def _apply_sql(connection, path: str) -> None:
    """Read a SQL file and execute it against the given connection."""
    with open(path, "r") as fh:
        sql = fh.read()
    with connection.cursor() as cur:
        cur.execute(sql)


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


def make_conn_fixture(
    migration_files: list[str],
    test_usernames: Optional[List[str]] = None,
):
    """Factory that returns a module-scoped ``conn`` fixture.

    Before the tests run, cleans up only the rows owned by *test_usernames*
    (setup isolation) and re-applies the given migration files so the schema
    is up-to-date.  After the tests finish the same usernames are cleaned up
    again (teardown isolation).

    Passing *test_usernames* is strongly preferred over the old drop-all
    behaviour: it scopes cleanup to just the test's own data and leaves all
    other rows (including data needed by other test cases) untouched.

    Usage::

        from testing.tests.conftest import make_conn_fixture

        conn = make_conn_fixture(
            migration_files=["/abs/path/to/0001_initial_schema.up.sql"],
            test_usernames=["testuser_iso_mytube80"],
        )
    """

    @pytest.fixture(scope="module")
    def conn(db_config: DBConfig):
        connection = psycopg2.connect(db_config.dsn())
        connection.autocommit = True
        # Pre-test cleanup: remove only this test's data so the run starts
        # from a known state without touching any other test's rows.
        _cleanup_users(connection, test_usernames or [])
        for path in migration_files:
            _apply_sql(connection, path)
        yield connection
        # Post-test cleanup: leave the DB tidy for the next run.
        _cleanup_users(connection, test_usernames or [])
        connection.close()

    return conn
