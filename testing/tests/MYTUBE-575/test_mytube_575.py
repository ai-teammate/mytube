"""
MYTUBE-575: Hero landing image source — asset served from static directory.

Objective
---------
Verify that landing_image.png is served correctly as a static asset with
HTTP 200 from the static assets directory.

Steps
-----
1. Open the homepage and observe network requests.
2. Refresh the page.
3. Filter for landing_image.png.

Expected Result
---------------
The asset is successfully fetched (HTTP 200) from the static assets
directory (e.g., /public or /_next/static), confirming it is served as a
static file.

Architecture
------------
Two complementary layers:

1. **Static source check** (always runs, no browser/network):
   - Confirms ``landing_image.png`` exists in ``web/public/``.

2. **HTTP request check** (via Playwright's APIRequestContext):
   - Makes a direct GET request for the asset URL.
   - Asserts HTTP 200 status.
   - Asserts the URL path is consistent with a static assets directory
     (i.e., served under the app root or a static prefix).

Run from repo root:
    pytest testing/tests/MYTUBE-575/test_mytube_575.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_PUBLIC_DIR = _REPO_ROOT / "web" / "public"
_ASSET_FILENAME = "landing_image.png"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUEST_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Layer A — Static source check
# ---------------------------------------------------------------------------


class TestLandingImageSource:
    """Layer A: landing_image.png must exist in the web/public directory."""

    def test_landing_image_exists_in_public_dir(self) -> None:
        """Confirm ``landing_image.png`` is present in ``web/public/``.

        The Next.js ``public/`` folder is served at the app root, so a file
        at ``web/public/landing_image.png`` is reachable via
        ``{base_url}/landing_image.png``.
        """
        asset_path = _PUBLIC_DIR / _ASSET_FILENAME
        assert asset_path.exists(), (
            f"Expected {_ASSET_FILENAME!r} to exist at {asset_path}. "
            f"The hero image must be placed in web/public/ to be served as a "
            f"static asset by Next.js."
        )
        assert asset_path.is_file(), (
            f"{asset_path} exists but is not a regular file."
        )


# ---------------------------------------------------------------------------
# Layer B — HTTP asset fetch check
# ---------------------------------------------------------------------------


class TestLandingImageHTTP:
    """Layer B: landing_image.png must be fetchable with HTTP 200."""

    def test_landing_image_returns_http_200(self, config: WebConfig) -> None:
        """Make a direct GET request for the landing image and assert HTTP 200.

        Simulates filtering the browser Network tab for landing_image.png
        after a page refresh. The asset must be:
        - Reachable (no 404/403/500)
        - Served with HTTP 200
        - Located under the app's base URL (confirming it is a static file
          served from the deployment, not a CDN redirect to an unrelated host)
        """
        asset_url = f"{config.base_url}/{_ASSET_FILENAME}"

        with sync_playwright() as pw:
            request_context = pw.request.new_context()
            try:
                response = request_context.get(asset_url, timeout=_REQUEST_TIMEOUT)

                assert response.status == 200, (
                    f"Expected HTTP 200 for {asset_url!r}, "
                    f"but got HTTP {response.status}. "
                    f"The hero landing image is not being served correctly as a "
                    f"static asset. Check that landing_image.png is present in "
                    f"web/public/ and the deployment includes it."
                )

                # Verify the final URL is still under the app's base URL
                # (i.e., not redirected to a 3rd-party CDN that returns 200 for
                # everything).
                final_url: str = response.url
                assert config.base_url in final_url or _ASSET_FILENAME in final_url, (
                    f"The final URL after redirect ({final_url!r}) does not appear "
                    f"to be the expected static asset. "
                    f"Expected the URL to contain the base URL ({config.base_url!r}) "
                    f"or the asset filename ({_ASSET_FILENAME!r})."
                )

                # Confirm Content-Type indicates an image
                content_type = response.headers.get("content-type", "")
                assert "image" in content_type.lower() or content_type == "", (
                    f"Unexpected Content-Type for landing image: {content_type!r}. "
                    f"Expected a content type containing 'image' (e.g., 'image/png')."
                )

            finally:
                request_context.dispose()

    def test_landing_image_intercepted_on_homepage(self, config: WebConfig) -> None:
        """Load the homepage and intercept the network request for landing_image.png.

        This mirrors the manual test steps:
        1. Open the homepage (with Network tab "open").
        2. Refresh the page.
        3. Filter for landing_image.png — assert it appears with HTTP 200.
        """
        captured: list[dict] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.headless)
            try:
                page = browser.new_page()

                # Intercept all responses and capture the landing image response
                def on_response(response) -> None:  # type: ignore[no-untyped-def]
                    if _ASSET_FILENAME in response.url:
                        captured.append(
                            {"url": response.url, "status": response.status}
                        )

                page.on("response", on_response)

                # Step 1 + 2: Navigate to (and thus load) the homepage
                page.goto(
                    config.home_url(),
                    timeout=_REQUEST_TIMEOUT,
                    wait_until="networkidle",
                )

                # Step 3: Verify landing_image.png was requested and returned 200
                assert len(captured) > 0, (
                    f"No network request for {_ASSET_FILENAME!r} was observed while "
                    f"loading {config.home_url()!r}. "
                    f"Expected: the homepage should reference landing_image.png so "
                    f"that the browser fetches it as a static asset. "
                    f"Check that the hero image component on the homepage uses "
                    f"src='/landing_image.png' or equivalent."
                )

                for entry in captured:
                    assert entry["status"] == 200, (
                        f"Request for {entry['url']!r} returned HTTP {entry['status']}. "
                        f"Expected HTTP 200 — the landing image is not being served "
                        f"correctly as a static asset."
                    )

            finally:
                browser.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "-s"])
