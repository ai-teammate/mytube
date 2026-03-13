"""
MYTUBE-587: HeroSection landing image — src attribute includes basePath prefix on GitHub Pages.

Objective
---------
Verify that the hero landing image ``src`` attribute is correctly prefixed
with the ``basePath`` (``/mytube``) when the application is deployed to
GitHub Pages, so the browser fetches ``/mytube/landing_image.png`` with HTTP 200
instead of ``/landing_image.png`` (HTTP 404).

This is a regression test for MYTUBE-584, which was fixed by reading
``NEXT_PUBLIC_BASE_PATH`` in ``HeroSection.tsx`` and prepending it to the
image ``src``.

Preconditions
-------------
The application is built and deployed with ``GITHUB_PAGES=true``, which sets:
  - ``basePath = "/mytube"`` in ``next.config.ts``
  - ``NEXT_PUBLIC_BASE_PATH = "/mytube"`` exported as env var

Steps
-----
1. Navigate to the homepage on the GitHub Pages deployment.
2. Locate the landing image ``<img>`` element within the HeroSection.
3. Inspect the ``src`` attribute of the image element.
4. Verify the network request URL for ``landing_image.png`` receives HTTP 200.

Expected Result
---------------
The ``src`` attribute contains the basePath prefix, e.g. ``/mytube/landing_image.png``,
and the browser fetches the image with HTTP 200.

Run
---
    pytest testing/tests/MYTUBE-587/test_mytube_587.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.hero_section.hero_section_page import HeroSectionPage
from testing.components.pages.hero_section.hero_image_network_component import (
    HeroImageNetworkComponent,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ASSET_FILENAME = "landing_image.png"
_EXPECTED_BASE_PATH = "/mytube"
_EXPECTED_PREFIXED_PATH = f"{_EXPECTED_BASE_PATH}/{_ASSET_FILENAME}"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Layer A — src attribute includes basePath prefix
# ---------------------------------------------------------------------------


class TestHeroImageSrcBasePath:
    """Layer A: the rendered <img> src must include the /mytube basePath prefix."""

    def test_landing_image_src_has_basepath_prefix(self, config: WebConfig) -> None:
        """Navigate to the homepage and assert the landing image src contains the basePath.

        Steps (mirrors manual test):
        1. Navigate to the homepage on the GitHub Pages deployment.
        2. Locate the landing image <img> element.
        3. Inspect the src attribute.

        Expected:
        The src attribute contains '/mytube/landing_image.png', confirming the
        NEXT_PUBLIC_BASE_PATH prefix is applied and MYTUBE-584 regression is absent.
        """
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.headless)
            try:
                page = browser.new_page()
                page.set_viewport_size({"width": 1280, "height": 800})
                hero_page = HeroSectionPage(page)
                attrs = hero_page.get_landing_image_attributes(config.home_url())
            finally:
                browser.close()

        src = attrs.get("src", "")
        assert src, (
            "The landing image <img> element was found but its 'src' attribute is empty. "
            f"Expected the src to contain '{_EXPECTED_PREFIXED_PATH}'. "
            "Check that HeroSection.tsx correctly sets the src using NEXT_PUBLIC_BASE_PATH."
        )

        assert _EXPECTED_BASE_PATH in src, (
            f"The landing image src='{src}' does not contain the expected basePath prefix "
            f"'{_EXPECTED_BASE_PATH}'. "
            f"Expected: src containing '{_EXPECTED_PREFIXED_PATH}'. "
            "This indicates the MYTUBE-584 regression: HeroSection is not prepending "
            "NEXT_PUBLIC_BASE_PATH to the image src on GitHub Pages."
        )

        assert _ASSET_FILENAME in src, (
            f"The landing image src='{src}' does not reference 'landing_image.png'. "
            "Ensure the HeroSection component renders the correct asset."
        )


# ---------------------------------------------------------------------------
# Layer B — network request returns HTTP 200 with basePath-prefixed URL
# ---------------------------------------------------------------------------


class TestHeroImageNetworkWithBasePath:
    """Layer B: the browser must successfully fetch /mytube/landing_image.png (HTTP 200)."""

    def test_landing_image_fetched_with_http_200(self, config: WebConfig) -> None:
        """Make a direct GET to the basePath-prefixed asset URL and assert HTTP 200.

        Steps (mirrors manual test step 4):
        Verify the request URL for landing_image.png in the Network tab
        returns HTTP 200 when accessed with the basePath prefix.

        The asset URL under basePath: {base_url}/landing_image.png
        Since base_url already includes /mytube, this yields:
          https://ai-teammate.github.io/mytube/landing_image.png
        which must return HTTP 200.
        """
        component = HeroImageNetworkComponent(config)
        result = component.fetch_direct()
        asset_url = f"{config.base_url}/{_ASSET_FILENAME}"

        assert result.status == 200, (
            f"Request for '{asset_url}' returned HTTP {result.status}. "
            f"Expected HTTP 200 — the landing image must be reachable at the "
            f"basePath-prefixed URL. "
            f"If HTTP 404: the image is not deployed at {asset_url!r}. "
            f"If this is a regression of MYTUBE-584, check that the src attribute "
            f"in HeroSection.tsx correctly prepends NEXT_PUBLIC_BASE_PATH."
        )

    def test_landing_image_intercepted_with_prefixed_url(self, config: WebConfig) -> None:
        """Load the homepage and intercept the network request for landing_image.png.

        Asserts that:
        1. The browser requests landing_image.png (it appears in the network log).
        2. The intercepted URL includes the basePath prefix.
        3. The response status is HTTP 200.

        This is the closest automated equivalent of the manual test steps:
        open Network tab → refresh → filter for landing_image.png → verify URL + status.
        """
        component = HeroImageNetworkComponent(config)
        captured = component.capture_all_landing_image_responses()

        assert len(captured) > 0, (
            f"No network request for '{_ASSET_FILENAME}' was observed while loading "
            f"'{config.home_url()}'. "
            "Expected: the homepage should trigger a fetch for landing_image.png. "
            "Check that HeroSection.tsx renders an <img> referencing landing_image.png."
        )

        for entry in captured:
            # The intercepted URL must contain the basePath prefix
            assert _EXPECTED_BASE_PATH in entry.url, (
                f"Intercepted request URL '{entry.url}' does not contain the "
                f"expected basePath prefix '{_EXPECTED_BASE_PATH}'. "
                f"This is the MYTUBE-584 regression: the browser is fetching "
                f"the image WITHOUT the /mytube prefix, meaning it will receive "
                f"HTTP 404 on GitHub Pages. "
                f"Fix: ensure HeroSection.tsx prepends NEXT_PUBLIC_BASE_PATH to the src."
            )

            assert entry.status == 200, (
                f"Request for '{entry.url}' returned HTTP {entry.status}. "
                f"Expected HTTP 200 for the basePath-prefixed landing image URL."
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest as _pytest
    _pytest.main([__file__, "-v", "-s"])
