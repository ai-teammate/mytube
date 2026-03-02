"""Web frontend configuration loaded from environment variables."""
import os


class WebConfig:
    """Configuration for web UI tests.

    Reads the deployed frontend URL from the APP_URL environment variable.
    Falls back to the local development server URL (http://localhost:3000)
    for local test execution, or the GitHub Pages URL for CI against the
    deployed app.
    """

    base_url: str

    def __init__(self):
        self.base_url = os.getenv(
            "APP_URL",
            "http://localhost:3000",
        ).rstrip("/")

    def register_url(self) -> str:
        return f"{self.base_url}/register/"

    def home_url(self) -> str:
        return f"{self.base_url}/"
