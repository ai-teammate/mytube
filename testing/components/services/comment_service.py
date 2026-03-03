"""Service object for interacting with the comment API endpoints."""
import json
import urllib.request
import urllib.error
from typing import Optional


class CommentService:
    """Encapsulates HTTP calls for the comment sub-resource.

    Endpoints covered:
    - POST  /api/videos/:video_id/comments  (authenticated)
    - GET   /api/videos/:video_id/comments  (public)
    - DELETE /api/comments/:comment_id      (authenticated; owner only)

    Token is injected via constructor to allow tests to supply it from
    environment variables without hardcoding values inside this class.

    Usage::

        svc = CommentService(
            base_url="http://localhost:8080",
            token=os.getenv("FIREBASE_TEST_TOKEN"),
        )
        status, body = svc.post_comment(video_id, "Hello!")
        comment_id = json.loads(body)["id"]
        status, _ = svc.delete_comment(comment_id)
        status, body = svc.list_comments(video_id)
    """

    def __init__(self, base_url: str, token: Optional[str] = None):
        self._base_url = base_url.rstrip("/")
        self._token = token

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------

    def post_comment(self, video_id: str, body: str) -> tuple[int, str]:
        """POST /api/videos/:video_id/comments with an authenticated request.

        Returns (status_code, response_body).
        """
        url = f"{self._base_url}/api/videos/{video_id}/comments"
        payload = json.dumps({"body": body}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def list_comments(self, video_id: str) -> tuple[int, str]:
        """GET /api/videos/:video_id/comments (public, no auth required).

        Returns (status_code, response_body).
        """
        url = f"{self._base_url}/api/videos/{video_id}/comments"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()

    def delete_comment(self, comment_id: str) -> tuple[int, str]:
        """DELETE /api/comments/:comment_id with an authenticated request.

        Returns (status_code, response_body).  A successful deletion returns
        HTTP 204 with an empty body.
        """
        url = f"{self._base_url}/api/comments/{comment_id}"
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = urllib.request.Request(url, method="DELETE", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()
