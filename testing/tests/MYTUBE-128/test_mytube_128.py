"""
MYTUBE-128: Run DB integration tests with active PostgreSQL service —
tests connect and pass successfully.

Objective:
    Verify that the DB integration tests in the TestMarkFailedSQLContract
    class (from MYTUBE-80) execute successfully when a PostgreSQL service
    is reachable.

    Specifically this test confirms:
      1. PostgreSQL is reachable at the configured host/port — no
         "Connection refused" errors occur.
      2. All three TestMarkFailedSQLContract tests pass:
           - test_mark_failed_sets_status_to_failed
           - test_failed_status_accepted_by_check_constraint
           - test_mark_failed_does_not_affect_other_rows

Strategy:
    Run the MYTUBE-80 test file filtered to TestMarkFailedSQLContract via
    pytest subprocess. Verify exit code 0 and that all 3 tests pass and none
    are skipped (no "skipped" count in the summary line).
"""

import os
import re
import subprocess
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_MYTUBE_80_TEST = os.path.join(
    _REPO_ROOT, "testing", "tests", "MYTUBE-80", "test_mytube_80.py"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXPECTED_TESTS = [
    "test_mark_failed_sets_status_to_failed",
    "test_failed_status_accepted_by_check_constraint",
    "test_mark_failed_does_not_affect_other_rows",
]


def _postgres_available() -> bool:
    """Return True if PostgreSQL is reachable using the default DBConfig."""
    try:
        conn = psycopg2.connect(DBConfig().dsn())
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDBIntegrationWithPostgres:
    """
    Verifies that TestMarkFailedSQLContract from MYTUBE-80 runs and passes
    when PostgreSQL is available.
    """

    def test_postgres_is_reachable(self):
        """
        PostgreSQL must be reachable at the configured host/port.
        This is the precondition for the DB integration tests.
        """
        cfg = DBConfig()
        try:
            conn = psycopg2.connect(cfg.dsn())
            conn.close()
        except psycopg2.OperationalError as exc:
            pytest.fail(
                f"PostgreSQL is not reachable at {cfg.host}:{cfg.port} — "
                f"connection refused.\nDSN: host={cfg.host} port={cfg.port} "
                f"dbname={cfg.dbname}\nError: {exc}"
            )

    def test_mark_failed_sql_contract_all_pass(self):
        """
        All 3 TestMarkFailedSQLContract tests from MYTUBE-80 must pass when
        PostgreSQL is available — none should be skipped or fail.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-v",
                "-k",
                "TestMarkFailedSQLContract",
                _MYTUBE_80_TEST,
            ],
            capture_output=True,
            text=True,
            cwd=_REPO_ROOT,
        )

        output = result.stdout + result.stderr

        # Must exit cleanly — all tests passed
        assert result.returncode == 0, (
            "TestMarkFailedSQLContract tests did not all pass.\n"
            f"Exit code: {result.returncode}\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        # None of the tests should have been skipped (PostgreSQL was available)
        assert "skipped" not in output.lower() or "0 skipped" in output, (
            "TestMarkFailedSQLContract tests were skipped — PostgreSQL was not "
            "detected as available during the MYTUBE-80 run.\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )

        # All 3 individual tests must be reported as PASSED (co-located on the same line)
        for test_name in _EXPECTED_TESTS:
            assert re.search(
                rf"PASSED.*{re.escape(test_name)}|{re.escape(test_name)}.*PASSED",
                output,
            ), (
                f"Expected test '{test_name}' to appear as PASSED in output.\n"
                f"STDOUT:\n{result.stdout}"
            )
