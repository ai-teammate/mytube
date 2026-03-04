"""Service objects for posting/querying video comments via the API and database."""
from __future__ import annotations

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Optional


class CommentService:
    """Provides HTTP comment operations against the MyTube REST API.

    Supports two construction modes:

    1. ``api_client`` mode — pass an ``ApiProcessService``-like object that
       exposes ``post(path, body, headers)`` and ``get(path, headers)`` returning
       ``(status_code, response_body_str)``.  Used by integration tests that spin
       up a local API subprocess::

           svc = CommentService(api_client=api_server, token="<firebase-token>")
           status, body = svc.post_comment(video_id="<uuid>", body="Great video!")

    2. ``base_url`` mode — pass the API root URL as a string.  Used by tests
       that call the deployed (or separately-started) API::

           svc = CommentService(base_url="https://…", token="<firebase-token>")
           status, body = svc.post_comment(video_id="<uuid>", body="Hello")
    """

    def __init__(
        self,
        api_client=None,
        token: str = "",
        base_url: str = "",
    ) -> None:
        self._api_client = api_client
        self._token = token
        self._base_url = base_url.rstrip("/") if base_url else ""

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def post_comment(self, video_id: str, body: str) -> tuple[int, str]:
        """POST /api/videos/{video_id}/comments with the given comment body.

        Returns (status_code, response_body_string).
        """
        payload = json.dumps({"body": body}).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        path = f"/api/videos/{video_id}/comments"
        if self._api_client is not None:
            return self._api_client.post(path, body=payload, headers=headers)
        return self._urlopen("POST", self._base_url + path, data=payload, headers=headers)

    def delete_comment(self, comment_id: str) -> tuple[int, str]:
        """DELETE /api/comments/{comment_id} with Bearer auth.

        Returns (status_code, response_body_string).
        Only available in ``base_url`` mode.
        """
        if self._api_client is not None:
            raise NotImplementedError(
                "delete_comment is not supported in api_client mode; use base_url mode."
            )
        headers = {"Authorization": f"Bearer {self._token}"}
        url = f"{self._base_url}/api/comments/{comment_id}"
        return self._urlopen("DELETE", url, headers=headers)

    def list_comments(self, video_id: str) -> tuple[int, str]:
        """GET /api/videos/{video_id}/comments.

        Returns (status_code, response_body_string).
        """
        path = f"/api/videos/{video_id}/comments"
        headers: dict = {}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        if self._api_client is not None:
            return self._api_client.get(path, headers=headers)
        return self._urlopen("GET", self._base_url + path, headers=headers)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _urlopen(
        method: str,
        url: str,
        data: Optional[bytes] = None,
        headers: Optional[dict] = None,
    ) -> tuple[int, str]:
        req = urllib.request.Request(
            url, data=data, method=method, headers=headers or {}
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode()


class CommentDBService:
    """Provides comment row operations against a live PostgreSQL database.

    Used by integration tests that seed comment data directly (bypassing HTTP).

    Usage::

        svc = CommentDBService(conn)
        comment_id = svc.insert_comment(video_id, author_id, "Hello")
    """

    def __init__(self, conn) -> None:
        self._conn = conn

    def insert_comment(
        self,
        video_id: str,
        author_id: str,
        body: str,
        created_at: Optional[datetime] = None,
    ) -> str:
        """Insert a comment row and return its id as a string."""
        with self._conn.cursor() as cur:
            if created_at is not None:
                cur.execute(
                    "INSERT INTO comments (video_id, author_id, body, created_at) "
                    "VALUES (%s, %s, %s, %s) RETURNING id",
                    (video_id, author_id, body, created_at),
                )
            else:
                cur.execute(
                    "INSERT INTO comments (video_id, author_id, body) "
                    "VALUES (%s, %s, %s) RETURNING id",
                    (video_id, author_id, body),
                )
            return str(cur.fetchone()[0])

    def insert_bulk_comments(
        self,
        video_id: str,
        author_id: str,
        count: int,
        base_time: datetime,
    ) -> list[str]:
        """Insert *count* comments with 1-second-apart timestamps starting at *base_time*.

        Returns the list of inserted comment ids in insertion order
        (index 0 = oldest, index count-1 = newest).
        """
        ids = []
        for i in range(count):
            ts = base_time + timedelta(seconds=i)
            comment_id = self.insert_comment(video_id, author_id, f"Comment number {i}", ts)
            ids.append(comment_id)
        return ids
