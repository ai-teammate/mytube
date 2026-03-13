"""HTTP API service for retrieving video recommendations."""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from testing.core.config.api_config import APIConfig


class RecommendationsService:
    """Encapsulates HTTP calls to the recommendations endpoint.

    Usage::

        svc = RecommendationsService(base_url)
        status_code, body = svc.get_recommendations(video_id)
    """

    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def get_recommendations(self, video_id: str) -> tuple[int, dict | None]:
        """GET /api/videos/{video_id}/recommendations.

        Returns (status_code, body_dict).
        Returns (0, None) when the host is unreachable.
        """
        url = f"{self._base_url}/api/videos/{video_id}/recommendations"
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:  # noqa: S310
                body = json.loads(resp.read().decode())
                return resp.status, body
        except urllib.error.HTTPError as exc:
            try:
                body = json.loads(exc.read().decode())
            except Exception:
                body = None
            return exc.code, body
        except Exception:
            return 0, None
