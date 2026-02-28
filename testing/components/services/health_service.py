"""Service object for interacting with the /health API endpoint."""
import urllib.request
import urllib.error
import json
from dataclasses import dataclass, field
from typing import Optional

from testing.core.config.api_config import APIConfig


@dataclass
class HealthResponse:
    status_code: int
    status: Optional[str]
    db: Optional[str]
    content_type: str = field(default="")


class HealthService:
    """Provides methods to interact with the GET /health endpoint."""

    def __init__(self, config: APIConfig):
        self._config = config

    def get_health(self) -> HealthResponse:
        """Perform GET /health and return a HealthResponse."""
        url = self._config.health_url()
        req = urllib.request.Request(url, method="GET")
        if self._config.health_token:
            req.add_header("X-Health-Token", self._config.health_token)

        try:
            with urllib.request.urlopen(req) as resp:
                status_code = resp.status
                content_type = resp.headers.get("Content-Type", "")
                body = json.loads(resp.read().decode())
                return HealthResponse(
                    status_code=status_code,
                    status=body.get("status"),
                    db=body.get("db"),
                    content_type=content_type,
                )
        except urllib.error.HTTPError as e:
            body_text = e.read().decode()
            content_type = e.headers.get("Content-Type", "")
            try:
                body = json.loads(body_text)
            except json.JSONDecodeError:
                body = {}
            return HealthResponse(
                status_code=e.code,
                status=body.get("status"),
                db=body.get("db"),
                content_type=content_type,
            )
