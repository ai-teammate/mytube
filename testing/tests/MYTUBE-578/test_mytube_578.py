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
- Playwright sync API with pytest.
- No hardcoded URLs.

Run from repo root:
    pytest testing/tests/MYTUBE-578/test_mytube_578.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# The expected logo asset name that both favicon and OG image must reference.
_EXPECTED_ASSET = "logo.svg"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_favicon_href(page: Page) -> str | None:
    """Return the ``href`` of the first ``<link rel='icon'>`` in the document head."""
    loc = page.locator("link[rel='icon']")
    if loc.count() == 0:
        # Also try shortcut icon
        loc = page.locator("link[rel='shortcut icon']")
    if loc.count() == 0:
        return None
    return loc.first.get_attribute("href")


def _get_og_image_content(page: Page) -> str | None:
    """Return the ``content`` of ``<meta property='og:image'>`` in the document head."""
    loc = page.locator("meta[property='og:image']")
    if loc.count() == 0:
        return None
    return loc.first.get_attribute("content")


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def test_favicon_and_og_image_reference_logo_svg() -> None:
    """Verify that the favicon and OG image metadata both reference logo.svg."""
    config = WebConfig()
    home_url = config.home_url()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        try:
            page = browser.new_page()

            # ── Step 1: Open the application ─────────────────────────────────
            page.goto(home_url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")

            # ── Step 2 & 3: Locate link[rel='icon'] ──────────────────────────
            favicon_href = _get_favicon_href(page)

            assert favicon_href is not None, (
                "No <link rel='icon'> (or <link rel='shortcut icon'>) found in the document <head>. "
                f"URL: {home_url}. "
                f"Expected: a favicon link tag with href referencing '{_EXPECTED_ASSET}'."
            )

            # ── Step 4a: Verify favicon references logo.svg ──────────────────
            assert _EXPECTED_ASSET in favicon_href, (
                f"Favicon href '{favicon_href}' does not reference '{_EXPECTED_ASSET}'. "
                f"URL: {home_url}. "
                f"Expected: <link rel='icon' href='.../{_EXPECTED_ASSET}'> or similar. "
                f"The favicon should have been updated from the old asset to '{_EXPECTED_ASSET}' "
                "as part of the logo refresh."
            )

            # ── Step 3 & 4b: Locate and verify og:image ───────────────────────
            og_image_content = _get_og_image_content(page)

            assert og_image_content is not None, (
                "No <meta property='og:image'> tag found in the document <head>. "
                f"URL: {home_url}. "
                f"Expected: an Open Graph image meta tag with content referencing '{_EXPECTED_ASSET}'."
            )

            assert _EXPECTED_ASSET in og_image_content, (
                f"OG image content '{og_image_content}' does not reference '{_EXPECTED_ASSET}'. "
                f"URL: {home_url}. "
                f"Expected: <meta property='og:image' content='.../{_EXPECTED_ASSET}'>. "
                f"The OG image should have been updated to '{_EXPECTED_ASSET}' "
                "as part of the logo refresh."
            )

        finally:
            browser.close()
