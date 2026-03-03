"""Service object for interacting with the comment API endpoints."""
from __future__ import annotations

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

    Accepts either a ``base_url`` (makes direct HTTP requests) or an
    ``api_client`` object that exposes ``post(path, body, headers)``
    (e.g. ``ApiProcessService``).  When ``api_client`` is supplied it is used
    for POST requests; ``list_comments`` and ``delete_comment`` always use
    direct urllib calls via ``base_url``.

    Token is injected via constructor to allow tests to supply it from
    environment variables without hardcoding values inside this class.

    Usage (deployed API)::

        svc = CommentService(
            base_url="https://mytube-api-80693608388.us-central1.run.app",
            token=os.getenv("FIREBASE_TEST_TOKEN"),
        )
        status, body = svc.post_comment(video_id, "Hello!")
        comment_id = json.loads(body)["id"]
        status, _ = svc.delete_comment(comment_id)
        status, body = svc.list_comments(video_id)

    Usage (local test server via ApiProcessService)::

        svc = CommentService(api_client=api_server, token=firebase_token)
        status, body = svc.post_comment(video_id=seeded_video, body="Great video!")
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        api_client=None,
    ) -> None:
        if base_url is None and api_client is None:
            raise ValueError("Either base_url or api_client must be provided.")
        self._base_url = base_url.rstrip("/") if base_url else None
        self._token = token
        self._client = api_client

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------

    def post_comment(self, video_id: str, body: str) -> tuple[int, str]:
        """POST /api/videos/:video_id/comments with an authenticated request.

        Returns (status_code, response_body).
        """
        path = f"/api/videos/{video_id}/comments"
        payload = json.dumps({"body": body}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"

        if self._client is not None:
            return self._client.post(path, body=payload, headers=headers)

        url = f"{self._base_url}{path}"
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
        base = self._base_url or ""
        url = f"{base}/api/videos/{video_id}/comments"
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
        base = self._base_url or ""
        url = f"{base}/api/comments/{comment_id}"
        headers = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = urllib.request.Request(url, method="DELETE", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()
