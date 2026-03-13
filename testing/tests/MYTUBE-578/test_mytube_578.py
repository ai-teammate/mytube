"""
MYTUBE-578: Update favicon and meta OG images — new logo is reflected in
browser tab and social previews.

Objective
---------
Verify that the site's favicon and Open Graph metadata tags have been updated
to reference the new logo (``logo.svg``).

Steps
-----
1. Open the application in a web browser.
2. Inspect the HTML source code within the ``<head>`` tag.
3. Locate the ``link[rel='icon']`` and the ``meta[property='og:image']`` tags.
4. Verify the asset source URLs.

Expected Result
---------------
The favicon and OG image metadata point to the updated ``logo.svg`` asset.

Architecture
------------
- WebConfig (core/config/web_config.py) centralises env var access.
- HeadMetaPage (testing/components/pages/head_meta_page/) encapsulates all
  Playwright DOM interactions with ``<head>`` metadata tags.
- Playwright sync API with module-scoped pytest fixtures.
- No hardcoded URLs.

Run from repo root:
    pytest testing/tests/MYTUBE-578/test_mytube_578.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.head_meta_page import HeadMetaPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# The expected logo asset name that both favicon and OG image must reference.
_EXPECTED_ASSET = "logo.svg"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    with sync_playwright() as pw:
        br = pw.chromium.launch(headless=web_config.headless, slow_mo=web_config.slow_mo)
        yield br
        br.close()


@pytest.fixture(scope="module")
def head_meta(browser: Browser, web_config: WebConfig) -> HeadMetaPage:
    """Navigate to the home page and yield a HeadMetaPage ready for assertions."""
    context = browser.new_context()
    page = context.new_page()
    head_meta_page = HeadMetaPage(page)
    # ── Step 1: Open the application ─────────────────────────────────────
    head_meta_page.navigate_to(web_config.home_url())
    yield head_meta_page
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFaviconAndOgImageReferenceLogo:
    """Verify that the favicon and OG image metadata both reference logo.svg."""

    def test_favicon_tag_is_present(self, head_meta: HeadMetaPage, web_config: WebConfig) -> None:
        """Step 2 & 3: A favicon link tag must exist in the document <head>."""
        favicon_href = head_meta.get_favicon_href()
        assert favicon_href is not None, (
            "No <link rel='icon'> (or <link rel='shortcut icon'>) found in the document <head>. "
            f"URL: {web_config.home_url()}. "
            f"Expected: a favicon link tag with href referencing '{_EXPECTED_ASSET}'."
        )

    def test_favicon_references_logo_svg(self, head_meta: HeadMetaPage, web_config: WebConfig) -> None:
        """Step 4a: The favicon href must reference logo.svg."""
        favicon_href = head_meta.get_favicon_href()
        assert favicon_href is not None and _EXPECTED_ASSET in favicon_href, (
            f"Favicon href '{favicon_href}' does not reference '{_EXPECTED_ASSET}'. "
            f"URL: {web_config.home_url()}. "
            f"Expected: <link rel='icon' href='.../{_EXPECTED_ASSET}'> or similar. "
            f"The favicon should have been updated from the old asset to '{_EXPECTED_ASSET}' "
            "as part of the logo refresh."
        )

    def test_og_image_tag_is_present(self, head_meta: HeadMetaPage, web_config: WebConfig) -> None:
        """Step 3: A meta og:image tag must exist in the document <head>."""
        og_image_content = head_meta.get_og_image_content()
        assert og_image_content is not None, (
            "No <meta property='og:image'> tag found in the document <head>. "
            f"URL: {web_config.home_url()}. "
            f"Expected: an Open Graph image meta tag with content referencing '{_EXPECTED_ASSET}'."
        )

    def test_og_image_references_logo_svg(self, head_meta: HeadMetaPage, web_config: WebConfig) -> None:
        """Step 4b: The og:image content must reference logo.svg."""
        og_image_content = head_meta.get_og_image_content()
        assert og_image_content is not None and _EXPECTED_ASSET in og_image_content, (
            f"OG image content '{og_image_content}' does not reference '{_EXPECTED_ASSET}'. "
            f"URL: {web_config.home_url()}. "
            f"Expected: <meta property='og:image' content='.../{_EXPECTED_ASSET}'>. "
            f"The OG image should have been updated to '{_EXPECTED_ASSET}' "
            "as part of the logo refresh."
        )
