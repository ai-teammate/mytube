"""
MYTUBE-148: Retrieve video metadata — hls_manifest_url uses configured CDN base URL.

Verifies that GET /api/videos/:id returns an hls_manifest_url that begins with
the configured CDN base URL and does not expose internal GCS paths.

Preconditions
-------------
- CDN_BASE_URL is set in the backend configuration.
- A video exists in the database with status='ready' and an hls_manifest_path
  stored as a GCS path (e.g. gs://bucket/videos/{id}/index.m3u8).

Test steps
----------
1. Build and start the Go API server with CDN_BASE_URL set.
2. Pre-insert a user and a 'ready' video with a known hls_manifest_path via
   direct DB access.
3. Call GET /api/videos/:id.
4. Assert HTTP 200.
5. Assert hls_manifest_url starts with CDN_BASE_URL.
6. Assert hls_manifest_url does NOT contain 'gs://' or other GCS path prefixes.

Environment variables
---------------------
- CDN_BASE_URL       : CDN base URL (default: "https://cdn.mytube.com").
                       Test is skipped when absent (cannot verify CDN behaviour).
- FIREBASE_PROJECT_ID: Firebase project ID required to initialise the verifier.
                       Test is skipped when absent.
- API_BINARY         : Path to the pre-built Go binary
                       (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                       Database connection settings (all have sensible defaults
                       matching the test DB configuration).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- Direct psycopg2 SQL is used for idempotent test-data setup (ON CONFLICT DO NOTHING).
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
- GET /api/videos/:id only returns videos with status='ready'.
"""
import json
import os
import subprocess
import sys

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18148
_STARTUP_TIMEOUT = 20.0

_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_CDN_BASE_URL = os.getenv("CDN_BASE_URL", "")
_RAW_UPLOADS_BUCKET = os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads")

# Deterministic test data
_UPLOADER_FIREBASE_UID = "test-uid-mytube-148-uploader"
_UPLOADER_USERNAME = "uploader148"
_VIDEO_TITLE = "CDN Manifest Test Video MYTUBE-148"
# A realistic HLS manifest GCS path that the API would store after transcoding
_HLS_BUCKET = "mytube-hls-output"
_HLS_OBJECT_PATH = "videos/test-mytube-148/index.m3u8"
_HLS_MANIFEST_PATH = f"gs://{_HLS_BUCKET}/{_HLS_OBJECT_PATH}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _db_is_reachable(config: DBConfig) -> bool:
    """Return True if a PostgreSQL connection can be established."""
    try:
        conn = psycopg2.connect(config.dsn(), connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


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
def require_infrastructure():
    """Skip the entire module when required infrastructure is unavailable."""
    if not _FIREBASE_PROJECT_ID:
        pytest.skip(
            "FIREBASE_PROJECT_ID not set — the API server cannot initialise "
            "the Firebase verifier without this variable."
        )
    if not _CDN_BASE_URL:
        pytest.skip(
            "CDN_BASE_URL not set — cannot verify that hls_manifest_url uses "
            "the CDN base URL. Set CDN_BASE_URL (e.g. https://cdn.mytube.com) to run this test."
        )
    cfg = DBConfig()
    if not _db_is_reachable(cfg):
        pytest.skip(
            f"PostgreSQL is not reachable at {cfg.host}:{cfg.port} — "
            "skipping integration test. Start the test database to run this test."
        )


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """
    Build (if needed) and start the Go API server with CDN_BASE_URL configured.

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
        "CDN_BASE_URL": _CDN_BASE_URL,
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
    """Open a direct psycopg2 connection to the test database."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_video(api_server, db_conn):
    """
    Insert an uploader user and a 'ready' video with a known hls_manifest_path.

    Uses ON CONFLICT DO NOTHING so the fixture is safe to re-run.

    Returns a dict with video_id and the expected CDN manifest URL.
    """
    # Insert uploader user (idempotent)
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO NOTHING
            """,
            (_UPLOADER_FIREBASE_UID, _UPLOADER_USERNAME),
        )
        cur.execute(
            "SELECT id FROM users WHERE firebase_uid = %s",
            (_UPLOADER_FIREBASE_UID,),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_UPLOADER_FIREBASE_UID!r}"
        )

    uploader_id = str(row[0])

    # Insert 'ready' video with a known hls_manifest_path (idempotent)
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO videos (uploader_id, title, status, hls_manifest_path)
            VALUES (%s, %s, 'ready', %s)
            ON CONFLICT DO NOTHING
            RETURNING id
            """,
            (uploader_id, _VIDEO_TITLE, _HLS_MANIFEST_PATH),
        )
        video_row = cur.fetchone()
        if video_row is None:
            # Row already existed; fetch its id
            cur.execute(
                "SELECT id FROM videos WHERE uploader_id = %s AND title = %s",
                (uploader_id, _VIDEO_TITLE),
            )
            video_row = cur.fetchone()

    if video_row is None:
        pytest.fail(f"Could not insert or find video row for title={_VIDEO_TITLE!r}")

    video_id = str(video_row[0])

    # Compute the expected CDN URL: strip gs://bucket prefix and prepend CDN base
    expected_cdn_url = _CDN_BASE_URL.rstrip("/") + "/" + _HLS_OBJECT_PATH

    return {
        "video_id": video_id,
        "expected_cdn_url": expected_cdn_url,
    }


@pytest.fixture(scope="module")
def video_response(api_server, seeded_video):
    """Issue GET /api/videos/:id and capture the response."""
    video_id = seeded_video["video_id"]
    status_code, body = api_server.get(f"/api/videos/{video_id}")
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVideoMetadataCDNManifestURL:
    """GET /api/videos/:id must return hls_manifest_url using the configured CDN base URL."""

    def test_status_code_is_200(self, video_response):
        """The response status must be HTTP 200 OK."""
        assert video_response["status_code"] == 200, (
            f"Expected HTTP 200, got {video_response['status_code']}. "
            f"Response body: {video_response['body']}"
        )

    def test_response_body_is_valid_json(self, video_response):
        """The response body must be parseable JSON."""
        try:
            json.loads(video_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\nBody: {video_response['body']}"
            )

    def test_hls_manifest_url_is_present(self, video_response):
        """The JSON response must contain an 'hls_manifest_url' key."""
        body = json.loads(video_response["body"])
        assert "hls_manifest_url" in body, (
            f"Expected 'hls_manifest_url' key in response, got keys: {list(body.keys())}"
        )

    def test_hls_manifest_url_is_not_null(self, video_response):
        """The 'hls_manifest_url' must not be null — the video has an HLS manifest."""
        body = json.loads(video_response["body"])
        assert body.get("hls_manifest_url") is not None, (
            "Expected 'hls_manifest_url' to be a non-null string, got null. "
            "Ensure the video row has hls_manifest_path set."
        )

    def test_hls_manifest_url_starts_with_cdn_base_url(self, video_response):
        """The 'hls_manifest_url' must start with the configured CDN_BASE_URL."""
        body = json.loads(video_response["body"])
        hls_url = body.get("hls_manifest_url", "")
        cdn_base = _CDN_BASE_URL.rstrip("/")
        assert hls_url.startswith(cdn_base), (
            f"Expected 'hls_manifest_url' to start with CDN base URL {cdn_base!r}, "
            f"but got: {hls_url!r}"
        )

    def test_hls_manifest_url_does_not_contain_gcs_scheme(self, video_response):
        """The 'hls_manifest_url' must NOT contain 'gs://' — no raw GCS paths exposed."""
        body = json.loads(video_response["body"])
        hls_url = body.get("hls_manifest_url", "")
        assert "gs://" not in hls_url, (
            f"Expected 'hls_manifest_url' to not contain 'gs://', "
            f"but got: {hls_url!r}. The API is leaking the internal GCS storage path."
        )

    def test_hls_manifest_url_does_not_contain_storage_googleapis(self, video_response):
        """The 'hls_manifest_url' must NOT contain 'storage.googleapis.com' — CDN URL only."""
        body = json.loads(video_response["body"])
        hls_url = body.get("hls_manifest_url", "")
        assert "storage.googleapis.com" not in hls_url, (
            f"Expected 'hls_manifest_url' to not contain 'storage.googleapis.com', "
            f"but got: {hls_url!r}. The API is returning a direct GCS URL instead of CDN."
        )

    def test_hls_manifest_url_matches_expected_cdn_url(self, video_response, seeded_video):
        """The full hls_manifest_url must exactly match the expected CDN-transformed URL."""
        body = json.loads(video_response["body"])
        hls_url = body.get("hls_manifest_url", "")
        expected = seeded_video["expected_cdn_url"]
        assert hls_url == expected, (
            f"Expected 'hls_manifest_url' to be {expected!r}, "
            f"but got: {hls_url!r}"
        )
