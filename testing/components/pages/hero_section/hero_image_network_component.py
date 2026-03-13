"""
HeroImageNetworkComponent — network-layer component for the hero landing image.

Encapsulates all Playwright browser/request lifecycle for capturing HTTP
responses for ``landing_image.png``, keeping this logic out of test methods.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from playwright.sync_api import sync_playwright

from testing.core.config.web_config import WebConfig

_ASSET_FILENAME = "landing_image.png"
_REQUEST_TIMEOUT = 30_000  # ms


@dataclass
class ImageNetworkResponse:
    """Holds the result of a single network response for the landing image."""

    url: str
    status: int
    content_type: str = field(default="")


class HeroImageNetworkComponent:
    """Component that owns Playwright lifecycle for landing image network checks.

    Provides two operations:
    - ``fetch_direct``: direct APIRequestContext GET for the asset URL.
    - ``capture_all_landing_image_responses``: loads the homepage and returns
      all intercepted responses for ``landing_image.png``.
    """

    def __init__(self, config: WebConfig) -> None:
        self._config = config

    def fetch_direct(self) -> ImageNetworkResponse:
        """Make a direct HTTP GET for the landing image and return the result."""
        asset_url = f"{self._config.base_url}/{_ASSET_FILENAME}"
        with sync_playwright() as pw:
            context = pw.request.new_context()
            try:
                response = context.get(asset_url, timeout=_REQUEST_TIMEOUT)
                return ImageNetworkResponse(
                    url=response.url,
                    status=response.status,
                    content_type=response.headers.get("content-type", ""),
                )
            finally:
                context.dispose()

    def capture_all_landing_image_responses(self) -> list[ImageNetworkResponse]:
        """Load the homepage and return ALL intercepted landing image responses."""
        captured: list[ImageNetworkResponse] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=self._config.headless)
            try:
                page = browser.new_page()

                def _on_response(response) -> None:  # type: ignore[no-untyped-def]
                    if _ASSET_FILENAME in response.url:
                        captured.append(
                            ImageNetworkResponse(
                                url=response.url,
                                status=response.status,
                            )
                        )

                page.on("response", _on_response)
                page.goto(
                    self._config.home_url(),
                    timeout=_REQUEST_TIMEOUT,
                    wait_until="networkidle",
                )
            finally:
                browser.close()

        return captured
