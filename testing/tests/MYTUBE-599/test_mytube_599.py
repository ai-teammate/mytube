"""
MYTUBE-599: Load playlist with orphaned owner reference —
system avoids 500 error and displays relevant message.

Objective
---------
Ensure that when a playlist row exists in the database but its owner_id does not
reference a valid user, the API handles the missing JOIN result gracefully and
returns a 404 (or other handled error) instead of a 500 Internal Server Error.
The frontend would then show a "not found" state instead of the generic
"Could not load playlist" alert.

Root cause context (MYTUBE-592)
-------------------------------
The repository's GetByID query uses INNER JOIN users u ON u.id = p.owner_id.
When the owner row is absent the JOIN yields no rows, which maps to sql.ErrNoRows
and the handler correctly returns 404 "playlist not found" — not 500.
This test verifies that path is exercised and regression-free.

Test steps
----------
1. Seed an orphaned playlist row directly in the DB: a playlist whose owner_id is
   a syntactically-valid UUID that does NOT exist in the users table.
2. Send GET /api/playlists/:id (public endpoint — no auth required).
3. Assert HTTP 404 (not 500 Internal Server Error).
4. Assert the response body signals "not found", not an internal error.

Environment variables
---------------------
- FIREBASE_PROJECT_ID   : Required to start the API server (Firebase verifier init).
                          Test is skipped when absent.
- API_BINARY            : Path to the pre-built Go binary
                          (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                          Database connection settings with sensible defaults.

Architecture notes
------------------
- ApiProcessService starts/stops the Go API binary; all HTTP calls go through it.
- PlaylistApiService wraps GET /api/playlists/:id (public, no token needed).
- Direct psycopg2 SQL is used for idempotent test-data seeding and teardown.
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.playlist_api_service import PlaylistApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18599
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

_DEFAULT_MOCK_CREDS = os.path.join(
    _REPO_ROOT, "testing", "fixtures", "mock_service_account.json"
)
_MOCK_CREDS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", _DEFAULT_MOCK_CREDS)
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> None:
    """Build the Go API binary if it is not already present."""
    if os.path.isfile(API_BINARY):
        return
    api_dir = os.path.join(_REPO_ROOT, "api")
    result = subprocess.run(
        ["go", "build", "-o", API_BINARY, "."],
        cwd=api_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to build API binary:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_project_id():
    """Skip the entire module when FIREBASE_PROJECT_ID is not set.

    The API server initialises a Firebase verifier on startup and will refuse
    to start without this variable, even though the GET endpoint under test is
    public (no token required at request time).
    """
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — the API server cannot initialise "
            "the Firebase verifier without this variable."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """Build (if needed) and start the Go API server in a subprocess.

    Yields the ApiProcessService once /health is reachable, then stops the
    process on teardown.
    """
    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "GOOGLE_APPLICATION_CREDENTIALS": _MOCK_CREDS,
        "RAW_UPLOADS_BUCKET": _RAW_UPLOADS_BUCKET,
    }

    svc = ApiProcessService(
        binary_path=API_BINARY,
        port=_PORT,
        env=env,
        startup_timeout=_STARTUP_TIMEOUT,
    )
    svc.start()

    ready = svc.wait_for_ready(path="/health")
    if not ready:
        logs = svc.get_log_output()
        svc.stop()
        pytest.fail(
            f"API server did not become ready within {_STARTUP_TIMEOUT}s.\n"
            f"Logs:\n{logs}"
        )

    yield svc
    svc.stop()


@pytest.fixture(scope="module")
def db_conn(db_config: DBConfig):
    """Open a direct psycopg2 connection for test-data seeding and teardown."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def orphaned_playlist_id(api_server, db_conn) -> str:  # noqa: ARG001
    """Seed an orphaned playlist row and return its ID.

    The playlist's owner_id is a random UUID that does NOT exist in the users
    table, creating the broken-FK scenario described in MYTUBE-599.

    Because the schema enforces ``playlists.owner_id REFERENCES users(id) ON
    DELETE RESTRICT``, we temporarily drop the FK constraint, insert the
    orphaned row, then immediately restore the constraint.  This mirrors the
    real-world scenario (e.g. a DB migration that removed a user without
    cleaning up playlist rows, or a direct DB operation that bypassed the API).

    Teardown removes the orphaned playlist row and ensures the FK is restored.
    """
    orphaned_owner_id = str(uuid.uuid4())
    playlist_id: str = ""

    with db_conn.cursor() as cur:
        # Drop the FK so we can insert without a parent user row.
        cur.execute(
            "ALTER TABLE playlists DROP CONSTRAINT IF EXISTS playlists_owner_id_fkey"
        )
        cur.execute(
            """
            INSERT INTO playlists (owner_id, title)
            VALUES (%s, %s)
            RETURNING id
            """,
            (orphaned_owner_id, "Orphaned Playlist — MYTUBE-599"),
        )
        playlist_id = str(cur.fetchone()[0])
        # Re-add with NOT VALID: Postgres skips validating existing rows
        # (our orphaned row) but still enforces the constraint on new writes.
        cur.execute(
            """
            ALTER TABLE playlists
            ADD CONSTRAINT playlists_owner_id_fkey
                FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT
                NOT VALID
            """
        )

    yield playlist_id

    # Teardown: delete the orphaned row (and any strays from prior runs), then
    # replace the NOT VALID constraint with a fully-validated one.
    with db_conn.cursor() as cur:
        cur.execute("DELETE FROM playlists WHERE id = %s", (playlist_id,))
        # Purge any other orphaned rows left over from previous failed runs so
        # that re-adding the FK with full validation succeeds.
        cur.execute(
            "DELETE FROM playlists WHERE owner_id NOT IN (SELECT id FROM users)"
        )
        cur.execute(
            "ALTER TABLE playlists DROP CONSTRAINT IF EXISTS playlists_owner_id_fkey"
        )
        cur.execute(
            """
            ALTER TABLE playlists
            ADD CONSTRAINT playlists_owner_id_fkey
                FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE RESTRICT
            """
        )


@pytest.fixture(scope="module")
def playlist_service(api_server) -> PlaylistApiService:
    """Return an unauthenticated PlaylistApiService (GET is a public endpoint)."""
    return PlaylistApiService(base_url=f"http://127.0.0.1:{_PORT}")


@pytest.fixture(scope="module")
def get_response(
    playlist_service: PlaylistApiService,
    orphaned_playlist_id: str,
) -> dict:
    """Issue GET /api/playlists/:id for the orphaned playlist and cache the result."""
    result = playlist_service.get_playlist(orphaned_playlist_id)
    return {"status_code": result.status_code, "raw_body": result.raw_body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOrphanedOwnerPlaylist:
    """MYTUBE-599: GET /api/playlists/:id for a playlist whose owner row is absent
    must return 404, not 500, confirming the JOIN-miss is handled gracefully."""

    def test_returns_404_not_500(self, get_response: dict) -> None:
        """API must return HTTP 404 (not 500) for a playlist with an orphaned owner.

        When the owner row is missing the INNER JOIN in GetByID produces
        sql.ErrNoRows, which the repository maps to (nil, nil).  The handler
        then emits 404 "playlist not found".  A 500 here would indicate the
        error path is not properly handled.
        """
        status = get_response["status_code"]
        body = get_response["raw_body"]
        assert status == 404, (
            f"Expected HTTP 404 for orphaned-owner playlist, got {status}. "
            f"Response body: {body!r}. "
            "A 500 means the JOIN miss bubbled up as an internal server error "
            "rather than being handled as a not-found case."
        )

    def test_body_not_internal_server_error(self, get_response: dict) -> None:
        """Response body must NOT indicate an internal server error.

        The body should contain a 'not found' message, confirming that the
        missing-owner case is treated as a missing resource, not a server fault.
        """
        body = get_response["raw_body"].lower()
        assert "internal server error" not in body, (
            f"Response body indicates an internal server error: {get_response['raw_body']!r}. "
            "Expected a 'not found' style message instead."
        )

    def test_body_contains_not_found_message(self, get_response: dict) -> None:
        """Response body should communicate that the playlist was not found."""
        body = get_response["raw_body"].lower()
        assert "not found" in body or "playlist not found" in body, (
            f"Expected a 'not found' message in the response body, got: "
            f"{get_response['raw_body']!r}"
        )
