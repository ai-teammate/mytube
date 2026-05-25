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
- AvatarApiService encapsulates all HTTP/multipart details (testing/components/services/).
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
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.components.services.avatar_api_service import AvatarApiService

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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def avatar_service() -> AvatarApiService:
    """Return an AvatarApiService instance configured from the environment."""
    return AvatarApiService(APIConfig(), token="")


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_upload_avatar_without_auth_returns_401(avatar_service: AvatarApiService) -> None:
    """POST /api/me/avatar without Authorization header must return 401."""
    status_code = avatar_service.upload_avatar_unauthenticated(_JPEG_BYTES)

    assert status_code == 401, (
        f"Expected HTTP 401 Unauthorized for unauthenticated POST /api/me/avatar, "
        f"but received HTTP {status_code}."
    )
