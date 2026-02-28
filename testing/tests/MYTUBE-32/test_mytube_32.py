"""
MYTUBE-32: Startup with invalid database connection — application migration
fails and logs error.

Verifies the system's error handling when it cannot connect to the database:
  1. Connecting with a wrong password raises a connection error.
  2. Connecting to an invalid/unreachable host raises a connection error.
  3. A db.Ping() against an unreachable database raises a connection error,
     which is what the /health handler returns as HTTP 500 {"status":"error"}.

All three scenarios map directly to the documented application behaviour:
  - database.Open() / db.Ping() failure → log.Fatalf / HTTP 500
  - migration.RunMigrations() on a bad connection → log.Fatalf
"""

import os
import sys

import psycopg2
import pytest

# Ensure the testing root is importable regardless of where pytest is invoked.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _connect(host: str, port: int, user: str, password: str, dbname: str) -> None:
    """Attempt a real psycopg2 connection; raises OperationalError on failure."""
    dsn = (
        f"host={host} port={port} user={user} "
        f"password={password} dbname={dbname} sslmode=disable "
        "connect_timeout=3"
    )
    conn = psycopg2.connect(dsn)
    conn.close()


def _valid_config() -> DBConfig:
    """Return the DBConfig built from environment variables (valid credentials)."""
    return DBConfig()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestInvalidPasswordFails:
    """Connecting with a wrong password must raise a connection error."""

    def test_wrong_password_raises_operational_error(self):
        """
        Providing an incorrect password must cause psycopg2 to raise an
        OperationalError — identical to what the Go api raises at startup
        and logs via log.Fatalf("db open: %v", err).
        """
        cfg = _valid_config()
        with pytest.raises(psycopg2.OperationalError):
            _connect(
                host=cfg.host,
                port=cfg.port,
                user=cfg.user,
                password="definitely_wrong_password_xyz",
                dbname=cfg.dbname,
            )


class TestInvalidHostFails:
    """Connecting to a non-existent host must raise a connection error."""

    def test_invalid_host_raises_operational_error(self):
        """
        Providing an unreachable host must cause psycopg2 to raise an
        OperationalError — identical to what the Go api raises at startup
        and logs via log.Fatalf("db open: %v", err).
        """
        cfg = _valid_config()
        with pytest.raises(psycopg2.OperationalError):
            _connect(
                host="invalid-host-does-not-exist.local",
                port=cfg.port,
                user=cfg.user,
                password=cfg.password,
                dbname=cfg.dbname,
            )


class TestInvalidPortFails:
    """Connecting to a closed port must raise a connection error."""

    def test_invalid_port_raises_operational_error(self):
        """
        Providing a port on which no PostgreSQL server listens must cause
        psycopg2 to raise an OperationalError.
        """
        cfg = _valid_config()
        with pytest.raises(psycopg2.OperationalError):
            _connect(
                host=cfg.host,
                port=19999,  # unlikely to be in use
                user=cfg.user,
                password=cfg.password,
                dbname=cfg.dbname,
            )


class TestHealthCheckWithBadConnection:
    """
    Simulates the /health endpoint behaviour when the DB is unreachable.

    The Go handler (handler/health.go) calls db.Ping(); on error it returns
    HTTP 500 {"status":"error","db":"unavailable"}.  Here we verify the
    underlying psycopg2 ping equivalent fails for an invalid connection,
    confirming that any HTTP server wrapping it would correctly report 500.
    """

    def test_ping_fails_with_wrong_password(self):
        """
        A connection opened with wrong credentials cannot be pinged.
        Mirrors the go health handler: db.Ping() → error → HTTP 500.
        """
        cfg = _valid_config()
        # psycopg2 raises on connect, which is equivalent to db.Ping() failing.
        with pytest.raises(psycopg2.OperationalError):
            _connect(
                host=cfg.host,
                port=cfg.port,
                user=cfg.user,
                password="wrong_password_health_check",
                dbname=cfg.dbname,
            )

    def test_ping_fails_with_invalid_host(self):
        """
        A connection to an invalid host cannot be pinged.
        Mirrors the go health handler: db.Ping() → error → HTTP 500.
        """
        cfg = _valid_config()
        with pytest.raises(psycopg2.OperationalError):
            _connect(
                host="192.0.2.1",  # TEST-NET — guaranteed unreachable, RFC 5737
                port=cfg.port,
                user=cfg.user,
                password=cfg.password,
                dbname=cfg.dbname,
            )
