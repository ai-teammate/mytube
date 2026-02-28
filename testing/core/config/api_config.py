"""API server configuration loaded from environment variables."""
import os


class APIConfig:
    base_url: str
    health_token: str

    def __init__(self):
        host = os.getenv("API_HOST", "localhost")
        port = os.getenv("API_PORT", "8080")
        self.base_url = os.getenv("API_BASE_URL", f"http://{host}:{port}")
        self.health_token = os.getenv("HEALTH_TOKEN", "")

    def health_url(self) -> str:
        return f"{self.base_url}/health"
