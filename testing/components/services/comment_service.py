"""Service object for posting and querying video comments via the API."""
from __future__ import annotations

from typing import Optional


class CommentService:
    """Provides comment operations against the MyTube REST API.

    Issues authenticated POST requests to create comments and encapsulates
    the HTTP interaction so tests never contain raw URL strings or headers.

    Usage::

        svc = CommentService(api_process_service, token="<firebase-token>")
        status, body = svc.post_comment(video_id="<uuid>", body="Great video!")
    """

    def __init__(self, api_client, token: str) -> None:
        """Initialise with an HTTP client and a Firebase Bearer token.

        Parameters
        ----------
        api_client:
            Any object that exposes ``post(path, body, headers)`` returning
            ``(status_code, response_body)`` — satisfied by both
            ``ApiProcessService`` and ``AuthService``.
        token:
            Firebase ID token used for ``Authorization: Bearer`` header.
        """
        self._client = api_client
        self._token = token

    def post_comment(self, video_id: str, body: str) -> tuple[int, str]:
        """POST /api/videos/{video_id}/comments with the given comment body.

        Returns (status_code, response_body_string).
        """
        import json

        payload = json.dumps({"body": body}).encode("utf-8")
        return self._client.post(
            f"/api/videos/{video_id}/comments",
            body=payload,
            headers={
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
            },
        )
