"""
MYTUBE-61: Authenticate with existing user — request succeeds without duplicate
record creation.

Objective:
    Verify that the auto-provisioning logic correctly handles users who already
    exist in the database by ignoring the insert conflict.

The auto-provisioning logic lives in repository.UserRepository.Upsert():

    INSERT INTO users (firebase_uid, username)
    VALUES ($1, $2)
    ON CONFLICT (firebase_uid) DO NOTHING

This DB-integration test exercises that SQL path directly:

1. A user record is pre-seeded into the users table (simulating the precondition
   that the user already exists).
2. The upsert SQL is executed multiple times for the same firebase_uid (simulating
   repeated authenticated requests to GET /api/me).
3. The test counts matching rows in the users table to confirm exactly one row
   remains — no duplicates.

Why DB-integration (not full server test):
    The test case's observable contract is database-level: "no duplicate records
    are created". The server-level behaviour (HTTP 200) is already covered by
    MYTUBE-30 (health/server start) and the Go unit tests in api/internal/. A
    direct DB-integration test is deterministic, fast, and does not require a
    live Firebase project or valid JWT tokens.
"""
import os
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIREBASE_UID = "test-uid-mytube-61-existing-user"
_EMAIL = "existing.user@example.com"
_USERNAME = "existing.user"  # email prefix of _EMAIL

# The upsert SQL mirroring api/internal/repository/user.go
_UPSERT_SQL = """
INSERT INTO users (firebase_uid, username)
VALUES (%s, %s)
ON CONFLICT (firebase_uid) DO NOTHING
"""

_COUNT_SQL = "SELECT COUNT(*) FROM users WHERE firebase_uid = %s"

# Number of times to repeat the upsert (simulates multiple authenticated requests)
_REPEAT_COUNT = 5


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def conn(db_config: DBConfig):
    """
    Open a connection, rebuild the schema from scratch, yield, then close.

    Module-scoped so all tests in this module share the same clean schema.
    """
    migration_sql_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "api", "migrations",
        "0001_initial_schema.up.sql",
    )

    connection = psycopg2.connect(db_config.dsn())
    connection.autocommit = True

    # Drop all public tables and functions for a clean slate.
    with connection.cursor() as cur:
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

    with open(migration_sql_path, "r") as fh:
        migration_sql = fh.read()
    with connection.cursor() as cur:
        cur.execute(migration_sql)

    yield connection

    connection.close()


@pytest.fixture(scope="module")
def pre_existing_user(conn) -> dict:
    """
    Pre-seed a user row that already exists in the database — the precondition
    described in the ticket.

    Returns a dict with 'firebase_uid', 'username', and 'id'.
    """
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) RETURNING id",
            (_FIREBASE_UID, _USERNAME),
        )
        user_id = str(cur.fetchone()[0])

    return {"id": user_id, "firebase_uid": _FIREBASE_UID, "username": _USERNAME}


@pytest.fixture(scope="module")
def upsert_results(conn, pre_existing_user) -> list[int]:
    """
    Execute the upsert SQL _REPEAT_COUNT times for the pre-existing user and
    return the list of psycopg2 rowcount values from each execution.

    rowcount == 0 means ON CONFLICT DO NOTHING triggered (no insert).
    rowcount == 1 means a new row was inserted (should only happen on the very
    first call if the user did not exist yet — in our case the user is
    pre-seeded, so all calls must return 0).
    """
    results = []
    for _ in range(_REPEAT_COUNT):
        with conn.cursor() as cur:
            cur.execute(_UPSERT_SQL, (_FIREBASE_UID, _USERNAME))
            results.append(cur.rowcount)
    return results


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAutoProvisioningExistingUser:
    """
    Verifies that repeated upserts for an already-existing firebase_uid do not
    create duplicate rows in the users table.
    """

    def test_precondition_user_exists_before_upsert(self, conn, pre_existing_user):
        """
        The user must already be present in the database before any upsert is
        executed — confirms the precondition from the ticket.
        """
        with conn.cursor() as cur:
            cur.execute(_COUNT_SQL, (pre_existing_user["firebase_uid"],))
            count = cur.fetchone()[0]

        assert count == 1, (
            f"Expected exactly 1 pre-existing user row for firebase_uid "
            f"'{pre_existing_user['firebase_uid']}', found {count}. "
            "Precondition setup failed."
        )

    def test_upsert_does_not_insert_when_conflict(self, conn, pre_existing_user, upsert_results):
        """
        Every upsert execution must hit ON CONFLICT DO NOTHING (rowcount == 0)
        because the firebase_uid already exists.
        """
        for i, rowcount in enumerate(upsert_results, start=1):
            assert rowcount == 0, (
                f"Upsert call #{i} returned rowcount={rowcount} "
                f"(expected 0 — ON CONFLICT DO NOTHING). "
                f"A duplicate row may have been inserted for firebase_uid "
                f"'{pre_existing_user['firebase_uid']}'."
            )

    def test_only_one_record_remains_after_repeated_upserts(self, conn, pre_existing_user, upsert_results):
        """
        After _REPEAT_COUNT upsert calls the users table must contain exactly
        one row for the firebase_uid — the original pre-seeded record.

        This is the primary assertion from the test case: "No duplicate records
        are created in the database; only the original user record remains."
        """
        with conn.cursor() as cur:
            cur.execute(_COUNT_SQL, (pre_existing_user["firebase_uid"],))
            count = cur.fetchone()[0]

        assert count == 1, (
            f"Expected exactly 1 user row after {_REPEAT_COUNT} upsert calls, "
            f"but found {count} rows for firebase_uid "
            f"'{pre_existing_user['firebase_uid']}'. "
            "The ON CONFLICT DO NOTHING clause is not preventing duplicates."
        )

    def test_original_user_id_is_unchanged(self, conn, pre_existing_user, upsert_results):
        """
        The user's UUID must remain the same as the originally inserted value.
        If a duplicate were inserted and the original deleted, the ID would change.
        This confirms the original row is preserved, not replaced.
        """
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM users WHERE firebase_uid = %s",
                (pre_existing_user["firebase_uid"],),
            )
            row = cur.fetchone()

        assert row is not None, (
            f"No user row found for firebase_uid '{pre_existing_user['firebase_uid']}' "
            "after repeated upserts — the original record appears to have been deleted."
        )

        fetched_id = str(row[0])
        assert fetched_id == pre_existing_user["id"], (
            f"User ID changed after upserts: original={pre_existing_user['id']!r}, "
            f"current={fetched_id!r}. "
            "The original row must not be replaced or modified."
        )

    def test_username_is_unchanged_after_upserts(self, conn, pre_existing_user, upsert_results):
        """
        The username must remain the value set at initial insert.
        DO NOTHING guarantees the row is never updated, so username must be
        identical to the pre-seeded value.
        """
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username FROM users WHERE firebase_uid = %s",
                (pre_existing_user["firebase_uid"],),
            )
            row = cur.fetchone()

        assert row is not None, (
            f"No user row found for firebase_uid '{pre_existing_user['firebase_uid']}'."
        )

        assert row[0] == pre_existing_user["username"], (
            f"Username changed after upserts: "
            f"original={pre_existing_user['username']!r}, current={row[0]!r}. "
            "ON CONFLICT DO NOTHING must leave the existing row untouched."
        )

    def test_upsert_executed_correct_number_of_times(self, upsert_results):
        """
        Confirms _REPEAT_COUNT upsert operations were actually executed.
        Guards against a defect in the test fixture itself.
        """
        assert len(upsert_results) == _REPEAT_COUNT, (
            f"Expected {_REPEAT_COUNT} upsert results, got {len(upsert_results)}."
        )
