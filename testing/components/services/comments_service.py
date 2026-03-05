"""Service object for posting and managing comments via the MyTube REST API."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


@dataclass
class CommentResponse:
    """Structured result of a POST /api/videos/:id/comments call."""

    status_code: int
    raw_body: str

    @property
    def json(self) -> Optional[dict]:
        """Return parsed JSON body, or None if body is not valid JSON."""
        try:
            return json.loads(self.raw_body)
        except (json.JSONDecodeError, ValueError):
            return None

    @property
    def error_message(self) -> Optional[str]:
        """Return the error message from the response body, if present."""
        data = self.json
        if not data:
            return None
        return data.get("error") or data.get("message")


class CommentsService:
    """Provides HTTP operations for the comments endpoints.

    Encapsulates POST /api/videos/:video_id/comments, GET comment list,
    and DELETE /api/comments/:comment_id with Bearer token auth.

    Usage::

        svc = CommentsService(
            base_url="https://mytube-api-80693608388.us-central1.run.app",
            token=os.getenv("FIREBASE_TEST_TOKEN"),
        )
        response = svc.post_comment(video_id="...", body="Hello world")
        assert response.status_code == 201
    """

    def __init__(self, base_url: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token

    def post_comment(self, video_id: str, body: str) -> CommentResponse:
        """POST a comment to /api/videos/:video_id/comments.

        Args:
            video_id: UUID of the target video.
            body: Comment text content.

        Returns:
            CommentResponse with status_code and raw_body.
        """
        url = f"{self._base_url}/api/videos/{video_id}/comments"
        payload = json.dumps({"body": body}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        req = urllib.request.Request(url, data=payload, method="POST", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return CommentResponse(
                    status_code=resp.status,
                    raw_body=resp.read().decode(),
                )
        except urllib.error.HTTPError as exc:
            return CommentResponse(
                status_code=exc.code,
                raw_body=exc.read().decode(),
            )

    def list_comments(self, video_id: str) -> CommentResponse:
        """GET /api/videos/:video_id/comments (public, no auth required).

        Returns:
            CommentResponse with status_code and raw_body.
        """
        url = f"{self._base_url}/api/videos/{video_id}/comments"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return CommentResponse(
                    status_code=resp.status,
                    raw_body=resp.read().decode(),
                )
        except urllib.error.HTTPError as exc:
            return CommentResponse(
                status_code=exc.code,
                raw_body=exc.read().decode(),
            )

    def delete_comment(self, comment_id: str) -> CommentResponse:
        """DELETE /api/comments/:comment_id (authenticated, owner only).

        Returns:
            CommentResponse with status_code and raw_body.
            A successful deletion returns HTTP 204 with an empty body.
        """
        url = f"{self._base_url}/api/comments/{comment_id}"
        headers = {
            "Authorization": f"Bearer {self._token}",
        }
        req = urllib.request.Request(url, method="DELETE", headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return CommentResponse(
                    status_code=resp.status,
                    raw_body=resp.read().decode(),
                )
        except urllib.error.HTTPError as exc:
            return CommentResponse(
                status_code=exc.code,
                raw_body=exc.read().decode(),
            )
