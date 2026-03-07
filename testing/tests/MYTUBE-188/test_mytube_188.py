"""
MYTUBE-188: Update video metadata as owner — changes successfully saved via PUT.

Verifies that the owner of a video can update its metadata using the
PUT /api/videos/:id endpoint and that all modified fields (title, description,
category_id, tags) are reflected in both the response and the database.

Preconditions
-------------
- User is authenticated and owns a video (pre-seeded via fixture).

Test steps
----------
1. Build and start the Go API server with valid DB credentials.
2. Pre-insert a user row via direct DB access using a known firebase_uid.
3. Pre-insert a video row owned by that user with initial metadata.
4. Obtain a valid category_id from the categories table (seed one if empty).
5. Send PUT /api/videos/:id with Authorization: Bearer <FIREBASE_TEST_TOKEN>
   and a JSON body containing new title, description, category_id, and tags.
6. Assert HTTP 200 and verify all updated fields in the response body.
7. Send GET /api/videos/:id and verify the updated values are persisted.
8. Query the database directly to confirm category_id and tags are persisted.

Environment variables
---------------------
- FIREBASE_TEST_TOKEN  : Firebase ID token for the test user.
                         Test is skipped when absent.
- FIREBASE_PROJECT_ID  : Firebase project ID required to initialise the
                         verifier.  Test is skipped when absent.
- API_BINARY           : Path to the pre-built Go binary
                         (default: <repo_root>/api/mytube-api).
- FIREBASE_TEST_UID    : The firebase_uid stored in the users row that must
                         match the test token (default: test-uid-mytube-188).
- DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE :
                         Database connection settings (all have sensible
                         defaults matching the test DB configuration).

Architecture notes
------------------
- All subprocess / HTTP I/O is encapsulated in ApiProcessService.
- UserService is used for idempotent test-user seeding (find_by_firebase_uid + create_user).
- CategoryService is used to obtain or seed a valid category_id.
- VideoService is used to seed the initial video row with tags.
- No hardcoded waits; ApiProcessService.wait_for_ready() polls /health.
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
from testing.components.services.category_service import CategoryService
from testing.components.services.user_service import UserService
from testing.components.services.video_service import VideoService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join(_REPO_ROOT, "api", "mytube-api")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18188
_STARTUP_TIMEOUT = 20.0

# Firebase test credentials (required at runtime; test skips when absent).
_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")

# The firebase_uid that the test token belongs to.
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "test-uid-mytube-188")

# Initial video metadata (state before the PUT).
_INITIAL_TITLE = "Original Title MYTUBE-188"
_INITIAL_DESCRIPTION = "Original description for MYTUBE-188"
_INITIAL_TAGS = ["initial-tag"]

# Updated metadata submitted via PUT /api/videos/:id.
_UPDATED_TITLE = "Updated Title MYTUBE-188"
_UPDATED_DESCRIPTION = "Updated description for MYTUBE-188"
_UPDATED_TAGS = ["updated", "metadata", "test"]

# Name used when seeding a test category (if none already exist).
_TEST_CATEGORY_NAME = "test-category-mytube-188"


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
            "FIREBASE_TEST_TOKEN not set — skipping PUT /api/videos/:id integration test. "
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
        "RAW_UPLOADS_BUCKET": os.getenv("RAW_UPLOADS_BUCKET", "mytube-raw-uploads"),
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
def seeded_user(api_server, db_conn):
    """Insert a user row with a known firebase_uid; return a dict with the user data."""
    user_svc = UserService(db_conn)
    existing = user_svc.find_by_firebase_uid(_FIREBASE_TEST_UID)
    if existing is not None:
        return existing
    user_id = user_svc.create_user(_FIREBASE_TEST_UID, "testuser188")
    return {"id": user_id, "firebase_uid": _FIREBASE_TEST_UID, "username": "testuser188"}


@pytest.fixture(scope="module")
def category_id(db_conn) -> int:
    """Return a valid category ID.

    Uses the first available category in the table.  If no categories exist,
    inserts a dedicated test category and returns its ID.
    """
    cat_svc = CategoryService(db_conn)
    cid = cat_svc.get_first_id()
    if cid is not None:
        return cid
    return cat_svc.insert_category(_TEST_CATEGORY_NAME)


@pytest.fixture(scope="module")
def seeded_video(seeded_user, db_conn):
    """Insert a video row owned by the test user with initial metadata.

    Returns a dict containing the video id.
    """
    video_svc = VideoService(db_conn)
    video_id = video_svc.insert_video_with_details(
        uploader_id=seeded_user["id"],
        title=_INITIAL_TITLE,
        description=_INITIAL_DESCRIPTION,
        status="ready",
        tags=_INITIAL_TAGS,
    )
    return {"id": video_id}


@pytest.fixture(scope="module")
def put_video_response(api_server, seeded_video, category_id):
    """Issue PUT /api/videos/:id with updated metadata; capture the response."""
    payload = json.dumps(
        {
            "title": _UPDATED_TITLE,
            "description": _UPDATED_DESCRIPTION,
            "category_id": category_id,
            "tags": _UPDATED_TAGS,
        }
    ).encode()

    video_id = seeded_video["id"]
    status_code, body = api_server.put(
        f"/api/videos/{video_id}",
        body=payload,
        headers={
            "Authorization": f"Bearer {_FIREBASE_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    return {"status_code": status_code, "body": body, "video_id": video_id}


@pytest.fixture(scope="module")
def get_video_response(api_server, put_video_response):
    """Issue GET /api/videos/:id after the PUT to verify persistence of changes."""
    video_id = put_video_response["video_id"]
    status_code, body = api_server.get(f"/api/videos/{video_id}")
    return {"status_code": status_code, "body": body}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUpdateVideoMetadata:
    """PUT /api/videos/:id as owner must update all metadata fields and persist them."""

    # --- PUT response: HTTP status ---

    def test_put_status_code_is_200(self, put_video_response):
        """The response status must be HTTP 200 OK."""
        assert put_video_response["status_code"] == 200, (
            f"Expected HTTP 200, got {put_video_response['status_code']}. "
            f"Response body: {put_video_response['body']}"
        )

    def test_put_response_is_valid_json(self, put_video_response):
        """The response body must be parseable JSON."""
        try:
            json.loads(put_video_response["body"])
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON: {exc}\nBody: {put_video_response['body']}"
            )

    # --- PUT response: updated field values ---

    def test_put_response_title_is_updated(self, put_video_response):
        """The PUT response must contain the new title."""
        body = json.loads(put_video_response["body"])
        assert body.get("title") == _UPDATED_TITLE, (
            f"Expected title={_UPDATED_TITLE!r}, got {body.get('title')!r}"
        )

    def test_put_response_description_is_updated(self, put_video_response):
        """The PUT response must contain the new description."""
        body = json.loads(put_video_response["body"])
        assert body.get("description") == _UPDATED_DESCRIPTION, (
            f"Expected description={_UPDATED_DESCRIPTION!r}, "
            f"got {body.get('description')!r}"
        )

    def test_put_response_category_id_is_updated(self, put_video_response, category_id):
        """The PUT response must return the submitted category_id."""
        body = json.loads(put_video_response["body"])
        assert body.get("category_id") == category_id, (
            f"Expected category_id={category_id}, "
            f"got {body.get('category_id')!r}. "
            f"Full response body: {put_video_response['body']}"
        )

    def test_put_response_tags_are_updated(self, put_video_response):
        """The PUT response must contain the new tags."""
        body = json.loads(put_video_response["body"])
        assert sorted(body.get("tags", [])) == sorted(_UPDATED_TAGS), (
            f"Expected tags={sorted(_UPDATED_TAGS)}, "
            f"got {sorted(body.get('tags', []))}"
        )

    # --- GET response: persistence of changes ---

    def test_get_status_code_is_200(self, get_video_response):
        """The GET /api/videos/:id response must be HTTP 200 OK."""
        assert get_video_response["status_code"] == 200, (
            f"Expected HTTP 200 on GET, got {get_video_response['status_code']}. "
            f"Body: {get_video_response['body']}"
        )

    def test_get_response_title_persisted(self, get_video_response):
        """The updated title must be returned by the subsequent GET."""
        body = json.loads(get_video_response["body"])
        assert body.get("title") == _UPDATED_TITLE, (
            f"Title not persisted: expected {_UPDATED_TITLE!r}, "
            f"got {body.get('title')!r}"
        )

    def test_get_response_description_persisted(self, get_video_response):
        """The updated description must be returned by the subsequent GET."""
        body = json.loads(get_video_response["body"])
        assert body.get("description") == _UPDATED_DESCRIPTION, (
            f"Description not persisted: expected {_UPDATED_DESCRIPTION!r}, "
            f"got {body.get('description')!r}"
        )

    def test_get_response_category_id_persisted(self, get_video_response, category_id):
        """The updated category_id must be returned by the subsequent GET."""
        body = json.loads(get_video_response["body"])
        assert body.get("category_id") == category_id, (
            f"category_id not persisted in GET response: expected {category_id}, "
            f"got {body.get('category_id')!r}. "
            f"Full GET response body: {get_video_response['body']}"
        )

    def test_get_response_tags_persisted(self, get_video_response):
        """The updated tags must be returned by the subsequent GET."""
        body = json.loads(get_video_response["body"])
        assert sorted(body.get("tags", [])) == sorted(_UPDATED_TAGS), (
            f"Tags not persisted: expected {sorted(_UPDATED_TAGS)}, "
            f"got {sorted(body.get('tags', []))}"
        )

    # --- Database: direct persistence verification ---

    def test_db_title_persisted(self, put_video_response, db_conn):
        """The videos table must reflect the new title after the PUT."""
        video_id = put_video_response["video_id"]
        with db_conn.cursor() as cur:
            cur.execute("SELECT title FROM videos WHERE id = %s", (video_id,))
            row = cur.fetchone()
        assert row is not None, f"Video row not found in DB for id={video_id!r}"
        assert row[0] == _UPDATED_TITLE, (
            f"Expected DB title={_UPDATED_TITLE!r}, got {row[0]!r}"
        )

    def test_db_description_persisted(self, put_video_response, db_conn):
        """The videos table must reflect the new description after the PUT."""
        video_id = put_video_response["video_id"]
        with db_conn.cursor() as cur:
            cur.execute("SELECT description FROM videos WHERE id = %s", (video_id,))
            row = cur.fetchone()
        assert row is not None, f"Video row not found in DB for id={video_id!r}"
        assert row[0] == _UPDATED_DESCRIPTION, (
            f"Expected DB description={_UPDATED_DESCRIPTION!r}, got {row[0]!r}"
        )

    def test_db_category_id_persisted(self, put_video_response, db_conn, category_id):
        """The videos table must reflect the new category_id after the PUT."""
        video_id = put_video_response["video_id"]
        with db_conn.cursor() as cur:
            cur.execute("SELECT category_id FROM videos WHERE id = %s", (video_id,))
            row = cur.fetchone()
        assert row is not None, f"Video row not found in DB for id={video_id!r}"
        assert row[0] == category_id, (
            f"Expected DB category_id={category_id}, got {row[0]!r}"
        )

    def test_db_tags_persisted(self, put_video_response, db_conn):
        """The video_tags table must contain exactly the new tags after the PUT."""
        video_id = put_video_response["video_id"]
        with db_conn.cursor() as cur:
            cur.execute(
                "SELECT tag FROM video_tags WHERE video_id = %s ORDER BY tag",
                (video_id,),
            )
            rows = cur.fetchall()
        db_tags = [row[0] for row in rows]
        assert sorted(db_tags) == sorted(_UPDATED_TAGS), (
            f"Expected DB tags={sorted(_UPDATED_TAGS)}, got {sorted(db_tags)}"
        )
