"""
MYTUBE-649: GCS object key versioning — unique path generated for consecutive uploads.

Objective
---------
Verify that every avatar upload produces a unique GCS object key path to prevent
CDN stale content issues.

Fix context (MYTUBE-642)
------------------------
Before the fix, the handler used ``avatars/{user.ID}.{ext}`` — a static path per
user/extension pair.  The browser/CDN cached the unchanged URL and served the old
image after re-upload.

The fix changed the key to ``avatars/{user.ID}/{uuid}.{ext}``, inserting a random
UUID component so each upload produces a distinct, cache-busting URL.

Test steps
----------
1. Build the Go API binary, start the API server.
2. Seed a test user row in the database.
3. POST /api/me/avatar with a first valid PNG image → capture avatar_url_a.
4. POST /api/me/avatar with a second valid PNG image → capture avatar_url_b.
5. Assert both uploads return HTTP 200.
6. Assert avatar_url_a != avatar_url_b (unique versioned GCS key per upload).
7. Assert the URL path follows the expected pattern:
   ``avatars/{userId}/{version}.ext`` (directory-based versioning, not flat key).

Expected result
---------------
Both uploads return HTTP 200.  The returned avatar_url values differ between
uploads, confirming that a UUID (or equivalent unique component) is embedded in
the GCS object key.

Environment variables
---------------------
FIREBASE_TEST_TOKEN    : Firebase ID token for the test user (required).
FIREBASE_PROJECT_ID    : Firebase project ID for the verifier (required).
FIREBASE_TEST_UID      : firebase_uid stored in the DB row (default: ci-test-user-001).
API_BINARY             : Path to the pre-built Go binary (default: /tmp/mytube-api-649).
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE : DB settings.
HLS_BUCKET             : GCS bucket used by the API for avatar storage.
CDN_BASE_URL           : Public CDN base URL for the HLS bucket.
"""
from __future__ import annotations

import json
import os
import re
import struct
import subprocess
import sys
import zlib

import psycopg2
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.db_config import DBConfig
from testing.components.services.api_process_service import ApiProcessService
from testing.components.services.avatar_api_service import AvatarApiService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
_DEFAULT_BINARY = os.path.join("/tmp", "mytube-api-649")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18649
_STARTUP_TIMEOUT = 20.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

_HLS_BUCKET = os.getenv("HLS_BUCKET", "mytube-hls-output")
_CDN_BASE_URL = os.getenv(
    "CDN_BASE_URL", "https://storage.googleapis.com/mytube-hls-output"
)
_GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

# UUID pattern (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Minimal PNG helpers
# ---------------------------------------------------------------------------


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


def _make_1x1_png(r: int, g: int, b: int) -> bytes:
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)
    raw_row = bytes([0, r, g, b])
    compressed = zlib.compress(raw_row)
    idat = _png_chunk(b"IDAT", compressed)
    iend = _png_chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


_IMAGE_A: bytes = _make_1x1_png(255, 0, 0)   # red pixel
_IMAGE_B: bytes = _make_1x1_png(0, 255, 0)   # green pixel

assert _IMAGE_A != _IMAGE_B, "Test images must differ"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_binary() -> None:
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


def _parse_response_body(raw: str) -> dict:
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials() -> None:
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping MYTUBE-649 GCS key versioning "
            "test. Set FIREBASE_TEST_TOKEN to a valid Firebase ID token."
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
    _build_binary()

    _raw_uploads_bucket = os.getenv(
        "GCS_RAW_UPLOADS_BUCKET", os.getenv("RAW_BUCKET", "mytube-raw-uploads")
    )
    env = {
        "DB_HOST": db_config.host,
        "DB_PORT": str(db_config.port),
        "DB_USER": db_config.user,
        "DB_PASSWORD": db_config.password,
        "DB_NAME": db_config.dbname,
        "SSL_MODE": db_config.sslmode,
        "FIREBASE_PROJECT_ID": _FIREBASE_PROJECT_ID,
        "HLS_BUCKET": _HLS_BUCKET,
        "CDN_BASE_URL": _CDN_BASE_URL,
        "RAW_UPLOADS_BUCKET": _raw_uploads_bucket,
    }
    if _GOOGLE_APPLICATION_CREDENTIALS:
        env["GOOGLE_APPLICATION_CREDENTIALS"] = _GOOGLE_APPLICATION_CREDENTIALS

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
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_user(api_server, db_conn) -> dict:
    username = "testuser649"
    with db_conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (firebase_uid, username)
            VALUES (%s, %s)
            ON CONFLICT (firebase_uid) DO UPDATE
                SET username = EXCLUDED.username
            RETURNING id, firebase_uid, username, avatar_url
            """,
            (_FIREBASE_TEST_UID, username),
        )
        row = cur.fetchone()

    if row is None:
        pytest.fail(
            f"Could not insert or find user row for firebase_uid={_FIREBASE_TEST_UID!r}"
        )
    return {
        "id": str(row[0]),
        "firebase_uid": row[1],
        "username": row[2],
        "avatar_url": row[3],
    }


@pytest.fixture(scope="module")
def avatar_service(api_server) -> AvatarApiService:
    api_cfg = APIConfig.__new__(APIConfig)
    api_cfg.base_url = f"http://127.0.0.1:{_PORT}"
    api_cfg.health_token = ""
    return AvatarApiService(api_cfg, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def first_upload_result(avatar_service: AvatarApiService, seeded_user) -> dict:
    status, raw = avatar_service.upload_avatar(
        file_bytes=_IMAGE_A,
        mime_type="image/png",
        filename="avatar_a.png",
    )
    return {"status": status, "body": _parse_response_body(raw)}


@pytest.fixture(scope="module")
def second_upload_result(
    avatar_service: AvatarApiService,
    seeded_user,
    first_upload_result,  # ensures sequencing
) -> dict:
    status, raw = avatar_service.upload_avatar(
        file_bytes=_IMAGE_B,
        mime_type="image/png",
        filename="avatar_b.png",
    )
    return {"status": status, "body": _parse_response_body(raw)}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGCSKeyVersioningUniquePerUpload:
    """MYTUBE-649: Each avatar upload must produce a unique GCS object key."""

    def test_first_upload_returns_200(self, first_upload_result: dict) -> None:
        """First avatar upload must succeed with HTTP 200."""
        assert first_upload_result["status"] == 200, (
            f"Expected HTTP 200 for first avatar upload, "
            f"got {first_upload_result['status']}. "
            f"Response body: {first_upload_result['body']}"
        )

    def test_first_upload_returns_avatar_url(self, first_upload_result: dict) -> None:
        """First upload response must include a non-empty avatar_url."""
        body = first_upload_result["body"]
        assert "avatar_url" in body, (
            f"Expected 'avatar_url' key in first upload response, "
            f"got keys: {list(body.keys())}"
        )
        assert body["avatar_url"], (
            f"Expected a non-empty avatar_url in first upload response, "
            f"got: {body['avatar_url']!r}"
        )

    def test_second_upload_returns_200(self, second_upload_result: dict) -> None:
        """Second avatar upload must also succeed with HTTP 200."""
        assert second_upload_result["status"] == 200, (
            f"Expected HTTP 200 for second avatar upload, "
            f"got {second_upload_result['status']}. "
            f"Response body: {second_upload_result['body']}"
        )

    def test_second_upload_returns_avatar_url(self, second_upload_result: dict) -> None:
        """Second upload response must include a non-empty avatar_url."""
        body = second_upload_result["body"]
        assert "avatar_url" in body, (
            f"Expected 'avatar_url' key in second upload response, "
            f"got keys: {list(body.keys())}"
        )
        assert body["avatar_url"], (
            f"Expected a non-empty avatar_url in second upload response, "
            f"got: {body['avatar_url']!r}"
        )

    def test_consecutive_uploads_produce_unique_urls(
        self,
        first_upload_result: dict,
        second_upload_result: dict,
    ) -> None:
        """Each upload must return a DISTINCT avatar_url (unique versioned GCS key).

        The handler (fixed in MYTUBE-642) constructs the key as
        ``avatars/{userID}/{uuid}.ext``.  Because a new UUID is generated on
        every upload, the returned CDN URL must differ between uploads —
        preventing the browser/CDN from serving a stale cached image.
        """
        url_a = first_upload_result["body"].get("avatar_url", "")
        url_b = second_upload_result["body"].get("avatar_url", "")

        assert url_a != url_b, (
            "Both uploads returned the SAME avatar_url, which means the GCS key "
            "is NOT versioned.  A shared static key would cause CDN cache staleness "
            "(bug MYTUBE-642).\n"
            f"  First upload  avatar_url : {url_a!r}\n"
            f"  Second upload avatar_url : {url_b!r}\n"
            "The handler must include a unique component (UUID / timestamp) in the "
            "GCS object key so every upload produces a distinct, cache-busting URL."
        )

    def test_first_url_contains_versioning_component(
        self, first_upload_result: dict
    ) -> None:
        """The avatar_url from the first upload must embed a UUID version component.

        Expected key pattern: ``avatars/{userID}/{uuid}.ext``
        i.e. the URL path has a directory segment per user AND a UUID filename.
        """
        url = first_upload_result["body"].get("avatar_url", "")
        # Extract the object path after CDN base
        cdn_prefix = _CDN_BASE_URL.rstrip("/")
        path = url[len(cdn_prefix):] if url.startswith(cdn_prefix) else url

        assert _UUID_RE.search(path), (
            f"Expected a UUID in the avatar_url path but found none.\n"
            f"  avatar_url : {url!r}\n"
            f"  parsed path: {path!r}\n"
            "The fix (MYTUBE-642) requires the object key to be "
            "``avatars/<userID>/<uuid>.<ext>`` to bust CDN caches."
        )

    def test_second_url_contains_versioning_component(
        self, second_upload_result: dict
    ) -> None:
        """The avatar_url from the second upload must also embed a UUID."""
        url = second_upload_result["body"].get("avatar_url", "")
        cdn_prefix = _CDN_BASE_URL.rstrip("/")
        path = url[len(cdn_prefix):] if url.startswith(cdn_prefix) else url

        assert _UUID_RE.search(path), (
            f"Expected a UUID in the second avatar_url path but found none.\n"
            f"  avatar_url : {url!r}\n"
            f"  parsed path: {path!r}\n"
        )

    def test_url_pattern_uses_directory_per_user(
        self, first_upload_result: dict, seeded_user: dict
    ) -> None:
        """The avatar_url must place each upload inside a per-user directory.

        Pattern: ``avatars/{userID}/{uuid}.ext``
        This confirms the versioning structure, not a flat ``avatars/{uuid}.ext``.
        """
        url = first_upload_result["body"].get("avatar_url", "")
        user_id = seeded_user["id"]

        assert f"avatars/{user_id}/" in url, (
            f"Expected URL to contain 'avatars/{user_id}/' path segment, "
            f"got: {url!r}\n"
            "The object key must be scoped per user: "
            "``avatars/<userID>/<uuid>.<ext>``."
        )

    def test_version_uuids_differ_between_uploads(
        self,
        first_upload_result: dict,
        second_upload_result: dict,
    ) -> None:
        """The version UUID (filename segment) embedded in each URL must be distinct.

        The GCS key has the structure ``avatars/{userID}/{versionUUID}.ext``.
        The userID is shared between uploads; only the versionUUID (filename)
        must differ so each upload results in a separately addressable GCS object.
        """
        url_a = first_upload_result["body"].get("avatar_url", "")
        url_b = second_upload_result["body"].get("avatar_url", "")

        # Extract filename (last path segment, without extension) from each URL.
        # e.g.  ".../avatars/<userID>/<versionUUID>.png"  →  "<versionUUID>"
        def _extract_filename_stem(url: str) -> str:
            path = url.split("?")[0]          # strip query string
            basename = path.rsplit("/", 1)[-1] # last segment
            return basename.rsplit(".", 1)[0]  # strip extension

        stem_a = _extract_filename_stem(url_a)
        stem_b = _extract_filename_stem(url_b)

        if not stem_a or not stem_b:
            pytest.skip("Could not extract filename stem from avatar URLs.")

        assert stem_a != stem_b, (
            f"Both uploads returned avatar URLs with the SAME filename (version) component.\n"
            f"  First  filename stem : {stem_a!r}\n"
            f"  Second filename stem : {stem_b!r}\n"
            f"  First  URL           : {url_a!r}\n"
            f"  Second URL           : {url_b!r}\n"
            "Each upload must generate a new UUID filename to create a unique GCS object key."
        )
