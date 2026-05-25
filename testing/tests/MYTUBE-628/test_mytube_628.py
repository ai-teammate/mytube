"""
MYTUBE-628: Upload avatar without authentication — API returns 401 Unauthorized.

Objective
---------
Ensure that the avatar upload endpoint requires valid authentication.

Steps
-----
1. Generate a minimal valid JPEG image in memory.
2. Send a POST request to /api/me/avatar with the image as multipart/form-data,
   but WITHOUT an Authorization header.
3. Assert the response status code is 401.

Expected Result
---------------
The API returns HTTP 401 Unauthorized.

Architecture
------------
- Pure API test using Python stdlib (urllib / http.client) — no auth token needed.
- APIConfig: centralised base URL from environment variable API_BASE_URL.

Environment Variables
---------------------
API_BASE_URL    Base URL of the deployed API.
                Default: https://mytube-api-80693608388.us-central1.run.app

Run from repo root:
    pytest testing/tests/MYTUBE-628/test_mytube_628.py -v
"""
from __future__ import annotations

import base64
import io
import os
import sys
import urllib.error
import urllib.request
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig

# ---------------------------------------------------------------------------
# Minimal 1×1 white-pixel JPEG (standard test image, <1 KB)
# ---------------------------------------------------------------------------

_MINIMAL_JPEG_B64 = (
    "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
    "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAARC"
    "AABAAEDASIA2gABAREA/8QAFgABAQEAAAAAAAAAAAAAAAAABgUE/8QAIxAAAQMEAgMB"
    "AAAAAAAAAAAAAQIDBAAFESExQVFh/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAA"
    "AAAAAAAAAAAAAAAAAP/aAAwDAQACEQMRAD8Amk2pa3pVoiu3CqNOmTUoSVJDSwFKA9yB"
    "vXisWtd2vMiTHt8B2Q3GdLTi0DYSobBH3rF0/8QAHRABAAICAwEBAAAAAAAAAAAAAQID"
    "BAAFITIUhP/aAAgBAQABPxCk2e63S4SY8aI484y4UOJQNkKHIIPkEf0qw2O0W2wxVxr"
    "XEbisuOFxSEb2onk1//2Q=="
)

_JPEG_BYTES = base64.b64decode(_MINIMAL_JPEG_B64)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_multipart(field_name: str, filename: str, data: bytes, content_type: str) -> tuple[bytes, str]:
    """Return (body_bytes, boundary) for a single-file multipart/form-data payload."""
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field_name}"; filename="{filename}"\r\n'
        f"Content-Type: {content_type}\r\n"
        f"\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    return body, boundary


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_base_url() -> str:
    return APIConfig().base_url


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_upload_avatar_without_auth_returns_401(api_base_url: str) -> None:
    """POST /api/me/avatar without Authorization header must return 401."""
    url = f"{api_base_url}/api/me/avatar"

    body, boundary = _build_multipart(
        field_name="avatar",
        filename="test_avatar.jpg",
        data=_JPEG_BYTES,
        content_type="image/jpeg",
    )

    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    # No Authorization header is added — this is the core of the test.

    status_code: int
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            status_code = resp.status
    except urllib.error.HTTPError as exc:
        status_code = exc.code

    assert status_code == 401, (
        f"Expected HTTP 401 Unauthorized for unauthenticated POST /api/me/avatar, "
        f"but received HTTP {status_code}."
    )
