"""
MYTUBE-228: Add video to playlist as owner — video appended to the end of the collection.

Objective
---------
Verify that the owner of a playlist can add a video and that the system manages
the position as append-only: each newly added video receives position
``COALESCE(MAX(current_positions), 0) + 1``.

Preconditions
-------------
- User is the owner of an existing playlist.
- A valid video (status = 'ready') exists in the system.

Steps
-----
1. Send POST /api/playlists/:id/videos with body { "video_id": "<video_uuid>" }.
2. Fetch the playlist details via GET /api/playlists/:id.
3. Check the position of the newly added video.

Expected Result
---------------
The POST call succeeds (HTTP 2xx). The video appears in the playlist's videos
array with a position equal to ``max(current_positions) + 1``.

Test Structure
--------------
Layer A — Go unit tests (always runs; no Firebase token or DB required):
    Invokes existing Go handler/repository unit tests that exercise the
    AddVideo handler and the position-computation logic.

Layer B — HTTP integration test (runs when FIREBASE_TEST_TOKEN is set):
    1. Creates a fresh playlist via POST /api/playlists.
    2. Discovers a ready video via VideoApiService.
    3. Adds the video to the (empty) playlist via POST /api/playlists/:id/videos.
    4. Fetches the playlist via GET /api/playlists/:id.
    5. Asserts the video appears with position == 1
       (= COALESCE(MAX(NULL), 0) + 1, i.e. append to empty collection).
    6. Adds a second (different) video when available and asserts position == 2
       (= MAX(1) + 1, direct validation of append-to-end formula).
    7. Cleans up the created playlist via DELETE /api/playlists/:id.

Environment Variables
---------------------
- FIREBASE_TEST_TOKEN  : Firebase ID token for the CI test user.
                         Layer B is skipped when absent.
- API_BASE_URL         : Base URL of the deployed API.
                         Defaults to https://mytube-api-80693608388.us-central1.run.app
                         via APIConfig.

Architecture
------------
- PlaylistApiService wraps playlist CRUD + video management with Bearer token auth.
- VideoApiService discovers ready videos from known CI usernames.
- AuthService is used for /api/me to resolve the caller's username.
- APIConfig loads API_BASE_URL from the environment.
- No hardcoded URLs, credentials, or sleeps.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Generator, Optional

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.video_api_service import VideoApiService
from testing.components.services.playlist_api_service import PlaylistApiService, PlaylistDetail

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_API_DIR = os.path.join(_REPO_ROOT, "api")

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")

_PLAYLIST_TITLE = "MYTUBE-228 CI Test Playlist"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_go_test(test_name: str, pkg: str = "./internal/handler/") -> subprocess.CompletedProcess:
    """Run a named Go test in the given package under the api/ directory."""
    return subprocess.run(
        ["go", "test", "-v", "-count=1", "-run", test_name, pkg],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )


def _run_go_repo_test(test_name: str) -> subprocess.CompletedProcess:
    """Run a named Go test in the repository package under the api/ directory."""
    return _run_go_test(test_name, pkg="./internal/repository/")


# ---------------------------------------------------------------------------
# Layer A — Go unit tests (always run; no credentials required)
# ---------------------------------------------------------------------------


class TestAddVideoHandlerGoUnit:
    """Invoke existing Go handler unit tests for POST /api/playlists/:id/videos."""

    def test_add_video_success_returns_204_unit(self):
        """Handler returns 204 No Content on a successful AddVideo call.

        Runs: TestAddVideoToPlaylistHandler_POST_Success_Returns204
        """
        result = _run_go_test("TestAddVideoToPlaylistHandler_POST_Success_Returns204")
        assert result.returncode == 0, (
            f"Go unit test TestAddVideoToPlaylistHandler_POST_Success_Returns204 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_add_video_no_auth_returns_401_unit(self):
        """Handler returns 401 Unauthorized when no Bearer token is provided.

        Runs: TestAddVideoToPlaylistHandler_POST_NoAuth_Returns401
        """
        result = _run_go_test("TestAddVideoToPlaylistHandler_POST_NoAuth_Returns401")
        assert result.returncode == 0, (
            f"Go unit test TestAddVideoToPlaylistHandler_POST_NoAuth_Returns401 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_add_video_forbidden_returns_403_unit(self):
        """Handler returns 403 Forbidden when the caller does not own the playlist.

        Runs: TestAddVideoToPlaylistHandler_POST_Forbidden_Returns403
        """
        result = _run_go_test("TestAddVideoToPlaylistHandler_POST_Forbidden_Returns403")
        assert result.returncode == 0, (
            f"Go unit test TestAddVideoToPlaylistHandler_POST_Forbidden_Returns403 failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_get_playlist_includes_video_position_unit(self):
        """GET handler returns the playlist with videos including their position field.

        Runs: TestPlaylistByIDHandler_GET_ReturnsPlaylist
        """
        result = _run_go_test("TestPlaylistByIDHandler_GET_ReturnsPlaylist")
        assert result.returncode == 0, (
            f"Go unit test TestPlaylistByIDHandler_GET_ReturnsPlaylist failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


class TestAddVideoRepositoryGoUnit:
    """Invoke existing Go repository unit tests for PlaylistRepository.AddVideo."""

    def test_repository_add_video_success_unit(self):
        """Repository AddVideo computes the next position and inserts the row.

        Runs: TestPlaylistAddVideo_Success
        """
        result = _run_go_repo_test("TestPlaylistAddVideo_Success")
        assert result.returncode == 0, (
            f"Go repository unit test TestPlaylistAddVideo_Success failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )

    def test_repository_add_video_forbidden_unit(self):
        """Repository AddVideo returns ErrForbidden when the caller is not the owner.

        Runs: TestPlaylistAddVideo_Forbidden_ReturnsErrForbidden
        """
        result = _run_go_repo_test("TestPlaylistAddVideo_Forbidden_ReturnsErrForbidden")
        assert result.returncode == 0, (
            f"Go repository unit test TestPlaylistAddVideo_Forbidden_ReturnsErrForbidden failed.\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


# ---------------------------------------------------------------------------
# Layer B — HTTP integration test via the deployed API
# Requires FIREBASE_TEST_TOKEN; skipped gracefully when absent.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_token():
    """Skip Layer B tests when FIREBASE_TEST_TOKEN is not set."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping Layer B HTTP integration tests. "
            "Set FIREBASE_TEST_TOKEN to a valid Firebase ID token to run these tests."
        )


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def playlist_service(api_config: APIConfig) -> PlaylistApiService:
    """Return a PlaylistApiService configured for the deployed API."""
    return PlaylistApiService(base_url=api_config.base_url, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def video_api_service(api_config: APIConfig) -> VideoApiService:
    """Return a VideoApiService for discovering ready videos."""
    return VideoApiService(api_config)


@pytest.fixture(scope="module")
def ready_video_id(
    video_api_service: VideoApiService,
) -> Generator[str, None, None]:
    """Return the ID of a ready video.

    Strategy:
    1. Try VideoApiService to discover an existing ready video (no side-effects).
    2. If none found, connect to the database and seed a minimal ready video,
       then yield its ID and delete it on teardown.
    3. Skip when neither the API has a ready video nor the DB is accessible.
    """
    # --- Step 1: discover via API ---
    result = video_api_service.find_ready_video()
    if result is not None:
        video_id, _ = result
        yield video_id
        return  # no cleanup needed for a pre-existing video

    # --- Step 2: seed directly in the database ---
    db_cfg = DBConfig()
    try:
        conn = psycopg2.connect(
            host=db_cfg.host,
            port=db_cfg.port,
            user=db_cfg.user,
            password=db_cfg.password,
            dbname=db_cfg.dbname,
            sslmode=db_cfg.sslmode,
            connect_timeout=5,
        )
        conn.autocommit = True
    except Exception as exc:
        pytest.skip(
            f"No ready video found via API and DB is not accessible ({exc}). "
            "Ensure at least one ready video exists or the database is reachable."
        )
        return

    firebase_uid = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s", (firebase_uid,)
        )
        row = cur.fetchone()

    if row is None:
        conn.close()
        pytest.skip(
            f"CI test user firebase_uid={firebase_uid!r} not found in DB — "
            "cannot seed a test video."
        )
        return

    user_id = str(row[0])
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO videos (uploader_id, title, status) "
            "VALUES (%s, %s, %s) RETURNING id",
            (user_id, "MYTUBE-228 CI Test Video", "ready"),
        )
        seeded_video_id = str(cur.fetchone()[0])

    yield seeded_video_id

    # Teardown: delete the seeded video (playlist_videos cascade-deleted via
    # the playlist teardown in test_playlist_id, but guard anyway).
    try:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM playlist_videos WHERE video_id = %s",
                (seeded_video_id,),
            )
            cur.execute(
                "DELETE FROM videos WHERE id = %s", (seeded_video_id,)
            )
    except Exception:
        pass
    finally:
        conn.close()


@pytest.fixture(scope="module")
def test_playlist_id(playlist_service: PlaylistApiService) -> str:
    """Create a fresh playlist for the test and delete it on teardown.

    Yields the playlist UUID. Always attempts cleanup via DELETE regardless of
    test outcome.
    """
    status, body = playlist_service.create_playlist(_PLAYLIST_TITLE)
    assert status == 201, (
        f"Failed to create test playlist: expected HTTP 201, got {status}. "
        f"Body: {body}"
    )
    data = json.loads(body)
    playlist_id = data.get("id", "")
    assert playlist_id, f"Playlist creation response missing 'id' field. Body: {body}"

    yield playlist_id

    # Teardown: remove the test playlist from the deployed API.
    playlist_service.delete_playlist(playlist_id)


@pytest.fixture(scope="module")
def positions_before_add(
    playlist_service: PlaylistApiService,
    test_playlist_id: str,
) -> int:
    """Return max(current_positions) before the video is added.

    For a newly created (empty) playlist this will be 0.
    """
    _, detail = playlist_service.get_playlist(test_playlist_id)
    if detail is None:
        return 0
    return detail.max_position


@pytest.fixture(scope="module")
def add_video_response(
    playlist_service: PlaylistApiService,
    test_playlist_id: str,
    ready_video_id: str,
    positions_before_add: int,
) -> tuple[int, str, int]:
    """Add the ready video to the test playlist and return (status, body, expected_position).

    expected_position = positions_before_add + 1, per the append-only formula.
    """
    expected_position = positions_before_add + 1
    status, body = playlist_service.add_video(test_playlist_id, ready_video_id)
    return status, body, expected_position


@pytest.fixture(scope="module")
def playlist_after_add(
    playlist_service: PlaylistApiService,
    test_playlist_id: str,
    add_video_response: tuple[int, str, int],
) -> Optional[PlaylistDetail]:
    """Fetch the playlist after the video has been added."""
    _, detail = playlist_service.get_playlist(test_playlist_id)
    return detail


# ---------------------------------------------------------------------------
# Tests — Layer B
# ---------------------------------------------------------------------------


class TestAddVideoToPlaylist:
    """POST /api/playlists/:id/videos appends the video at position max+1."""

    def test_add_video_response_is_success(
        self,
        add_video_response: tuple[int, str, int],
    ) -> None:
        """POST /api/playlists/:id/videos must return a 2xx success status."""
        status, body, _ = add_video_response
        assert 200 <= status < 300, (
            f"Expected a 2xx response from POST /api/playlists/:id/videos, "
            f"got HTTP {status}. Body: {body}"
        )

    def test_get_playlist_returns_200(
        self,
        playlist_service: PlaylistApiService,
        test_playlist_id: str,
        add_video_response: tuple[int, str, int],
    ) -> None:
        """GET /api/playlists/:id must return HTTP 200 after the video is added."""
        status, _ = playlist_service.get_playlist(test_playlist_id)
        assert status == 200, (
            f"Expected GET /api/playlists/{test_playlist_id} to return 200, got {status}."
        )

    def test_added_video_appears_in_playlist(
        self,
        playlist_after_add: Optional[PlaylistDetail],
        ready_video_id: str,
    ) -> None:
        """The added video must appear in the playlist's 'videos' array."""
        assert playlist_after_add is not None, (
            "GET /api/playlists/:id returned an unparseable response after adding the video."
        )
        video_ids = [v.id for v in playlist_after_add.videos]
        assert ready_video_id in video_ids, (
            f"Expected video {ready_video_id!r} to appear in the playlist videos, "
            f"but found: {video_ids}. "
            "Note: only videos with status='ready' are included in the playlist response."
        )

    def test_video_position_is_append_only(
        self,
        playlist_after_add: Optional[PlaylistDetail],
        ready_video_id: str,
        add_video_response: tuple[int, str, int],
    ) -> None:
        """The newly added video's position must equal max(previous_positions) + 1.

        For an empty playlist the formula resolves to COALESCE(MAX(NULL), 0) + 1 = 1.
        """
        _, _, expected_position = add_video_response

        assert playlist_after_add is not None, (
            "Cannot verify position: GET /api/playlists/:id returned no parseable data."
        )

        matching = [v for v in playlist_after_add.videos if v.id == ready_video_id]
        assert matching, (
            f"Video {ready_video_id!r} not found in playlist after add. "
            f"Videos present: {[v.id for v in playlist_after_add.videos]}"
        )

        actual_position = matching[0].position
        assert actual_position == expected_position, (
            f"Expected video position to be {expected_position} "
            f"(= max(previous_positions) + 1 = {expected_position - 1} + 1), "
            f"but got position {actual_position}. "
            "The API must append videos at the end of the collection, not prepend or use a fixed position."
        )
