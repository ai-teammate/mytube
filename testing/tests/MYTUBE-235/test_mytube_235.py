"""
MYTUBE-235: Remove video from playlist via API — association record deleted.

Objective
---------
Verify that the owner can remove a specific video from their playlist.

Preconditions
-------------
User is the owner of a playlist that contains video X.

Steps
-----
1. Send a DELETE request to /api/playlists/:id/videos/[video_X_id].
2. Fetch the playlist via GET /api/playlists/:id.

Expected Result
---------------
API returns a success status for the DELETE. The subsequent GET returns 200 OK
and the videos array no longer contains video X.

Test approach
-------------
- Test data is seeded via a direct Cloud SQL connection:
    * CI test user row is upserted (firebase_uid = FIREBASE_TEST_UID).
    * A synthetic test video is inserted owned by the CI test user.
    * A test playlist is inserted owned by the CI test user.
    * The test video is added to the playlist (playlist_videos row).
- DELETE /api/playlists/:id/videos/:video_id is issued with the CI test
  user's Firebase Bearer token.
- GET /api/playlists/:id (public) is called and the videos array is inspected.
- All seeded rows are removed in teardown (FK-safe order).

Environment variables
---------------------
FIREBASE_TEST_TOKEN       : Valid Firebase ID token (required; test skips when absent).
FIREBASE_TEST_UID         : firebase_uid of the CI test user (default: ci-test-user-001).
CLOUD_SQL_CONNECTION_NAME : Cloud SQL instance connection name.
                            Default: ai-native-478811:us-central1:learn-ai-db
DB_USER                   : Database user (default: mytube).
DB_PASSWORD               : Database password.
DB_NAME                   : Database name (default: mytube).
API_BASE_URL              : Deployed API base URL.
                            Default: https://mytube-api-80693608388.us-central1.run.app

Architecture
------------
- PlaylistApiService encapsulates DELETE and GET /api/playlists HTTP calls.
- Cloud SQL Python connector provides the direct database connection for seeding.
- No hardcoded credentials — only well-known CI defaults are referenced.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.services.playlist_api_service import PlaylistApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEPLOYED_API_URL = "https://mytube-api-80693608388.us-central1.run.app"
_API_BASE_URL = os.getenv("API_BASE_URL", _DEPLOYED_API_URL)

# Firebase credentials — required; test skips when absent.
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")

# CI test user.
_CI_USER_FIREBASE_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")
_CI_USER_USERNAME = "testuser_235_owner"

# Synthetic test data labels.
_VIDEO_TITLE = "MYTUBE-235 Test Video"
_PLAYLIST_TITLE = "MYTUBE-235 Test Playlist"

# Cloud SQL — used for direct database access.
_CLOUD_SQL_INSTANCE = os.getenv(
    "CLOUD_SQL_CONNECTION_NAME", "ai-native-478811:us-central1:learn-ai-db"
)
_DB_USER = os.getenv("DB_USER", "mytube")
_DB_PASS = os.getenv("DB_PASSWORD", "")
_DB_NAME = os.getenv("DB_NAME", "mytube")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _cloud_sql_connect():
    """Open a synchronous pg8000 connection to Cloud SQL via the connector.

    Returns (conn, connector); caller is responsible for closing both.
    Raises ImportError if cloud-sql-python-connector is not installed.
    """
    from google.cloud.sql.connector import Connector  # type: ignore

    connector = Connector()
    conn = connector.connect(
        _CLOUD_SQL_INSTANCE,
        "pg8000",
        user=_DB_USER,
        password=_DB_PASS,
        db=_DB_NAME,
    )
    conn.autocommit = True
    return conn, connector


def _api_is_reachable(base_url: str) -> bool:
    """Return True if the API /health endpoint responds without a 5xx error."""
    import urllib.request

    try:
        resp = urllib.request.urlopen(f"{base_url}/health", timeout=5)
        return resp.status < 500
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_token():
    """Skip the entire module when FIREBASE_TEST_TOKEN is not available."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-235 integration test. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run."
        )


@pytest.fixture(scope="module", autouse=True)
def require_api(require_firebase_token):
    """Skip when the deployed API is not reachable."""
    if not _api_is_reachable(_API_BASE_URL):
        pytest.skip(
            f"API at {_API_BASE_URL} is not reachable — "
            "skipping MYTUBE-235 integration test."
        )


@pytest.fixture(scope="module")
def db_conn(require_api):
    """Open a direct Cloud SQL connection for test-data seeding.

    Skips when cloud-sql-python-connector is not installed or the
    connection cannot be established.
    """
    try:
        conn, connector = _cloud_sql_connect()
    except ImportError:
        pytest.skip(
            "cloud-sql-python-connector is not installed. "
            "Run: pip install 'cloud-sql-python-connector[pg8000]'"
        )
    except Exception as exc:
        pytest.skip(f"Cannot connect to Cloud SQL: {exc}")

    yield conn

    try:
        conn.close()
        connector.close()
    except Exception:
        pass


@pytest.fixture(scope="module")
def seeded_data(db_conn):
    """Seed the CI test user, a test video, and a test playlist with the video.

    Returns a dict with:
      user_id     : DB id of the CI test user
      video_id    : DB id of the test video (video X)
      playlist_id : DB id of the test playlist
    """
    cur = db_conn.cursor()

    # --- CI test user: upsert so the API's Firebase-UID lookup succeeds ---
    cur.execute(
        "SELECT id FROM users WHERE firebase_uid = %s",
        (_CI_USER_FIREBASE_UID,),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) RETURNING id",
            (_CI_USER_FIREBASE_UID, _CI_USER_USERNAME),
        )
        row = cur.fetchone()
    user_id = str(row[0])

    # --- Test video owned by CI test user ---
    cur.execute(
        "INSERT INTO videos (uploader_id, title, status) "
        "VALUES (%s, %s, 'ready') RETURNING id",
        (user_id, _VIDEO_TITLE),
    )
    video_id = str(cur.fetchone()[0])

    # --- Test playlist owned by CI test user ---
    cur.execute(
        "INSERT INTO playlists (owner_id, title) VALUES (%s, %s) RETURNING id",
        (user_id, _PLAYLIST_TITLE),
    )
    playlist_id = str(cur.fetchone()[0])

    # --- Associate video X with the playlist (position 1) ---
    cur.execute(
        "INSERT INTO playlist_videos (playlist_id, video_id, position) "
        "VALUES (%s, %s, %s)",
        (playlist_id, video_id, 1),
    )

    yield {
        "user_id": user_id,
        "video_id": video_id,
        "playlist_id": playlist_id,
    }

    # Teardown: remove seeded rows in FK-safe order.
    # playlist_videos is CASCADE on playlist delete; delete playlist first.
    cur.execute("DELETE FROM playlist_videos WHERE playlist_id = %s", (playlist_id,))
    cur.execute("DELETE FROM playlists WHERE id = %s", (playlist_id,))
    cur.execute("DELETE FROM videos WHERE id = %s", (video_id,))
    # Do NOT delete the CI test user — they are shared across tests.


@pytest.fixture(scope="module")
def playlist_service() -> PlaylistApiService:
    """Return a PlaylistApiService pointing at the deployed API."""
    return PlaylistApiService(base_url=_API_BASE_URL, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def delete_response(seeded_data, playlist_service: PlaylistApiService) -> dict:
    """Step 1: DELETE /api/playlists/:id/videos/:video_id as the CI test user.

    Returns a dict with status_code and body.
    """
    status_code, body = playlist_service.remove_video(
        playlist_id=seeded_data["playlist_id"],
        video_id=seeded_data["video_id"],
    )
    return {"status_code": status_code, "body": body}


@pytest.fixture(scope="module")
def playlist_after_delete(seeded_data, delete_response, playlist_service: PlaylistApiService):
    """Step 2: GET /api/playlists/:id after the DELETE.

    Returns the PlaylistDetailResponse.
    """
    return playlist_service.get_playlist(seeded_data["playlist_id"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRemoveVideoFromPlaylist:
    """MYTUBE-235: Owner removes a video from their playlist via the API."""

    def test_delete_video_from_playlist_returns_success_status(
        self, delete_response: dict
    ) -> None:
        """DELETE /api/playlists/:id/videos/:video_id must return a 2xx success status.

        The server must confirm the removal with an HTTP 200 or 204 response.
        A 4xx or 5xx response indicates the endpoint is broken or the owner
        check is failing incorrectly.
        """
        status = delete_response["status_code"]
        assert 200 <= status < 300, (
            f"Expected a 2xx success status from "
            f"DELETE /api/playlists/:id/videos/:video_id, but got HTTP {status}. "
            f"Response body: {delete_response['body']!r}"
        )

    def test_get_playlist_returns_200(
        self, playlist_after_delete
    ) -> None:
        """GET /api/playlists/:id must return HTTP 200 after the video is removed.

        The playlist itself must still exist and be publicly accessible.
        """
        assert playlist_after_delete.status_code == 200, (
            f"Expected HTTP 200 from GET /api/playlists/:id after video removal, "
            f"but got HTTP {playlist_after_delete.status_code}. "
            f"Body: {playlist_after_delete.raw_body!r}"
        )

    def test_video_absent_from_playlist_after_delete(
        self, seeded_data: dict, playlist_after_delete
    ) -> None:
        """The removed video must not appear in the playlist's videos array.

        After DELETE /api/playlists/:id/videos/:video_id the association row is
        removed; GET /api/playlists/:id must return a videos list that no
        longer contains the deleted video's ID.
        """
        video_id = seeded_data["video_id"]
        remaining_ids = playlist_after_delete.video_ids
        assert video_id not in remaining_ids, (
            f"Expected video {video_id!r} to be absent from the playlist videos "
            f"after DELETE, but it still appears in the list: {remaining_ids}. "
            "The playlist_videos association row was NOT removed by the API."
        )
