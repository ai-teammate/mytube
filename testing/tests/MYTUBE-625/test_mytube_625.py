"""
MYTUBE-625: Upload valid PNG avatar — image stored in GCS and profile updated.

Objective
---------
Verify that the API successfully processes PNG file uploads for user avatars.

Preconditions
-------------
User is authenticated.

Steps
-----
1. Send a POST request to `/api/me/avatar` using `multipart/form-data`.
2. Attach a file with `image/png` MIME type and size under 5 MB.

Expected Result
---------------
The API returns HTTP 200 OK. The JSON response contains the updated `avatar_url`,
and the file is correctly uploaded to GCS.

Architecture notes
------------------
- AuthService wraps authenticated HTTP calls including multipart upload.
- FIREBASE_TEST_TOKEN is used for authentication (pre-fetched CI token).
- APIConfig supplies the base URL via environment variables.
- A minimal valid 1×1 PNG image is generated in-memory (no external files needed).
- The test verifies the HTTP 200 status code and `avatar_url` presence in the response.

Environment variables
---------------------
FIREBASE_TEST_TOKEN  Valid Firebase ID token for the CI test user (required).
API_BASE_URL         Base URL of the deployed API (default: http://localhost:8080).
"""
from __future__ import annotations

import json
import os
import struct
import sys
import zlib

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.components.services.auth_service import AuthService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIREBASE_TOKEN = os.getenv("FIREBASE_TEST_TOKEN", "")

_AVATAR_ENDPOINT = "/api/me/avatar"
_AVATAR_FIELD = "avatar"
_AVATAR_FILENAME = "test_avatar.png"
_AVATAR_MIME = "image/png"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_minimal_png() -> bytes:
    """Return the bytes of a minimal valid 1×1 pixel red PNG image.

    Constructed manually so the test has zero external file dependencies.
    The resulting bytes pass Go's http.DetectContentType sniff test.
    """

    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return length + chunk_type + data + crc

    # PNG signature
    sig = b"\x89PNG\r\n\x1a\n"

    # IHDR: 1x1 px, 8-bit, RGB colour (type 2), no interlace
    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    ihdr = _chunk(b"IHDR", ihdr_data)

    # IDAT: one scanline filter byte (0) + RGB pixel (255, 0, 0) — red
    raw_scanline = b"\x00\xff\x00\x00"
    idat = _chunk(b"IDAT", zlib.compress(raw_scanline))

    # IEND
    iend = _chunk(b"IEND", b"")

    return sig + ihdr + idat + iend


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def require_firebase_token() -> None:
    """Skip this module when FIREBASE_TEST_TOKEN is not set."""
    if not _FIREBASE_TOKEN:
        pytest.skip(
            "FIREBASE_TEST_TOKEN is not set — skipping MYTUBE-625 integration test. "
            "Provide a valid Firebase ID token to run this test."
        )


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def auth_service(api_config: APIConfig) -> AuthService:
    return AuthService(base_url=api_config.base_url, token=_FIREBASE_TOKEN)


@pytest.fixture(scope="module")
def avatar_png() -> bytes:
    """Return in-memory bytes of a minimal valid PNG file."""
    return _make_minimal_png()


@pytest.fixture(scope="module")
def upload_response(auth_service: AuthService, avatar_png: bytes) -> tuple[int, str]:
    """Send POST /api/me/avatar with a valid PNG and return (status, body)."""
    status, body = auth_service.post_multipart(
        path=_AVATAR_ENDPOINT,
        fields={},
        files={
            _AVATAR_FIELD: (_AVATAR_FILENAME, avatar_png, _AVATAR_MIME),
        },
    )
    return status, body


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAvatarUploadPNG:
    """MYTUBE-625: POST /api/me/avatar with valid PNG — 200 OK and avatar_url returned."""

    def test_status_200(self, upload_response: tuple[int, str]) -> None:
        """Step 1+2: The API must return HTTP 200 OK for a valid PNG upload."""
        status, body = upload_response
        assert status == 200, (
            f"Expected HTTP 200 OK for POST /api/me/avatar with a valid PNG file, "
            f"got HTTP {status}. Response body: {body!r}"
        )

    def test_response_contains_avatar_url(self, upload_response: tuple[int, str]) -> None:
        """The JSON response must include the `avatar_url` key with a non-empty value."""
        status, body = upload_response
        try:
            data = json.loads(body)
        except json.JSONDecodeError as exc:
            pytest.fail(
                f"Response body is not valid JSON. Status: {status}. "
                f"Body: {body!r}. Error: {exc}"
            )

        assert "avatar_url" in data, (
            f"Expected JSON key 'avatar_url' in the response, but got: {data!r}"
        )

        avatar_url: str = data["avatar_url"]
        assert avatar_url, (
            f"Expected 'avatar_url' to be a non-empty string, got: {avatar_url!r}"
        )

    def test_avatar_url_is_gcs_path(self, upload_response: tuple[int, str]) -> None:
        """The returned avatar_url must be an absolute HTTPS URL pointing to GCS storage."""
        _, body = upload_response
        data = json.loads(body)
        avatar_url: str = data.get("avatar_url", "")

        assert avatar_url.startswith("https://"), (
            f"Expected avatar_url to be an HTTPS URL, got: {avatar_url!r}"
        )
        assert "avatars/" in avatar_url, (
            f"Expected avatar_url to contain 'avatars/' GCS path prefix, "
            f"got: {avatar_url!r}"
        )
        assert avatar_url.endswith(".png"), (
            f"Expected avatar_url to end with '.png' for a PNG upload, "
            f"got: {avatar_url!r}"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
