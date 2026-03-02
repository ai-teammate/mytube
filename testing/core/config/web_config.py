"""Web application configuration loaded from environment variables."""
import os


class WebConfig:
    """Configuration for web UI tests.

    Environment variables
    ---------------------
    WEB_BASE_URL        Base URL of the deployed web application.
                        Default: https://ai-teammate.github.io/mytube
    FIREBASE_TEST_EMAIL Email address of the test Firebase user.
    FIREBASE_TEST_PASSWORD
                        Password for the test Firebase user.
    PLAYWRIGHT_HEADLESS Run browser in headless mode (default: true).
    PLAYWRIGHT_SLOW_MO  Slow-motion delay in ms for debugging (default: 0).
    """

    def __init__(self) -> None:
        self.base_url: str = os.getenv(
            "WEB_BASE_URL", "https://ai-teammate.github.io/mytube"
        ).rstrip("/")
        self.test_email: str = os.getenv("FIREBASE_TEST_EMAIL", "")
        self.test_password: str = os.getenv("FIREBASE_TEST_PASSWORD", "")
        self.headless: bool = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        self.slow_mo: int = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))

    def login_url(self) -> str:
        return f"{self.base_url}/login/"

    def home_url(self) -> str:
        return self.base_url + "/"
