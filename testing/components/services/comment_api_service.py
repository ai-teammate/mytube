"""Service object for the /api/comments endpoints."""
import urllib.request
import urllib.error
from typing import Optional


class CommentApiService:
    """Provides helpers for interacting with the comments API.

    All HTTP details (headers, error handling) are encapsulated here.
    Tests receive only high-level action methods and typed return values.

    Usage::

        svc = CommentApiService(base_url="http://localhost:8080", token=token)
        status, body = svc.delete_comment(comment_id)
    """

    def __init__(self, base_url: str, token: Optional[str] = None):
        self._base_url = base_url.rstrip("/")
        self._token = token

    def delete_comment(self, comment_id: str) -> tuple[int, str]:
        """Send DELETE /api/comments/{comment_id} with Bearer auth.

        Returns (status_code, response_body).
        """
        url = f"{self._base_url}/api/comments/{comment_id}"
        headers: dict = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = urllib.request.Request(url, method="DELETE", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()
