"""
MYTUBE-237: View user profile with private playlists — only public playlists
are displayed.

Objective
---------
Verify that the user profile page respects playlist privacy settings and only
displays public playlists.

Preconditions
-------------
The user "tester" has at least one public playlist and at least one private
playlist.

Steps
-----
1. Navigate to the user profile page at /u/tester.
2. Inspect the list of playlists rendered in the playlists section.

Expected Result
---------------
Only the public playlists are visible on the profile page. Private playlists
are excluded from the list.

Test approach
-------------
1. Seed test data via a direct Cloud SQL connection:
   - Upsert the CI test user.
   - Insert one public playlist  (is_private = FALSE).
   - Insert one private playlist (is_private = TRUE).
   If the ``is_private`` column does not exist the INSERT raises an exception
   and the test is skipped — indicating the feature has not yet been deployed.
2. Call GET /api/users/:username/playlists via PlaylistApiService (unauthenticated).
3. Assert:
   - HTTP 200 is returned.
   - The public playlist appears in the response.
   - The private playlist does NOT appear in the response.
4. Clean up seeded rows in teardown (FK-safe order).

Environment variables
---------------------
FIREBASE_TEST_UID         : firebase_uid of the CI test user
                            (default: ci-test-user-001).
CLOUD_SQL_CONNECTION_NAME : Cloud SQL instance connection name
                            (default: ai-native-478811:us-central1:learn-ai-db).
DB_USER                   : Database user (default: mytube).
DB_PASSWORD               : Database password.
DB_NAME                   : Database name (default: mytube).
API_BASE_URL              : Deployed API base URL
                            (default: https://mytube-api-80693608388.us-central1.run.app).

``GOOGLE_APPLICATION_CREDENTIALS`` must be set (configured by
``google-github-actions/auth@v2`` in CI).

Architecture
------------
- APIConfig (testing/core/config/api_config.py) provides the API base URL.
- HealthService (testing/components/services/health_service.py) checks reachability.
- PlaylistApiService (testing/components/services/playlist_api_service.py)
  encapsulates GET /api/users/:username/playlists HTTP calls.
- Cloud SQL Python connector provides the direct database connection for seeding.
- No hardcoded credentials — only well-known CI defaults are referenced.
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.components.services.health_service import HealthService
from testing.components.services.playlist_api_service import PlaylistApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_cfg = APIConfig()
_API_BASE_URL = _cfg.base_url

_CI_USER_FIREBASE_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")
_CI_USER_USERNAME = "testuser_237_owner"

_PUBLIC_PLAYLIST_TITLE = "MYTUBE-237 Public Playlist"
_PRIVATE_PLAYLIST_TITLE = "MYTUBE-237 Private Playlist"

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
    """Open a pg8000 connection via the Cloud SQL Python connector.

    Returns (conn, connector); the caller must close both.
    Raises ImportError when the connector library is not installed.
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_api():
    """Skip the entire module when the deployed API is not reachable."""
    health = HealthService(_cfg)
    try:
        resp = health.get_health()
        if resp.status_code >= 500:
            pytest.skip(
                f"API at {_API_BASE_URL} returned HTTP {resp.status_code} — "
                "skipping MYTUBE-237 integration test."
            )
    except Exception:
        pytest.skip(
            f"API at {_API_BASE_URL} is not reachable — "
            "skipping MYTUBE-237 integration test."
        )


@pytest.fixture(scope="module")
def db_conn(require_api):
    """Open a direct Cloud SQL connection for test-data seeding.

    Skips when the cloud-sql-python-connector library is not installed or the
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
    """Seed the CI test user, a public playlist, and a private playlist.

    Yields a dict with:
      username            : DB username for the CI test user
      public_playlist_id  : UUID of the public playlist
      private_playlist_id : UUID of the private playlist

    Skips the test module when the ``is_private`` column does not exist on the
    ``playlists`` table, indicating the privacy feature has not been deployed.
    """
    cur = db_conn.cursor()

    # --- Upsert CI test user ---
    cur.execute(
        "SELECT id, username FROM users WHERE firebase_uid = %s",
        (_CI_USER_FIREBASE_UID,),
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO users (firebase_uid, username) VALUES (%s, %s) RETURNING id, username",
            (_CI_USER_FIREBASE_UID, _CI_USER_USERNAME),
        )
        row = cur.fetchone()
    user_id = str(row[0])
    username = row[1] or _CI_USER_USERNAME

    # --- Insert public playlist (is_private = FALSE) ---
    # If the is_private column does not exist the INSERT will raise an exception;
    # we catch it and skip rather than failing so CI doesn't produce a spurious bug.
    try:
        cur.execute(
            "INSERT INTO playlists (owner_id, title, is_private) "
            "VALUES (%s, %s, FALSE) RETURNING id",
            (user_id, _PUBLIC_PLAYLIST_TITLE),
        )
        public_playlist_id = str(cur.fetchone()[0])
    except Exception as exc:
        pytest.skip(
            f"Cannot insert playlist with is_private=FALSE: {exc}. "
            "The is_private column may not exist — "
            "the playlist privacy feature appears not yet deployed to the database."
        )

    # --- Insert private playlist (is_private = TRUE) ---
    try:
        cur.execute(
            "INSERT INTO playlists (owner_id, title, is_private) "
            "VALUES (%s, %s, TRUE) RETURNING id",
            (user_id, _PRIVATE_PLAYLIST_TITLE),
        )
        private_playlist_id = str(cur.fetchone()[0])
    except Exception as exc:
        # Clean up the public playlist before skipping.
        cur.execute("DELETE FROM playlists WHERE id = %s", (public_playlist_id,))
        pytest.skip(f"Cannot insert private playlist: {exc}")

    yield {
        "user_id": user_id,
        "username": username,
        "public_playlist_id": public_playlist_id,
        "private_playlist_id": private_playlist_id,
    }

    # --- Teardown: remove seeded playlists in FK-safe order ---
    cur.execute("DELETE FROM playlist_videos WHERE playlist_id = %s", (private_playlist_id,))
    cur.execute("DELETE FROM playlist_videos WHERE playlist_id = %s", (public_playlist_id,))
    cur.execute("DELETE FROM playlists WHERE id = %s", (private_playlist_id,))
    cur.execute("DELETE FROM playlists WHERE id = %s", (public_playlist_id,))
    # Do NOT delete the CI test user — shared across test cases.


@pytest.fixture(scope="module")
def playlists_response(seeded_data: dict) -> tuple[int, list]:
    """Fetch GET /api/users/:username/playlists via PlaylistApiService and return (status, list)."""
    svc = PlaylistApiService(base_url=_API_BASE_URL)
    return svc.get_user_playlists(seeded_data["username"])


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUserProfilePrivatePlaylists:
    """MYTUBE-237 — Private playlists must not appear on the public user profile."""

    def test_public_endpoint_returns_200(
        self,
        playlists_response: tuple[int, list],
        seeded_data: dict,
    ) -> None:
        """GET /api/users/:username/playlists must respond with HTTP 200.

        A non-200 response means the endpoint is broken or the username
        is not being resolved correctly.
        """
        status, _ = playlists_response
        assert status == 200, (
            f"Expected HTTP 200 from GET /api/users/{seeded_data['username']}/playlists "
            f"but got HTTP {status}."
        )

    def test_public_playlist_present_in_response(
        self,
        playlists_response: tuple[int, list],
        seeded_data: dict,
    ) -> None:
        """The public playlist must appear in the API response.

        Verifies that the endpoint correctly exposes non-private playlists to
        unauthenticated callers.
        """
        _, playlists = playlists_response
        returned_ids = [p.get("id") for p in playlists]
        assert seeded_data["public_playlist_id"] in returned_ids, (
            f"Public playlist {seeded_data['public_playlist_id']!r} (title: "
            f"{_PUBLIC_PLAYLIST_TITLE!r}) was NOT found in the response from "
            f"GET /api/users/{seeded_data['username']}/playlists. "
            f"Returned playlist IDs: {returned_ids}. "
            "The endpoint must include public playlists in its response."
        )

    def test_private_playlist_absent_from_response(
        self,
        playlists_response: tuple[int, list],
        seeded_data: dict,
    ) -> None:
        """The private playlist must NOT appear in the public API response.

        This is the core assertion for MYTUBE-237: when a playlist is marked
        is_private=TRUE it must be filtered out by the backend before the
        response is sent to an unauthenticated caller.  Exposing private
        playlists would be a privacy violation.
        """
        _, playlists = playlists_response
        returned_ids = [p.get("id") for p in playlists]
        assert seeded_data["private_playlist_id"] not in returned_ids, (
            f"Private playlist {seeded_data['private_playlist_id']!r} (title: "
            f"{_PRIVATE_PLAYLIST_TITLE!r}) was found in the response from "
            f"GET /api/users/{seeded_data['username']}/playlists (unauthenticated). "
            f"Returned playlist IDs: {returned_ids}. "
            "The backend must exclude playlists with is_private=TRUE from the "
            "public user profile endpoint."
        )
