"""Service object for avatar upload HTTP operations against the MyTube REST API."""
from __future__ import annotations

import http.client
import io
import socket
import urllib.parse
import uuid
from typing import Optional

from testing.core.config.api_config import APIConfig


class AvatarApiService:
    """Provides helpers for POST /api/me/avatar with multipart/form-data payloads.

    Requires a valid Firebase Bearer token; returns (status_code, body) pairs.

    Usage::

        svc = AvatarApiService(api_config, token="firebase-id-token")
        status, body = svc.upload_avatar(file_bytes, mime_type="image/jpeg")
    """

    def __init__(self, api_config: APIConfig, token: str) -> None:
        self._base_url = api_config.base_url.rstrip("/")
        self._token = token

    def upload_avatar_unauthenticated(
        self,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        filename: str = "test_avatar.jpg",
        timeout: int = 15,
    ) -> int:
        """POST *image_bytes* to /api/me/avatar WITHOUT an Authorization header.

        Returns the HTTP status code.  This is the test-facing method for
        MYTUBE-628: verifying that the endpoint rejects unauthenticated callers
        with HTTP 401.
        """
        import urllib.error
        import urllib.request as _ureq

        boundary = uuid.uuid4().hex
        body = _build_multipart_body(boundary, image_bytes, mime_type, filename)
        url = f"{self._base_url}/api/me/avatar"
        req = _ureq.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        # No Authorization header — this is deliberate.
        try:
            with _ureq.urlopen(req, timeout=timeout) as resp:
                return resp.status
        except urllib.error.HTTPError as exc:
            return exc.code

    def upload_avatar(
        self,
        file_bytes: bytes,
        mime_type: str = "image/jpeg",
        filename: str = "avatar.jpg",
        timeout: int = 60,
    ) -> tuple[int, str]:
        """POST *file_bytes* as multipart/form-data to /api/me/avatar.

        Uses http.client directly so we can handle early server responses
        (e.g. HTTP 413) that arrive while the body is still being uploaded.
        The server may reset the connection after sending the 413, which is
        normal behaviour for ``http.MaxBytesReader``; this method captures
        the response status before the reset.

        Returns ``(status_code, response_body_as_str)``.
        """
        parsed = urllib.parse.urlparse(self._base_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        is_https = parsed.scheme == "https"

        boundary = uuid.uuid4().hex
        body = _build_multipart_body(boundary, file_bytes, mime_type, filename)

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
            "Connection": "close",
        }

        if is_https:
            conn = http.client.HTTPSConnection(host, port, timeout=timeout)
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)

        try:
            # putrequest + putheader + endheaders + send keeps the request
            # open so we can read an early 413 before the full body is sent.
            conn.connect()
            conn.putrequest("POST", "/api/me/avatar")
            for key, val in headers.items():
                conn.putheader(key, val)
            conn.endheaders()

            # Stream body in chunks; if the server resets the connection while
            # we are sending (normal for MaxBytesReader), catch the error and
            # still try to read whatever response was already buffered.
            chunk_size = 65536  # 64 KB
            offset = 0
            while offset < len(body):
                chunk = body[offset : offset + chunk_size]
                try:
                    conn.sock.sendall(chunk)
                except (ConnectionResetError, BrokenPipeError, OSError):
                    # Server reset the connection — response may already be in
                    # the receive buffer; fall through to getresponse().
                    break
                offset += chunk_size

            try:
                response = conn.getresponse()
                status = response.status
                response_body = response.read().decode("utf-8", errors="replace")
                return status, response_body
            except (http.client.RemoteDisconnected, ConnectionResetError, OSError):
                # If we still cannot read, the response arrived and connection
                # was closed.  Return 0 to signal a connection-level error.
                return 0, "connection reset before response was received"
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_multipart_body(
    boundary: str,
    file_bytes: bytes,
    mime_type: str,
    filename: str,
) -> bytes:
    """Build a minimal multipart/form-data body with a single 'avatar' file part."""
    b = boundary.encode()
    buf = io.BytesIO()
    buf.write(b"--" + b + b"\r\n")
    buf.write(
        f'Content-Disposition: form-data; name="avatar"; filename="{filename}"\r\n'.encode()
    )
    buf.write(f"Content-Type: {mime_type}\r\n".encode())
    buf.write(b"\r\n")
    buf.write(file_bytes)
    buf.write(b"\r\n--" + b + b"--\r\n")
    return buf.getvalue()
