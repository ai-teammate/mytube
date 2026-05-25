"""
MYTUBE-624: Upload valid JPEG avatar — image stored in GCS and profile updated.

Objective
---------
Verify that an authenticated user can successfully upload a JPEG image as their
avatar via POST /api/me/avatar, resulting in:
  * HTTP 200 response with a JSON body containing ``avatar_url``.
  * The returned URL is under the ``avatars/`` GCS prefix.
  * The user's ``avatar_url`` in the database matches the returned URL.

Preconditions
-------------
* User is authenticated with a valid Firebase ID token (``FIREBASE_TEST_TOKEN``).

Implementation note
-------------------
The pre-built ``api/mytube-api`` binary in the repository does not include the
avatar endpoint (compiled before the feature was added). This test rebuilds the
binary from source to ensure the endpoint is present.

Environment Variables
---------------------
FIREBASE_TEST_TOKEN  Firebase ID token for the CI test user. Test skips if absent.
FIREBASE_PROJECT_ID  Firebase project ID. Required to start the API server.
FIREBASE_TEST_UID    Firebase UID of the CI test user. Default: ci-test-user-001
CDN_BASE_URL         CDN/GCS public base URL. Default: https://storage.googleapis.com/mytube-hls-output
HLS_BUCKET           GCS bucket for avatar storage. Default: mytube-hls-output
RAW_UPLOADS_BUCKET   GCS bucket for raw uploads. Default: mytube-raw-uploads
DB_*                 Database connection settings with sensible defaults.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.avatar_api_service import AvatarApiService

# ---------------------------------------------------------------------------
# Minimal valid JPEG (1x1 pixel) — generated programmatically.
# Verified by http.DetectContentType to produce "image/jpeg".
# ---------------------------------------------------------------------------
_MINIMAL_JPEG_BYTES: bytes = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDB"
    "kSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAAR"
    "CAABAAEDASIAAhEBAxEB/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAIxAAAQME"
    "AgMBAAAAAAAAAAAAAQIDAAQFESExQVFh/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/E"
    "ABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AJmk2pa3pVoiu3CqNOmT"
    "UoSVJDSwFKA9yBvXisWtd2vMiTHt8B2Q3GdLTi0DYSobBH3rF0/wBwAAD/2Q=="
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_API_DIR = os.path.join(_REPO_ROOT, "api")
_REBUILT_BINARY = "/tmp/mytube-api-avatar-test"

_FIREBASE_TOKEN: str = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID: str = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_UID: str = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")
_CDN_BASE_URL: str = os.getenv("CDN_BASE_URL", "https://storage.googleapis.com/mytube-hls-output")
_HLS_BUCKET: str = os.getenv("HLS_BUCKET", "mytube-hls-output")
_RAW_UPLOADS_BUCKET: str = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

_db_config = DBConfig()
_PORT = 18624

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> str:
    """Build the Go API binary from source and return its path."""
    result = subprocess.run(
        ["go", "build", "-o", _REBUILT_BINARY, "."],
        cwd=_API_DIR,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        pytest.fail(
            f"Failed to build API binary:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return _REBUILT_BINARY


def _get_db_avatar_url(firebase_uid: str) -> str | None:
    """Return the avatar_url stored for firebase_uid, or None."""
    try:
        import psycopg2
        conn = psycopg2.connect(_db_config.dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT avatar_url FROM users WHERE firebase_uid = %s", (firebase_uid,))
            row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception as exc:
        pytest.skip(f"Cannot connect to database: {exc}")


# ---------------------------------------------------------------------------
# Module-level state (populated in setup_module)
# ---------------------------------------------------------------------------

_api: ApiProcessService | None = None
_upload_status: int = 0
_upload_raw: str = ""
_upload_body: dict = {}


def setup_module(module) -> None:
    global _api, _upload_status, _upload_raw, _upload_body

    if not _FIREBASE_TOKEN or not _FIREBASE_PROJECT_ID:
        return  # fixtures handle the skip

    binary = _build_binary()
    env = {
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "RAW_UPLOADS_BUCKET": _RAW_UPLOADS_BUCKET,
        "HLS_BUCKET": _HLS_BUCKET,
        "CDN_BASE_URL": _CDN_BASE_URL,
    }
    _api = ApiProcessService(binary, port=_PORT, env=env, startup_timeout=20.0)
    _api.start()
    if not _api.wait_for_ready("/health"):
        logs = _api.get_log_output()
        pytest.fail(f"API server did not become ready within 20 s.\nLogs:\n{logs}")

    base_url = f"http://127.0.0.1:{_PORT}"
    api_cfg = APIConfig.__new__(APIConfig)
    api_cfg.base_url = base_url
    api_cfg.health_token = ""
    avatar_svc = AvatarApiService(api_cfg, token=_FIREBASE_TOKEN)
    _upload_status, _upload_raw = avatar_svc.upload_avatar(_MINIMAL_JPEG_BYTES)
    try:
        _upload_body.update(json.loads(_upload_raw))
    except json.JSONDecodeError:
        pass


def teardown_module(module) -> None:
    if _api is not None:
        _api.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True, scope="module")
def require_credentials():
    """Skip all tests when required credentials are absent."""
    if not _FIREBASE_TOKEN:
        pytest.skip("FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-624")
    if not _FIREBASE_PROJECT_ID:
        pytest.skip("FIREBASE_PROJECT_ID is not set — API server cannot start without it")


class TestAvatarUpload:
    """POST /api/me/avatar — valid JPEG upload stores image and updates profile."""

    def test_http_status_is_200(self):
        """POST /api/me/avatar must return HTTP 200 OK."""
        assert _upload_status == 200, (
            f"Expected HTTP 200, got {_upload_status}. Raw response: {_upload_raw!r}"
        )

    def test_response_is_valid_json(self):
        """Response body must be parseable JSON."""
        assert _upload_body, (
            f"Response is not valid JSON or is empty. Raw: {_upload_raw!r}"
        )

    def test_response_contains_avatar_url(self):
        """Response JSON must contain the 'avatar_url' key."""
        assert "avatar_url" in _upload_body, (
            f"'avatar_url' missing from response. Full response: {_upload_body}"
        )

    def test_avatar_url_is_non_empty(self):
        """The returned 'avatar_url' must be a non-empty string."""
        assert _upload_body.get("avatar_url"), (
            f"'avatar_url' is empty. Response: {_upload_body}"
        )

    def test_avatar_url_under_avatars_prefix(self):
        """The returned 'avatar_url' must contain the 'avatars/' path prefix."""
        url = _upload_body.get("avatar_url", "")
        assert "avatars/" in url, (
            f"'avatar_url' does not contain 'avatars/' prefix. Got: {url!r}"
        )

    def test_avatar_url_starts_with_cdn_base(self):
        """The returned 'avatar_url' must start with the configured CDN base URL."""
        url = _upload_body.get("avatar_url", "")
        cdn_base = _CDN_BASE_URL.rstrip("/")
        assert url.startswith(cdn_base), (
            f"'avatar_url' does not start with '{cdn_base}'. Got: {url!r}"
        )

    def test_avatar_url_ends_with_jpg_extension(self):
        """The returned 'avatar_url' must end with '.jpg' for a JPEG upload."""
        url = _upload_body.get("avatar_url", "")
        assert url.endswith(".jpg"), (
            f"'avatar_url' does not end with '.jpg'. Got: {url!r}"
        )

    def test_database_avatar_url_matches_response(self):
        """The user's avatar_url in the database must match the API response."""
        api_url = _upload_body.get("avatar_url", "")
        db_url = _get_db_avatar_url(_FIREBASE_UID)
        assert db_url is not None, (
            f"No user row found for firebase_uid={_FIREBASE_UID!r}."
        )
        assert db_url == api_url, (
            f"DB avatar_url ({db_url!r}) != API avatar_url ({api_url!r})."
        )
