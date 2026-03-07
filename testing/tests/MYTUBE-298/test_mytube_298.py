"""
MYTUBE-298: OPTIONS preflight for /api/me/videos — 200 OK and CORS headers returned.

Objective
---------
Verify that the API server responds to CORS OPTIONS preflight requests for the
/api/me/videos endpoint with HTTP 200 and the required Access-Control headers,
ensuring the request is not blocked by authentication middleware.

Steps
-----
1. Send an OPTIONS request to /api/me/videos.
2. Set the Origin header to https://ai-teammate.github.io.
3. Set the Access-Control-Request-Method header to GET.
4. Set the Access-Control-Request-Headers header to authorization.
5. Do NOT include an Authorization header.

Expected Result
---------------
- HTTP 200 OK status.
- Access-Control-Allow-Origin: https://ai-teammate.github.io
- Access-Control-Allow-Methods includes GET and OPTIONS
- Access-Control-Allow-Headers includes authorization

Architecture notes
------------------
- Raw urllib.request is used to send the OPTIONS preflight request.
- APIConfig supplies the base URL via environment variables.
- No authentication is included — the endpoint must respond before auth middleware.

Environment variables
---------------------
API_BASE_URL  Base URL of the deployed API.
              Default: http://localhost:8080 (via APIConfig).
API_HOST      API host (used when API_BASE_URL is absent).
API_PORT      API port (used when API_BASE_URL is absent).
"""
from __future__ import annotations

import os
import sys
import urllib.request
import urllib.error

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig

_ORIGIN = "https://ai-teammate.github.io"
_REQUEST_METHOD = "GET"
_REQUEST_HEADERS = "authorization"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def api_config() -> APIConfig:
    return APIConfig()


@pytest.fixture(scope="module")
def preflight_response(api_config: APIConfig):
    """Send the OPTIONS preflight request and return (status_code, headers_dict).

    Returns (0, {}) if the host is unreachable.
    """
    url = api_config.base_url.rstrip("/") + "/api/me/videos"
    req = urllib.request.Request(url, method="OPTIONS")
    req.add_header("Origin", _ORIGIN)
    req.add_header("Access-Control-Request-Method", _REQUEST_METHOD)
    req.add_header("Access-Control-Request-Headers", _REQUEST_HEADERS)
    # Explicitly do NOT add Authorization header.

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, headers
    except urllib.error.HTTPError as exc:
        headers = {k.lower(): v for k, v in exc.headers.items()}
        return exc.code, headers
    except Exception as exc:
        pytest.skip(f"API host unreachable: {exc}")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCorsPreflightMeVideos:
    """MYTUBE-298: CORS OPTIONS preflight for /api/me/videos."""

    def test_status_200(self, preflight_response) -> None:
        """The OPTIONS preflight must return HTTP 200 OK."""
        status_code, _ = preflight_response
        assert status_code == 200, (
            f"Expected HTTP 200 for OPTIONS /api/me/videos, got {status_code}. "
            "The server may be blocking the preflight request with authentication middleware."
        )

    def test_allow_origin_header(self, preflight_response) -> None:
        """Response must include Access-Control-Allow-Origin matching the request Origin."""
        _, headers = preflight_response
        acao = headers.get("access-control-allow-origin", "")
        assert acao == _ORIGIN, (
            f"Expected Access-Control-Allow-Origin: {_ORIGIN!r}, got {acao!r}."
        )

    def test_allow_methods_includes_get(self, preflight_response) -> None:
        """Response must include Access-Control-Allow-Methods containing GET."""
        _, headers = preflight_response
        acam = headers.get("access-control-allow-methods", "")
        methods = [m.strip().upper() for m in acam.split(",")]
        assert "GET" in methods, (
            f"Expected Access-Control-Allow-Methods to include GET, got {acam!r}."
        )

    def test_allow_methods_includes_options(self, preflight_response) -> None:
        """Response must include Access-Control-Allow-Methods containing OPTIONS."""
        _, headers = preflight_response
        acam = headers.get("access-control-allow-methods", "")
        methods = [m.strip().upper() for m in acam.split(",")]
        assert "OPTIONS" in methods, (
            f"Expected Access-Control-Allow-Methods to include OPTIONS, got {acam!r}."
        )

    def test_allow_headers_includes_authorization(self, preflight_response) -> None:
        """Response must include Access-Control-Allow-Headers containing authorization."""
        _, headers = preflight_response
        acah = headers.get("access-control-allow-headers", "")
        allowed = [h.strip().lower() for h in acah.split(",")]
        assert "authorization" in allowed, (
            f"Expected Access-Control-Allow-Headers to include 'authorization', got {acah!r}."
        )
