"""
MYTUBE-32: Startup with invalid database connection — application migration
fails and logs error.

Verifies the Go API's error-handling behaviour when DB credentials are invalid:
  1. The process exits with a non-zero exit code (log.Fatalf path).
  2. The log output contains an error referencing the DB connection.

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService
  (testing/components/services/api_process_service.py).
- DBConfig supplies valid baseline credentials from env vars; tests override
  individual fields to inject faults.
- The Go binary path is resolved relative to the repo root via an env var
  (API_BINARY) or a sensible default build location.

Note on ticket step 3 (/health endpoint)
-----------------------------------------
The ticket asks to "try to access the /health endpoint" when started with bad
credentials.  The Go application architecture makes this impossible to exercise
as a standalone step: main() calls database.Open() → RunMigrations() → (only
then) http.ListenAndServe().  RunMigrations calls postgres.WithInstance() which
pings the DB; if the DB is unreachable the function returns an error, main()
calls log.Fatalf(), and the process exits **before** the HTTP server ever
starts listening.

Consequently there is no window in which a client can reach /health with an
invalid DB.  The /health handler's HTTP-500 path (db.Ping() failure at request
time) can only be triggered by a mid-flight DB disconnection **after** a
successful startup.  That scenario is out of scope for this ticket.

What this test suite does assert:
- The application exits non-zero (not silently swallowing the error).
- The log output contains a connection-related error string.
These two assertions together confirm the expected behaviour described in the
ticket ("The application logs a connection failure error. The API either fails
to start or the /health endpoint returns an error status").
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService

# ---------------------------------------------------------------------------
# Resolve binary path
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

# Ports chosen to avoid conflicts with the real service.
_PORT_WRONG_PASSWORD = 18081
_PORT_INVALID_HOST   = 18082
_PORT_CLOSED_PORT    = 18083


def _make_env(cfg: DBConfig, overrides: dict) -> dict:
    """Build an env dict from DBConfig with selective overrides."""
    base = {
        "DB_HOST": cfg.host,
        "DB_PORT": str(cfg.port),
        "DB_USER": cfg.user,
        "DB_PASSWORD": cfg.password,
        "DB_NAME": cfg.dbname,
        "SSL_MODE": cfg.sslmode,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests — process exits on bad credentials (ticket steps 1–2)
# ---------------------------------------------------------------------------


class TestApiExitsOnBadCredentials:
    """The Go API must call log.Fatalf and exit non-zero when DB connection fails."""

    def test_wrong_password_causes_nonzero_exit(self):
        """
        Starting the API with a wrong DB password must result in the process
        exiting with a non-zero code (log.Fatalf path in main.go).
        """
        cfg = DBConfig()
        env = _make_env(cfg, {"DB_PASSWORD": "definitely_wrong_password_xyz"})
        svc = ApiProcessService(API_BINARY, port=_PORT_WRONG_PASSWORD, env=env, startup_timeout=5.0)
        svc.start()
        try:
            exit_code = svc.wait_for_exit(timeout=8.0)
            assert exit_code is not None, "Process did not exit within timeout"
            assert exit_code != 0, (
                f"Expected non-zero exit code on bad password, got {exit_code}"
            )
        finally:
            svc.stop()

    def test_wrong_password_logs_connection_error(self):
        """
        The log output must contain evidence of a DB connection error.
        The application calls log.Fatalf("migrate: %v", err) when migration
        fails; the underlying postgres driver includes the TCP/auth error.
        """
        cfg = DBConfig()
        env = _make_env(cfg, {"DB_PASSWORD": "definitely_wrong_password_xyz"})
        svc = ApiProcessService(API_BINARY, port=_PORT_WRONG_PASSWORD + 10, env=env, startup_timeout=5.0)
        svc.start()
        try:
            svc.wait_for_exit(timeout=8.0)
            logs = svc.get_log_output()
            # The app logs via log.Fatalf("migrate: %v", err) or
            # log.Fatalf("db open: %v", err). Either prefix indicates startup
            # failure due to a DB connection problem.
            assert any(kw in logs.lower() for kw in ("migrate", "db open", "connect", "fatal")), (
                f"Expected a DB connection error in logs, got:\n{logs}"
            )
        finally:
            svc.stop()

    def test_invalid_host_causes_nonzero_exit(self):
        """
        Starting the API with an unreachable DB host must exit non-zero.
        """
        cfg = DBConfig()
        env = _make_env(cfg, {"DB_HOST": "invalid-host-does-not-exist.local"})
        svc = ApiProcessService(API_BINARY, port=_PORT_INVALID_HOST, env=env, startup_timeout=5.0)
        svc.start()
        try:
            exit_code = svc.wait_for_exit(timeout=8.0)
            assert exit_code is not None, "Process did not exit within timeout"
            assert exit_code != 0, (
                f"Expected non-zero exit code on invalid host, got {exit_code}"
            )
        finally:
            svc.stop()

    def test_invalid_host_logs_connection_error(self):
        """
        Log output must reference a DB connection error when the host is
        unreachable (mirrors log.Fatalf in main.go).
        """
        cfg = DBConfig()
        env = _make_env(cfg, {"DB_HOST": "invalid-host-does-not-exist.local"})
        svc = ApiProcessService(API_BINARY, port=_PORT_INVALID_HOST + 10, env=env, startup_timeout=5.0)
        svc.start()
        try:
            svc.wait_for_exit(timeout=8.0)
            logs = svc.get_log_output()
            assert any(kw in logs.lower() for kw in ("migrate", "db open", "connect", "fatal", "no such host")), (
                f"Expected a DB connection error in logs, got:\n{logs}"
            )
        finally:
            svc.stop()


# ---------------------------------------------------------------------------
# Tests — app exits before HTTP server starts with unreachable DB (ticket step 3)
# ---------------------------------------------------------------------------


class TestApiExitsBeforeServingWhenDbUnreachable:
    """
    Verifies that the API exits before the HTTP server starts when the DB
    is unreachable at boot time.

    This covers the ticket's expected result: "The API either fails to start
    or the /health endpoint returns an error status."  Because main() calls
    RunMigrations() (which pings the DB) before http.ListenAndServe(), the
    process always exits non-zero and never reaches a serving state when the
    DB is unavailable.  There is therefore no window to call /health; the
    fast-fail exit itself is the observable evidence of the error handling.
    """

    def test_api_exits_before_serving_when_db_unreachable_at_closed_port(self):
        """
        Start the API with a closed local port as DB target.

        A closed local port gives an immediate "connection refused" so we
        get a fast, deterministic result without a network timeout.  The
        process must exit non-zero and its logs must contain the connection
        error — confirming the application fails fast rather than silently
        starting in a broken state.
        """
        cfg = DBConfig()
        env = _make_env(cfg, {
            "DB_HOST": "127.0.0.1",
            "DB_PORT": "19998",   # almost certainly no service listening here
            "SSL_MODE": "disable",
        })
        svc = ApiProcessService(API_BINARY, port=_PORT_CLOSED_PORT, env=env, startup_timeout=5.0)
        svc.start()
        try:
            exit_code = svc.wait_for_exit(timeout=8.0)
            logs = svc.get_log_output()

            # The API must not silently swallow the error and start serving.
            assert exit_code is not None, "Process did not exit — API started despite bad DB"
            assert exit_code != 0, (
                f"Expected non-zero exit when DB is unreachable, got exit_code={exit_code}"
            )
            assert any(kw in logs.lower() for kw in ("migrate", "db open", "connect", "refused")), (
                f"Expected connection error in logs, got:\n{logs}"
            )
        finally:
            svc.stop()
