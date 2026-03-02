"""
MYTUBE-129: Run DB integration tests with custom environment variables —
tests utilize DB_HOST and DB_PORT for connection.

Objective
---------
Ensure the test suite correctly utilises environment variable overrides to
connect to a non-default PostgreSQL host or port, preventing hardcoded
environment failures.

What is verified
----------------
1. DBConfig reads DB_HOST and DB_PORT from the environment rather than using
   hardcoded defaults.
2. The DSN produced by DBConfig embeds the custom host and port values.
3. psycopg2.connect() uses the DSN built from DBConfig — when the env vars
   point to the running test database the connection succeeds; when they are
   overridden to an unreachable address the connection fails (proving the
   driver honours the overridden values).

Architecture notes
------------------
- DBConfig (testing/core/config/db_config.py) is the single source of truth
  for all DB connection parameters.  It reads: DB_HOST (default "localhost"),
  DB_PORT (default 5432), DB_USER, DB_PASSWORD, DB_NAME, SSL_MODE.
- Tests manipulate os.environ directly and re-instantiate DBConfig so that
  each case reflects the state of the environment at call time.
- No Go binary is required; all assertions are on the Python config layer and
  the psycopg2 TCP connection behaviour.
"""

import os
import sys
import socket

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _free_local_port() -> int:
    """Return a local TCP port that has nothing listening on it."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# ---------------------------------------------------------------------------
# Class 1 — DBConfig reflects custom DB_HOST / DB_PORT env vars
# ---------------------------------------------------------------------------


class TestDBConfigReadsEnvVars:
    """DBConfig must pick up DB_HOST and DB_PORT from the environment."""

    def test_custom_host_reflected_in_config(self, monkeypatch):
        """DB_HOST override must appear in the DBConfig.host attribute."""
        monkeypatch.setenv("DB_HOST", "custom-pg-host.internal")
        cfg = DBConfig()
        assert cfg.host == "custom-pg-host.internal", (
            f"Expected DBConfig.host='custom-pg-host.internal', got '{cfg.host}'"
        )

    def test_custom_port_reflected_in_config(self, monkeypatch):
        """DB_PORT override must appear as an integer in DBConfig.port."""
        monkeypatch.setenv("DB_PORT", "5433")
        cfg = DBConfig()
        assert cfg.port == 5433, (
            f"Expected DBConfig.port=5433, got {cfg.port}"
        )

    def test_default_host_when_env_unset(self, monkeypatch):
        """When DB_HOST is not set DBConfig must default to 'localhost'."""
        monkeypatch.delenv("DB_HOST", raising=False)
        cfg = DBConfig()
        assert cfg.host == "localhost", (
            f"Expected default host 'localhost', got '{cfg.host}'"
        )

    def test_default_port_when_env_unset(self, monkeypatch):
        """When DB_PORT is not set DBConfig must default to 5432."""
        monkeypatch.delenv("DB_PORT", raising=False)
        cfg = DBConfig()
        assert cfg.port == 5432, (
            f"Expected default port 5432, got {cfg.port}"
        )

    def test_port_is_integer(self, monkeypatch):
        """DBConfig.port must be an int, not a string."""
        monkeypatch.setenv("DB_PORT", "5433")
        cfg = DBConfig()
        assert isinstance(cfg.port, int), (
            f"Expected DBConfig.port to be int, got {type(cfg.port)}"
        )


# ---------------------------------------------------------------------------
# Class 2 — DSN embeds the custom values
# ---------------------------------------------------------------------------


class TestDSNContainsCustomValues:
    """DBConfig.dsn() must embed DB_HOST and DB_PORT overrides."""

    def test_dsn_contains_custom_host(self, monkeypatch):
        """Custom DB_HOST must appear in the DSN string."""
        monkeypatch.setenv("DB_HOST", "pg.example.com")
        cfg = DBConfig()
        dsn = cfg.dsn()
        assert "host=pg.example.com" in dsn, (
            f"Expected 'host=pg.example.com' in DSN, got: {dsn}"
        )

    def test_dsn_contains_custom_port(self, monkeypatch):
        """Custom DB_PORT must appear in the DSN string."""
        monkeypatch.setenv("DB_PORT", "5433")
        cfg = DBConfig()
        dsn = cfg.dsn()
        assert "port=5433" in dsn, (
            f"Expected 'port=5433' in DSN, got: {dsn}"
        )

    def test_dsn_contains_both_custom_host_and_port(self, monkeypatch):
        """Both DB_HOST and DB_PORT overrides must appear together in the DSN."""
        monkeypatch.setenv("DB_HOST", "10.0.0.5")
        monkeypatch.setenv("DB_PORT", "5433")
        cfg = DBConfig()
        dsn = cfg.dsn()
        assert "host=10.0.0.5" in dsn, (
            f"Expected 'host=10.0.0.5' in DSN, got: {dsn}"
        )
        assert "port=5433" in dsn, (
            f"Expected 'port=5433' in DSN, got: {dsn}"
        )

    def test_dsn_default_host_and_port(self, monkeypatch):
        """When neither DB_HOST nor DB_PORT is set the DSN must use defaults."""
        monkeypatch.delenv("DB_HOST", raising=False)
        monkeypatch.delenv("DB_PORT", raising=False)
        cfg = DBConfig()
        dsn = cfg.dsn()
        assert "host=localhost" in dsn, (
            f"Expected 'host=localhost' in default DSN, got: {dsn}"
        )
        assert "port=5432" in dsn, (
            f"Expected 'port=5432' in default DSN, got: {dsn}"
        )

    def test_dsn_logged_value_matches_env(self, monkeypatch, capsys):
        """
        Simulates the 'Check the DSN logged in the test output' step from the
        ticket.  Print the DSN (as a test would log it) and confirm the
        captured output contains the expected host and port.
        """
        monkeypatch.setenv("DB_HOST", "nonstandard-host.db")
        monkeypatch.setenv("DB_PORT", "5433")
        cfg = DBConfig()
        dsn = cfg.dsn()
        print(f"DSN: {dsn}")  # simulates what tests log to stdout
        captured = capsys.readouterr()
        assert "nonstandard-host.db" in captured.out, (
            f"DSN log output does not contain custom host. Output: {captured.out}"
        )
        assert "5433" in captured.out, (
            f"DSN log output does not contain custom port. Output: {captured.out}"
        )


# ---------------------------------------------------------------------------
# Class 3 — psycopg2 honours the custom host/port from DBConfig
# ---------------------------------------------------------------------------


class TestPsycopg2HonoursDBConfig:
    """
    psycopg2.connect() must attempt to use the host/port supplied by DBConfig.
    When the target is unreachable the driver raises OperationalError (not a
    silent fallback to the default address).
    """

    def test_connection_fails_to_unreachable_custom_port(self, monkeypatch):
        """
        Setting DB_PORT to a port with nothing listening must cause
        psycopg2.connect() to raise OperationalError, confirming the driver
        actually uses the override rather than silently falling back to 5432.
        """
        closed_port = _free_local_port()
        monkeypatch.setenv("DB_HOST", "127.0.0.1")
        monkeypatch.setenv("DB_PORT", str(closed_port))
        cfg = DBConfig()
        dsn = cfg.dsn()
        print(f"DSN (unreachable): {dsn}")
        with pytest.raises(psycopg2.OperationalError):
            psycopg2.connect(dsn)

    def test_connection_fails_to_unreachable_custom_host(self, monkeypatch):
        """
        Setting DB_HOST to a non-existent host must cause psycopg2.connect()
        to raise OperationalError, confirming the override is forwarded to the
        driver.
        """
        monkeypatch.setenv("DB_HOST", "host-does-not-exist-mytube-129.invalid")
        cfg = DBConfig()
        dsn = cfg.dsn()
        print(f"DSN (bad host): {dsn}")
        with pytest.raises(psycopg2.OperationalError):
            psycopg2.connect(dsn)

    def test_connection_succeeds_with_valid_db_config(self):
        """
        When DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, and DB_NAME point to the
        running test database instance (set via env vars by the CI / test
        runner), the connection must succeed.

        This is the primary happy-path assertion from the ticket:
        "The test suite connects to the database using the provided environment
        variables instead of the default localhost:5432, and the tests execute
        successfully."
        """
        cfg = DBConfig()
        dsn = cfg.dsn()
        print(f"DSN (live): {dsn}")
        conn = psycopg2.connect(dsn)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT version();")
                row = cur.fetchone()
                assert row is not None, "SELECT version() returned no rows"
                pg_version = row[0]
                print(f"Connected to: {pg_version}")
                assert "PostgreSQL" in pg_version, (
                    f"Unexpected version string: {pg_version}"
                )
        finally:
            conn.close()
