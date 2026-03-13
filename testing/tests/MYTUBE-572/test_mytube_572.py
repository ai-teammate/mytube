"""
MYTUBE-572: Hero visual panel image update — landing_image.png is rendered.

Objective
---------
Verify that the Personal Playback Preview placeholder has been replaced with
the specific landing_image.png asset.

Steps
-----
1. Navigate to the homepage.
2. Locate the visual preview panel in the hero section.
3. Inspect the image element within the ``.visual-canvas`` area.

Expected Result
---------------
The image source points to ``landing_image.png`` and the visual content matches
the newly provided design asset instead of the previous placeholder.

Architecture
------------
Two complementary modes:

1. **Static source analysis** (always runs):
   - Reads ``web/src/components/HeroSection.tsx`` and confirms that the
     ``<Image>`` inside the ``visualCanvas`` block uses ``src="/landing_image.png"``.

2. **Live Playwright mode** (runs when APP_URL / WEB_BASE_URL is resolvable):
   - Navigates to the homepage.
   - Waits for the hero section to be visible.
   - Locates the image element within the visual-canvas area of the hero section.
   - Asserts that the rendered ``src`` attribute contains ``landing_image.png``.

Run from repo root:
    pytest testing/tests/MYTUBE-572/test_mytube_572.py -v
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Browser, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.hero_section.hero_section_component import HeroSectionComponent

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HERO_TSX = _REPO_ROOT / "web" / "src" / "components" / "HeroSection.tsx"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_EXPECTED_IMAGE_FILENAME = "landing_image.png"


# ---------------------------------------------------------------------------
# Static source analysis (no browser required)
# ---------------------------------------------------------------------------


class TestHeroImageSourceAnalysis:
    """Validate that the source code references landing_image.png in the hero."""

    def test_hero_tsx_references_landing_image(self) -> None:
        """HeroSection.tsx must use /landing_image.png as the Image src."""
        assert _HERO_TSX.exists(), f"Source file not found: {_HERO_TSX}"
        source = _HERO_TSX.read_text(encoding="utf-8")

        assert 'src="/landing_image.png"' in source, (
            f"Expected 'src=\"/landing_image.png\"' in {_HERO_TSX.name} but it was not found.\n"
            "The hero visual panel must render the landing_image.png asset."
        )

    def test_hero_tsx_no_placeholder_only(self) -> None:
        """The visual canvas image src must not be a generic placeholder URL."""
        assert _HERO_TSX.exists(), f"Source file not found: {_HERO_TSX}"
        source = _HERO_TSX.read_text(encoding="utf-8")

        # Ensure it is not using a placeholder like via.placeholder.com or picsum
        placeholder_patterns = [
            r"via\.placeholder\.com",
            r"picsum\.photos",
            r"placeholder\.(png|jpg|svg)",
            r'src="[^"]*placeholder[^"]*"',
        ]
        for pattern in placeholder_patterns:
            assert not re.search(pattern, source, re.IGNORECASE), (
                f"Found placeholder image pattern '{pattern}' in {_HERO_TSX.name}. "
                "The hero section should use the actual landing_image.png asset."
            )


# ---------------------------------------------------------------------------
# Live browser E2E test
# ---------------------------------------------------------------------------


class TestHeroImageLive:
    """End-to-end browser test: verify landing_image.png is rendered on the homepage."""

    def test_landing_image_rendered_in_hero(self, browser: Browser) -> None:
        """Navigate to the homepage and verify the hero image src is landing_image.png."""
        cfg = WebConfig()
        page = browser.new_page()
        try:
            page.goto(cfg.base_url + "/", timeout=_PAGE_LOAD_TIMEOUT)

            # Wait for the hero section to appear
            hero = HeroSectionComponent(page)
            assert hero.is_hero_visible(timeout=_PAGE_LOAD_TIMEOUT), (
                "Hero section is not visible on the homepage."
            )

            # Retrieve the rendered src via component method — Next.js Image rewrites
            # the src via _next/image, so we check both src and srcset for the filename.
            src, srcset = hero.get_visual_image_src(timeout=_PAGE_LOAD_TIMEOUT)

            assert _EXPECTED_IMAGE_FILENAME in src or _EXPECTED_IMAGE_FILENAME in srcset, (
                f"Expected image src/srcset to contain '{_EXPECTED_IMAGE_FILENAME}'.\n"
                f"Actual src:    {src!r}\n"
                f"Actual srcset: {srcset!r}\n"
                "The hero visual panel does not appear to be rendering landing_image.png."
            )
        finally:
            page.close()
