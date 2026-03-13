"""
MYTUBE-574: Hero landing image accessibility — alt attribute and dimensions are set.

Objective
---------
Verify that the Next.js Image component for the landing asset includes required
accessibility and performance attributes.

Steps
-----
1. Navigate to the homepage.
2. Inspect the <img> tag for the landing image.
3. Check for the presence of alt, width, and height attributes.

Expected Result
---------------
The image tag contains a descriptive alt attribute for accessibility and explicit
width and height values to prevent layout shifts.

Architecture
------------
Two complementary layers:

**Layer A — Static source analysis** (always runs, no browser):
  Reads ``web/src/components/HeroSection.tsx`` and confirms:
  - An ``alt`` prop is passed to the ``<Image>`` component (non-empty string).
  - A ``width`` prop is present with a positive numeric value.
  - A ``height`` prop is present with a positive numeric value.

**Layer B — Live Playwright E2E** (runs against the deployed app):
  1. Opens the homepage.
  2. Locates the ``<img>`` element whose ``src`` contains ``landing_image``.
  3. Asserts that the ``alt`` attribute is present and non-empty.
  4. Asserts that the ``width`` and ``height`` attributes are present and positive.

Run from repo root::

    pytest testing/tests/MYTUBE-574/test_mytube_574.py -v
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Browser

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.hero_section.hero_section_page import HeroSectionPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VIEWPORT = {"width": 1280, "height": 800}

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HERO_SECTION_SRC = _REPO_ROOT / "web" / "src" / "components" / "HeroSection.tsx"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def hero_source() -> str:
    """Return the raw source text of HeroSection.tsx."""
    assert _HERO_SECTION_SRC.exists(), (
        f"HeroSection.tsx not found at expected path: {_HERO_SECTION_SRC}. "
        "Ensure the web source is checked out alongside the testing directory."
    )
    return _HERO_SECTION_SRC.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Layer A — Static source analysis (always runs)
# ---------------------------------------------------------------------------


class TestHeroImageSourceAttributes:
    """Layer A: HeroSection.tsx must declare alt, width, and height on the landing Image."""

    def test_landing_image_has_alt_prop(self, hero_source: str) -> None:
        """
        The <Image> component for landing_image.png must include a non-empty alt prop.

        A missing or empty alt attribute fails WCAG 1.1.1 (Non-text Content).
        """
        # Find the Image block that includes landing_image by searching from the src occurrence
        src_match = re.search(r'src=["\'][^"\']*landing_image[^"\']*["\']', hero_source)
        assert src_match, (
            "No <Image> with src matching 'landing_image' was found in HeroSection.tsx. "
            "Expected: a Next.js <Image src=\"/landing_image.png\" ...> component."
        )

        # Extract surrounding context (up to 500 chars after the src match to capture all props)
        start = max(0, hero_source.rfind("<Image", 0, src_match.start()))
        snippet = hero_source[start : src_match.end() + 500]

        alt_match = re.search(r'\balt=["\']([^"\']+)["\']', snippet)
        assert alt_match, (
            "The landing <Image> component is missing an 'alt' prop or the alt value is empty.\n"
            f"Source snippet:\n{snippet}\n\n"
            "Expected: alt=\"<descriptive text>\" — required for screen reader accessibility."
        )
        alt_value = alt_match.group(1).strip()
        assert alt_value, (
            "The landing <Image> component has an empty alt attribute.\n"
            "Expected: a non-empty descriptive string for screen reader accessibility."
        )

    def test_landing_image_has_width_prop(self, hero_source: str) -> None:
        """
        The <Image> component for landing_image.png must include a positive width prop.

        Explicit width prevents layout shift (CLS) while the image loads.
        """
        src_match = re.search(r'src=["\'][^"\']*landing_image[^"\']*["\']', hero_source)
        assert src_match, (
            "No <Image> with src matching 'landing_image' was found in HeroSection.tsx."
        )
        start = max(0, hero_source.rfind("<Image", 0, src_match.start()))
        snippet = hero_source[start : src_match.end() + 500]

        width_match = re.search(r'\bwidth=\{?(\d+)\}?', snippet)
        assert width_match, (
            "The landing <Image> component is missing a 'width' prop.\n"
            f"Source snippet:\n{snippet}\n\n"
            "Expected: width={<positive integer>} — required to prevent cumulative layout shift."
        )
        width_value = int(width_match.group(1))
        assert width_value > 0, (
            f"The landing <Image> width must be a positive integer, got: {width_value}."
        )

    def test_landing_image_has_height_prop(self, hero_source: str) -> None:
        """
        The <Image> component for landing_image.png must include a positive height prop.

        Explicit height prevents layout shift (CLS) while the image loads.
        """
        src_match = re.search(r'src=["\'][^"\']*landing_image[^"\']*["\']', hero_source)
        assert src_match, (
            "No <Image> with src matching 'landing_image' was found in HeroSection.tsx."
        )
        start = max(0, hero_source.rfind("<Image", 0, src_match.start()))
        snippet = hero_source[start : src_match.end() + 500]

        height_match = re.search(r'\bheight=\{?(\d+)\}?', snippet)
        assert height_match, (
            "The landing <Image> component is missing a 'height' prop.\n"
            f"Source snippet:\n{snippet}\n\n"
            "Expected: height={<positive integer>} — required to prevent cumulative layout shift."
        )
        height_value = int(height_match.group(1))
        assert height_value > 0, (
            f"The landing <Image> height must be a positive integer, got: {height_value}."
        )


# ---------------------------------------------------------------------------
# Layer B — Live Playwright E2E test
# ---------------------------------------------------------------------------


class TestHeroImageLive:
    """Layer B: The rendered <img> in the DOM must have alt, width, and height attributes."""

    def test_hero_landing_image_alt_width_height(
        self, browser: Browser, config: WebConfig
    ) -> None:
        """
        Full E2E verification of MYTUBE-574:

        1. Navigate to the homepage via HeroSectionPage.
        2. Retrieve alt, width, and height from the landing image via the component.
        3. Assert alt attribute is present and non-empty.
        4. Assert width attribute is present and a positive integer.
        5. Assert height attribute is present and a positive integer.
        """
        page = browser.new_page(viewport=_VIEWPORT)
        try:
            hero = HeroSectionPage(page)
            attrs = hero.get_landing_image_attributes(config.home_url())

            # ── Step 3: Assert alt attribute ─────────────────────────────
            alt = attrs.get("alt")
            assert alt is not None, (
                f"The hero landing <img> is missing an 'alt' attribute entirely.\n"
                f"Image src: {attrs.get('src', 'unknown')}\n"
                "Expected: alt attribute with descriptive text for screen reader accessibility."
            )
            assert alt.strip(), (
                f"The hero landing <img> has an empty alt attribute (alt='').\n"
                f"Image src: {attrs.get('src', 'unknown')}\n"
                "Expected: a non-empty descriptive string for screen reader accessibility."
            )

            # ── Step 4: Assert width attribute ────────────────────────────
            width_raw = attrs.get("width")
            assert width_raw is not None, (
                f"The hero landing <img> is missing a 'width' attribute.\n"
                f"Image src: {attrs.get('src', 'unknown')}\n"
                "Expected: width attribute to prevent cumulative layout shift (CLS)."
            )
            try:
                width_val = int(width_raw)
            except (ValueError, TypeError):
                pytest.fail(
                    f"The hero landing <img> 'width' attribute is not a valid integer: "
                    f"{width_raw!r}. Expected a positive integer."
                )
            assert width_val > 0, (
                f"The hero landing <img> 'width' attribute must be > 0, got: {width_val}."
            )

            # ── Step 5: Assert height attribute ───────────────────────────
            height_raw = attrs.get("height")
            assert height_raw is not None, (
                f"The hero landing <img> is missing a 'height' attribute.\n"
                f"Image src: {attrs.get('src', 'unknown')}\n"
                "Expected: height attribute to prevent cumulative layout shift (CLS)."
            )
            try:
                height_val = int(height_raw)
            except (ValueError, TypeError):
                pytest.fail(
                    f"The hero landing <img> 'height' attribute is not a valid integer: "
                    f"{height_raw!r}. Expected a positive integer."
                )
            assert height_val > 0, (
                f"The hero landing <img> 'height' attribute must be > 0, got: {height_val}."
            )

        finally:
            page.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import pytest as _pytest

    _pytest.main([__file__, "-v", "-s"])
