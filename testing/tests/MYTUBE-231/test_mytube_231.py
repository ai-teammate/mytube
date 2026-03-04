"""
MYTUBE-231: Delete playlist as owner — playlist and its video associations removed.

Objective
---------
Verify that deleting a playlist removes the playlist record and all related entries
in the playlist_videos table.

Preconditions
-------------
- User is authenticated and owns a playlist containing at least one video.

Test steps
----------
1. Seed a user (firebase_uid matching the test token), a video, a playlist, and a
   playlist_videos row via direct DB access.
2. Send DELETE /api/playlists/:id with Authorization: Bearer <FIREBASE_TEST_TOKEN>.
3. Assert HTTP 204 No Content.
4. Send GET /api/playlists/:id — assert HTTP 404 (playlist gone).
5. Query playlist_videos WHERE playlist_id = :id — assert 0 rows.
6. Query playlists WHERE id = :id — assert 0 rows.

Note on ticket vs implementation
---------------------------------
The ticket states "API returns 200 OK" but the implementation returns 204 No Content,
which is the standard HTTP response for a successful DELETE with no body.  The test
asserts 204 (the actual implementation behaviour).

Environment variables
---------------------
- FIREBASE_TEST_TOKEN   : Firebase ID token. Test is skipped when absent.
- FIREBASE_PROJECT_ID   : Firebase project ID required to initialise the Firebase
                          verifier in the API server. Test is skipped when absent.
- FIREBASE_TEST_UID     : UID embedded in the test token
                          (default: test-uid-mytube-231).
- API_BINARY            : Path to the pre-built Go binary
                          (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                          Database connection settings with sensible defaults.

Architecture notes
------------------
- ApiProcessService starts and stops the Go API binary; all HTTP calls go through it.
- PlaylistApiService (testing/components/services/playlist_api_service.py) wraps
  the authenticated DELETE and unauthenticated GET playlist calls.
- Direct psycopg2 SQL is used for idempotent test-data setup and DB assertions.
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
"""
from __future__ import annotations

import os
import subprocess
import sys

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

_PORT = 18231
_STARTUP_TIMEOUT = 20.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-231")

_TEST_USERNAME = "testuser_mytube231"

# GCS: use a mock service-account JSON so the binary can initialise its GCS
# client without hitting real GCP infrastructure.  Upload operations are not
# exercised by this test, so the mock is sufficient.
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
def require_firebase_credentials():
    """Skip the entire module when Firebase credentials are not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping delete-playlist integration test. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run this test."
        )
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
    """Open a direct psycopg2 connection for test-data setup and DB assertions."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_data(api_server, db_conn):
    """Seed user → video → playlist → playlist_videos in the test DB.

    Teardown cleans up remaining rows in FK-safe order after the test run.
    The DELETE /api/playlists/:id call (in delete_response fixture) will
    already have removed the playlist and playlist_videos rows via the API,
    so teardown handles the residual video and user rows.
    """
    with db_conn.cursor() as cur:
        # Insert user (idempotent; firebase_uid has UNIQUE constraint).
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_FIREBASE_TEST_UID, _TEST_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_FIREBASE_TEST_UID,),
        )
        row = cur.fetchone()
        if row is None:
            pytest.fail(
                f"Could not insert or find user row for firebase_uid={_FIREBASE_TEST_UID!r}"
            )
        user_id = str(row[0])

        # Insert a video owned by the test user.
        cur.execute(
            "INSERT INTO videos (uploader_id, title, status) VALUES (%s, %s, %s) RETURNING id",
            (user_id, "Test Video for MYTUBE-231", "ready"),
        )
        video_id = str(cur.fetchone()[0])

        # Insert a playlist owned by the test user.
        cur.execute(
            "INSERT INTO playlists (owner_id, title) VALUES (%s, %s) RETURNING id",
            (user_id, "Test Playlist for MYTUBE-231"),
        )
        playlist_id = str(cur.fetchone()[0])

        # Associate the video with the playlist.
        cur.execute(
            "INSERT INTO playlist_videos (playlist_id, video_id, position) VALUES (%s, %s, %s)",
            (playlist_id, video_id, 1),
        )

    yield {
        "user_id": user_id,
        "video_id": video_id,
        "playlist_id": playlist_id,
    }

    # Teardown: remove residual rows in FK-safe order.
    # The playlist and playlist_videos rows are already gone (deleted by the API via
    # cascade).  The video and user rows must be cleaned up explicitly.
    # We delete ALL videos/playlists for this user to handle re-runs where a prior
    # teardown failure left orphaned rows.
    with db_conn.cursor() as cur:
        cur.execute(
            """DELETE FROM playlist_videos WHERE playlist_id IN (
                SELECT id FROM playlists WHERE owner_id = %s
            )""",
            (user_id,),
        )
        cur.execute("DELETE FROM playlists WHERE owner_id = %s", (user_id,))
        cur.execute("DELETE FROM videos WHERE uploader_id = %s", (user_id,))
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))


@pytest.fixture(scope="module")
def playlist_service(api_server) -> PlaylistApiService:
    """Return a PlaylistApiService that calls the local API server with the test token."""
    return PlaylistApiService(
        base_url=f"http://127.0.0.1:{_PORT}",
        token=_FIREBASE_TOKEN,
    )


@pytest.fixture(scope="module")
def delete_response(playlist_service: PlaylistApiService, seeded_data: dict) -> dict:
    """Issue DELETE /api/playlists/:id once and cache the (status_code, body) result."""
    status_code, body = playlist_service.delete_playlist(seeded_data["playlist_id"])
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDeletePlaylistAsOwner:
    """MYTUBE-231: DELETE /api/playlists/:id as the owner must remove the playlist
    and all associated playlist_videos rows."""

    def test_delete_returns_204(self, delete_response: dict) -> None:
        """DELETE /api/playlists/:id must return HTTP 204 No Content."""
        assert delete_response["status_code"] == 204, (
            f"Expected HTTP 204 No Content, got {delete_response['status_code']}. "
            f"Response body: {delete_response['body']!r}"
        )

    def test_get_returns_404_after_delete(
        self,
        playlist_service: PlaylistApiService,
        seeded_data: dict,
        delete_response: dict,  # ensures DELETE ran first
    ) -> None:
        """GET /api/playlists/:id must return HTTP 404 after the playlist is deleted."""
        status_code, body = playlist_service.get_playlist(seeded_data["playlist_id"])
        assert status_code == 404, (
            f"Expected HTTP 404 (playlist gone), got {status_code}. "
            f"Response body: {body!r}"
        )

    def test_playlist_videos_purged_from_db(
        self,
        db_conn,
        seeded_data: dict,
        delete_response: dict,  # ensures DELETE ran first
    ) -> None:
        """No rows must remain in playlist_videos for the deleted playlist's ID."""
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM playlist_videos WHERE playlist_id = %s",
                (seeded_data["playlist_id"],),
            )
            count = cur.fetchone()[0]
        assert count == 0, (
            f"Expected 0 rows in playlist_videos for deleted playlist "
            f"{seeded_data['playlist_id']}, but found {count}."
        )

    def test_playlist_row_purged_from_db(
        self,
        db_conn,
        seeded_data: dict,
        delete_response: dict,  # ensures DELETE ran first
    ) -> None:
        """No row must remain in playlists for the deleted playlist's ID."""
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM playlists WHERE id = %s",
                (seeded_data["playlist_id"],),
            )
            count = cur.fetchone()[0]
        assert count == 0, (
            f"Expected 0 rows in playlists for ID {seeded_data['playlist_id']}, "
            f"but found {count}."
        )
