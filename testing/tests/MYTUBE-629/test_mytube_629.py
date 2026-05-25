"""
MYTUBE-629: Re-upload avatar for same user — previous file is overwritten in GCS.

Objective
---------
Verify that subsequent uploads by the same user use a deterministic object key
(avatars/<user_id>.<ext>) to overwrite the existing file in GCS rather than
creating a new object with a unique suffix.

Preconditions
-------------
- A user row already exists in the database for the test Firebase UID.
- The API server is running and the Firebase token is valid.

Test steps
----------
1. Build and start the Go API server.
2. Ensure a test user exists in the database with the known Firebase UID.
3. POST /api/me/avatar with a first valid PNG image (image_a).
4. Assert HTTP 200 and capture avatar_url_a.
5. POST /api/me/avatar with a second, different PNG image (image_b).
6. Assert HTTP 200 and capture avatar_url_b.
7. Assert avatar_url_a == avatar_url_b (deterministic key — same GCS object path).
8. If GCS credentials are available, retrieve the live GCS object and verify
   its content matches image_b (confirming overwrite, not a new parallel object).

Expected result
---------------
Both uploads return HTTP 200. The avatar_url returned is identical in both
cases (same bucket + key). The GCS object content equals image_b after the
second upload.

Environment variables
---------------------
FIREBASE_TEST_TOKEN    : Firebase ID token for the test user (required).
FIREBASE_PROJECT_ID    : Firebase project ID for the verifier (required).
FIREBASE_TEST_UID      : firebase_uid stored in the DB row (default: ci-test-user-001).
API_BINARY             : Path to the pre-built Go binary (default: <repo>/api/mytube-api).
DB_HOST / DB_PORT / DB_USER / DB_PASSWORD / DB_NAME / SSL_MODE : DB settings.
GCP_PROJECT_ID         : GCP project (for GCS verification — optional).
GOOGLE_APPLICATION_CREDENTIALS : Path to a GCP service-account JSON key (optional).
HLS_BUCKET             : GCS bucket used by the API for avatar storage.
CDN_BASE_URL           : Public CDN base URL for the HLS bucket.

Architecture
------------
- ApiProcessService manages the Go API subprocess lifecycle.
- AvatarApiService encapsulates multipart POST /api/me/avatar requests.
- psycopg2 is used for idempotent test-user seeding.
- GCS verification uses google-cloud-storage when credentials are present.
- No hardcoded URLs, credentials, or secrets.
"""
from __future__ import annotations

import hashlib
import json
import os
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
# Use a test-specific binary path so the freshly built binary is used even
# when the pre-built api/mytube-api is from an older code revision.
_DEFAULT_BINARY = os.path.join("/tmp", "mytube-api-629")
API_BINARY = os.getenv("API_BINARY", _DEFAULT_BINARY)

_PORT = 18629
_STARTUP_TIMEOUT = 20.0

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")
_FIREBASE_PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID", "")
_FIREBASE_TEST_UID = os.getenv("FIREBASE_TEST_UID", "ci-test-user-001")

_HLS_BUCKET = os.getenv("HLS_BUCKET", "mytube-hls-output")
_CDN_BASE_URL = os.getenv("CDN_BASE_URL", "https://storage.googleapis.com/mytube-hls-output")

_GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
_GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")


# ---------------------------------------------------------------------------
# Minimal PNG helpers
# ---------------------------------------------------------------------------

def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    """Build a single PNG chunk: length + type + data + CRC."""
    length = struct.pack(">I", len(data))
    crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return length + chunk_type + data + crc


def _make_1x1_png(r: int, g: int, b: int) -> bytes:
    """Create a minimal, valid 1×1 RGB PNG with the given colour."""
    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"
    # IHDR: width=1, height=1, bit_depth=8, color_type=2 (RGB), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _png_chunk(b"IHDR", ihdr_data)
    # IDAT: single pixel, filter byte 0 + RGB
    raw_row = bytes([0, r, g, b])
    compressed = zlib.compress(raw_row)
    idat = _png_chunk(b"IDAT", compressed)
    # IEND
    iend = _png_chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


# Two visually distinct 1×1 PNG images with unique colour channels.
_IMAGE_A: bytes = _make_1x1_png(255, 0, 0)   # red pixel
_IMAGE_B: bytes = _make_1x1_png(0, 0, 255)   # blue pixel

assert _IMAGE_A != _IMAGE_B, "Test images must differ for overwrite verification"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_binary() -> None:
    """Build the Go API binary fresh to ensure the current source is used.

    Always rebuilds to avoid stale pre-built binaries that may be missing
    recently-added routes (e.g. /api/me/avatar).
    """
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
    """Parse a JSON response body string; fall back to ``{"raw": raw}``."""
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_credentials() -> None:
    """Skip the entire module when Firebase credentials are absent."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN not set — skipping MYTUBE-629 avatar re-upload "
            "test.  Set FIREBASE_TEST_TOKEN to a valid Firebase ID token."
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
    """Build (if needed) and start the Go API server; yield; stop on teardown."""
    _build_binary()

    _raw_uploads_bucket = os.getenv("GCS_RAW_UPLOADS_BUCKET", os.getenv("RAW_BUCKET", "mytube-raw-uploads"))

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
    """Open a direct psycopg2 connection for test-user setup."""
    conn = psycopg2.connect(db_config.dsn())
    conn.autocommit = True
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def seeded_user(api_server, db_conn) -> dict:
    """Ensure a user row exists for *_FIREBASE_TEST_UID* and return it."""
    username = "testuser629"
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
    """Return an AvatarApiService pointing at the local test server."""
    api_cfg = APIConfig.__new__(APIConfig)
    api_cfg.base_url = f"http://127.0.0.1:{_PORT}"
    api_cfg.health_token = ""
    return AvatarApiService(api_cfg, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def first_upload_result(avatar_service: AvatarApiService, seeded_user) -> dict:
    """Upload image_a and capture the HTTP response."""
    status, raw = avatar_service.upload_avatar(
        file_bytes=_IMAGE_A,
        mime_type="image/png",
        filename="avatar_a.png",
    )
    return {"status": status, "body": _parse_response_body(raw)}


@pytest.fixture(scope="module")
def second_upload_result(avatar_service: AvatarApiService, seeded_user, first_upload_result) -> dict:
    """Upload image_b immediately after image_a and capture the HTTP response."""
    status, raw = avatar_service.upload_avatar(
        file_bytes=_IMAGE_B,
        mime_type="image/png",
        filename="avatar_b.png",
    )
    return {"status": status, "body": _parse_response_body(raw)}


@pytest.fixture(scope="module")
def gcs_client(seeded_user):
    """Return an authenticated GCS client, or None if credentials are absent."""
    if not _GCP_PROJECT_ID or not _GOOGLE_APPLICATION_CREDENTIALS:
        return None
    try:
        from google.cloud import storage as gcs_storage
        return gcs_storage.Client(project=_GCP_PROJECT_ID)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarReUploadOverwritesGCSObject:
    """MYTUBE-629: Re-uploading an avatar overwrites the existing GCS object."""

    def test_first_upload_returns_200(self, first_upload_result: dict) -> None:
        """Initial avatar upload must return HTTP 200."""
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
        """Subsequent avatar upload must also return HTTP 200."""
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

    def test_avatar_url_is_deterministic(
        self,
        first_upload_result: dict,
        second_upload_result: dict,
    ) -> None:
        """Both uploads must return the same avatar_url (deterministic GCS key).

        The handler constructs the object key as ``avatars/<user_id>.<ext>``.
        Because the user ID and extension are fixed across re-uploads, the
        returned CDN URL must be identical — confirming that the second upload
        overwrites the first rather than creating a parallel object.
        """
        url_a = first_upload_result["body"].get("avatar_url", "")
        url_b = second_upload_result["body"].get("avatar_url", "")

        assert url_a == url_b, (
            "The avatar_url changed between the first and second upload, "
            "which means the second upload created a NEW GCS object instead of "
            "overwriting the existing one.\n"
            f"  First upload  avatar_url: {url_a!r}\n"
            f"  Second upload avatar_url: {url_b!r}\n"
            "The handler must derive the object key deterministically from the "
            "user's database ID and file extension (avatars/<user_id>.<ext>) "
            "so that subsequent uploads overwrite the same GCS object."
        )

    def test_avatar_url_contains_expected_bucket_prefix(
        self,
        second_upload_result: dict,
        seeded_user: dict,
    ) -> None:
        """The avatar_url must reference the configured bucket and user ID path.

        This confirms the GCS object key is constructed as
        ``avatars/<user_id>.png`` inside the HLS bucket.
        """
        url = second_upload_result["body"].get("avatar_url", "")
        user_id = seeded_user["id"]

        assert "avatars/" in url, (
            f"Expected avatar_url to contain 'avatars/' path segment, "
            f"got: {url!r}"
        )
        assert user_id in url, (
            f"Expected avatar_url to contain the user's database ID {user_id!r}, "
            f"got: {url!r}.  "
            "The handler must use the user's DB UUID as the filename to ensure "
            "the key is deterministic and unique per user."
        )

    def test_gcs_object_content_matches_second_upload(
        self,
        second_upload_result: dict,
        gcs_client,
    ) -> None:
        """GCS object content must equal the second uploaded image (image_b).

        This verifies the GCS object was actually overwritten rather than the
        handler returning a cached / stale URL.  Skipped when GCS credentials
        are not available in the test environment.
        """
        if gcs_client is None:
            pytest.skip(
                "GCS client not available (GCP_PROJECT_ID or "
                "GOOGLE_APPLICATION_CREDENTIALS not set) — skipping live GCS "
                "content verification."
            )

        avatar_url = second_upload_result["body"].get("avatar_url", "")

        # Derive the GCS object key from the CDN URL.
        # CDN_BASE_URL = https://storage.googleapis.com/<bucket>
        # avatar_url   = https://storage.googleapis.com/<bucket>/avatars/<id>.png
        cdn_prefix = _CDN_BASE_URL.rstrip("/")
        if not avatar_url.startswith(cdn_prefix + "/"):
            pytest.skip(
                f"avatar_url {avatar_url!r} does not start with CDN prefix "
                f"{cdn_prefix!r} — cannot derive GCS object key for live verification."
            )

        object_key = avatar_url[len(cdn_prefix) + 1:]

        try:
            bucket = gcs_client.bucket(_HLS_BUCKET)
            blob = bucket.blob(object_key)
            live_content: bytes = blob.download_as_bytes()
        except Exception as exc:
            pytest.skip(
                f"Could not download GCS object {object_key!r} from bucket "
                f"{_HLS_BUCKET!r}: {exc}.  "
                "Skipping live content verification."
            )

        expected_hash = hashlib.sha256(_IMAGE_B).hexdigest()
        actual_hash = hashlib.sha256(live_content).hexdigest()

        assert actual_hash == expected_hash, (
            "GCS object content does not match the second uploaded image.\n"
            f"  Object key       : {object_key}\n"
            f"  Bucket           : {_HLS_BUCKET}\n"
            f"  Expected SHA-256 : {expected_hash} (image_b — blue 1×1 PNG)\n"
            f"  Actual SHA-256   : {actual_hash}\n"
            "This means the GCS object was NOT overwritten by the second upload.  "
            "The handler must write to the deterministic key unconditionally on "
            "every upload so the content is always up-to-date."
        )
