"""
MYTUBE-149: Access non-ready video — system returns 404 error.

Verifies that videos with status 'processing' or 'failed' are inaccessible
via the public GET /api/videos/:id endpoint, which must return HTTP 404.

The GET /api/videos/:id handler queries the database with:
    WHERE v.id = $1 AND v.status = 'ready'
so any non-ready video is treated as not found and the handler returns 404.

Preconditions
-------------
- A video exists in the database with status 'processing'.
- A video exists in the database with status 'failed'.
- A user (uploader) row exists to satisfy the FK constraint on videos.

Test steps
----------
1. Build and start the Go API server against the test database.
   The API runs its own migrations on startup.
2. Pre-insert a user and two video rows (one 'processing', one 'failed')
   via direct psycopg2 SQL into the now-migrated database.
3. Issue GET /api/videos/<processing_video_id> — assert HTTP 404.
4. Issue GET /api/videos/<failed_video_id>    — assert HTTP 404.

Environment variables
---------------------
- API_BINARY : Path to the pre-built Go binary
               (default: <repo_root>/api/mytube-api).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
               Database connection settings (all have sensible defaults
               matching the test DB configuration).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- The Go API server runs its own migrations at startup; we do NOT apply
  migrations via Python to avoid the duplicate-trigger conflict.
- Before starting the server we wipe all public tables so the API starts
  against a clean schema, guaranteeing test isolation.
- All database seeding is done via direct psycopg2 SQL after the server
  is up (and therefore after migrations have run).
- No Firebase credentials are required — the endpoint is unauthenticated.
"""
import json
import os
import subprocess
import sys
import uuid

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

_PORT = 18149
_STARTUP_TIMEOUT = 20.0

# Mock service account allows the GCS client to initialise without real GCP
# credentials.  The video endpoint never touches GCS, so this is safe.
_MOCK_SA_PATH = os.path.join(_REPO_ROOT, "testing", "fixtures", "mock_service_account.json")

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


def _drop_all_tables(conn) -> None:
    """Drop all public tables so the API server starts against a clean schema."""
    with conn.cursor() as cur:
        cur.execute(
            """
            DO $$ DECLARE
                r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
            """
        )
        cur.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE;")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def db_config() -> DBConfig:
    return DBConfig()


@pytest.fixture(scope="module")
def api_server(db_config: DBConfig):
    """
    Wipe the database, build (if needed), and start the Go API server.

    The server runs its own migrations at startup, so we only need to drop
    all tables first to guarantee a clean state.  We do NOT apply migrations
    via Python — doing so would conflict with the server's own migration runner
    (duplicate trigger error).

    Yields the ApiProcessService once /health is reachable, then stops the
    process on teardown.
    """
    # Wipe the database before starting so migrations run cleanly.
    pre_conn = psycopg2.connect(db_config.dsn())
    pre_conn.autocommit = True
    try:
        _drop_all_tables(pre_conn)
    finally:
        pre_conn.close()

    _build_binary()

    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        # Firebase verifier initialises but the video endpoint is unauthenticated.
        "FIREBASE_PROJECT_ID": os.getenv("FIREBASE_PROJECT_ID", "test-project"),
        # GCS client requires credentials even though the video endpoint never
        # calls GCS.  The mock service account satisfies the SDK's init path.
        "GOOGLE_APPLICATION_CREDENTIALS": os.getenv(
            "GOOGLE_APPLICATION_CREDENTIALS", _MOCK_SA_PATH
        ),
        # RAW_UPLOADS_BUCKET is required by the server at startup.
        "RAW_UPLOADS_BUCKET": os.getenv("RAW_UPLOADS_BUCKET", "test-raw-bucket"),
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
def db_conn(db_config: DBConfig, api_server):
    """
    Open a psycopg2 connection for seeding test data.

    Depends on *api_server* to ensure the server has already run its
    migrations before we insert rows.
    """
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_videos(db_conn):
    """
    Insert one user and two video rows (status='processing', status='failed').

    Returns a dict with the two video IDs.
    """
    processing_video_id = str(uuid.uuid4())
    failed_video_id = str(uuid.uuid4())
    firebase_uid = f"test-uid-mytube-149-{uuid.uuid4().hex[:8]}"

    with db_conn.cursor() as cur:
        # Insert a user to satisfy the FK on uploader_id.
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            RETURNING id
            """,
            (firebase_uid, "testuser149"),
        )
        uploader_id = str(cur.fetchone()[0])

        # Insert a video with status='processing'.
        cur.execute(
            """
            INSERT INTO videos (id, uploader_id, title, status)
            VALUES (%s, %s, %s, 'processing')
            """,
            (processing_video_id, uploader_id, "Processing Video MYTUBE-149"),
        )

        # Insert a video with status='failed'.
        cur.execute(
            """
            INSERT INTO videos (id, uploader_id, title, status)
            VALUES (%s, %s, %s, 'failed')
            """,
            (failed_video_id, uploader_id, "Failed Video MYTUBE-149"),
        )

    return {
        "processing_video_id": processing_video_id,
        "failed_video_id": failed_video_id,
    }


@pytest.fixture(scope="module")
def processing_video_response(api_server, seeded_videos):
    """Issue GET /api/videos/<processing_video_id> and return the response."""
    video_id = seeded_videos["processing_video_id"]
    status_code, body = api_server.get(f"/api/videos/{video_id}")
    return {"status_code": status_code, "body": body, "video_id": video_id}


@pytest.fixture(scope="module")
def failed_video_response(api_server, seeded_videos):
    """Issue GET /api/videos/<failed_video_id> and return the response."""
    video_id = seeded_videos["failed_video_id"]
    status_code, body = api_server.get(f"/api/videos/{video_id}")
    return {"status_code": status_code, "body": body, "video_id": video_id}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProcessingVideoReturns404:
    """GET /api/videos/:id for a video with status='processing' must return 404."""

    def test_status_code_is_404(self, processing_video_response):
        """The API must return HTTP 404 Not Found for a processing video."""
        assert processing_video_response["status_code"] == 404, (
            f"Expected HTTP 404 for processing video "
            f"(id={processing_video_response['video_id']}), "
            f"got {processing_video_response['status_code']}. "
            f"Response body: {processing_video_response['body']}"
        )

    def test_response_is_json(self, processing_video_response):
        """The 404 response body must be valid JSON."""
        try:
            json.loads(processing_video_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Expected JSON response body for processing video, "
                f"got: {processing_video_response['body']!r}. Error: {exc}"
            )

    def test_response_contains_error_field(self, processing_video_response):
        """The 404 JSON response must contain an 'error' field."""
        body = json.loads(processing_video_response["body"])
        assert "error" in body, (
            f"Expected 'error' field in 404 response for processing video, "
            f"got keys: {list(body.keys())}"
        )


class TestFailedVideoReturns404:
    """GET /api/videos/:id for a video with status='failed' must return 404."""

    def test_status_code_is_404(self, failed_video_response):
        """The API must return HTTP 404 Not Found for a failed video."""
        assert failed_video_response["status_code"] == 404, (
            f"Expected HTTP 404 for failed video "
            f"(id={failed_video_response['video_id']}), "
            f"got {failed_video_response['status_code']}. "
            f"Response body: {failed_video_response['body']}"
        )

    def test_response_is_json(self, failed_video_response):
        """The 404 response body must be valid JSON."""
        try:
            json.loads(failed_video_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Expected JSON response body for failed video, "
                f"got: {failed_video_response['body']!r}. Error: {exc}"
            )

    def test_response_contains_error_field(self, failed_video_response):
        """The 404 JSON response must contain an 'error' field."""
        body = json.loads(failed_video_response["body"])
        assert "error" in body, (
            f"Expected 'error' field in 404 response for failed video, "
            f"got keys: {list(body.keys())}"
        )
