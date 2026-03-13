"""
MYTUBE-531: Hero CTA 'Upload Your First Video' — button links to upload page
with primary (green gradient pill) styling.

Objective
---------
Verify that the primary CTA button is correctly styled and redirects the user
to the upload page.

Steps
-----
1. Navigate to the homepage.
2. Locate the "Upload Your First Video" button (.btn.cta).
3. Verify the styling includes a green gradient pill and green box-shadow.
4. Click the button.

Expected Result
---------------
The button is rendered with the correct gradient and shadow; clicking it
navigates the browser to the /upload page.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- HeroSectionComponent from testing/components/pages/hero_section/ provides the
  CTA button locator and style helpers (component layer).
- Browser lifecycle is managed by the shared framework fixture
  (testing/frameworks/web/playwright/fixtures.py) via conftest.py.
- Tests use only semantic methods from the component; no raw Playwright APIs
  in tests.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.hero_section.hero_section_component import (
    HeroSectionComponent,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Green gradient from globals.css: linear-gradient(90deg, #62c235 0%, #4fa82b 100%)
# Browsers resolve this to an rgb() form, but the gradient keyword and green
# colour stops must be present in the computed backgroundImage.
_EXPECTED_GRADIENT_START_HEX = "62c235"
_EXPECTED_GRADIENT_END_HEX = "4fa82b"

# Box-shadow: 0 0 0 2px rgba(98, 194, 53, 0.3)  ← green alpha glow
_BOX_SHADOW_GREEN_CHANNEL_R = 98
_BOX_SHADOW_GREEN_CHANNEL_G = 194
_BOX_SHADOW_GREEN_CHANNEL_B = 53

# Button text colour — white (#ffffff → rgb(255, 255, 255))
_EXPECTED_TEXT_COLOR = "rgb(255, 255, 255)"


# ---------------------------------------------------------------------------
# Fixtures (browser lifecycle lives in conftest.py)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def hero(browser_page: Page) -> HeroSectionComponent:
    return HeroSectionComponent(browser_page)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _contains_green_gradient(background_image: str) -> bool:
    """Return True if *background_image* references a green gradient.

    The browser serialises the CSS gradient either as a hex colour literal or
    as rgb()/rgba(), so we check for the hex digits of the two green stops.
    Both colour stops must be present to avoid false positives.
    """
    bi = background_image.lower()
    # Direct hex match (some WebKit builds keep the hex)
    if _EXPECTED_GRADIENT_START_HEX in bi and _EXPECTED_GRADIENT_END_HEX in bi:
        return True
    # rgb() serialisation: rgb(98, 194, 53) and rgb(79, 168, 43)
    if "rgb(98, 194, 53)" in bi and "rgb(79, 168, 43)" in bi:
        return True
    return False


def _has_green_box_shadow(box_shadow: str) -> bool:
    """Return True if *box_shadow* contains green RGB channel values."""
    # Expect something like: rgba(98, 194, 53, 0.3) or rgb(98, 194, 53)
    return (
        f"{_BOX_SHADOW_GREEN_CHANNEL_R}, {_BOX_SHADOW_GREEN_CHANNEL_G}, "
        f"{_BOX_SHADOW_GREEN_CHANNEL_B}" in box_shadow
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHeroCtaUploadButton:
    """MYTUBE-531: 'Upload Your First Video' CTA — styling and navigation."""

    def test_upload_cta_is_visible(self, hero: HeroSectionComponent) -> None:
        """Step 2: The CTA button must be present and visible on the homepage."""
        assert hero.is_upload_cta_visible(), (
            "The 'Upload Your First Video' CTA button (.btn.cta) is not visible "
            "on the homepage. Expected a Link element with class 'btn cta' and text "
            "'Upload Your First Video'."
        )

    def test_upload_cta_has_green_gradient_background(
        self, hero: HeroSectionComponent
    ) -> None:
        """Step 3a: The button background must be the green gradient pill."""
        styles = hero.upload_cta_computed_styles()
        bg_image = styles.get("backgroundImage", "")
        assert _contains_green_gradient(bg_image), (
            f"CTA button does not have the expected green gradient background.\n"
            f"Expected backgroundImage to contain green colour stops "
            f"(#62c235 → #4fa82b / rgb(98,194,53) → rgb(79,168,43)).\n"
            f"Actual backgroundImage: {bg_image!r}"
        )

    def test_upload_cta_has_pill_shape(self, hero: HeroSectionComponent) -> None:
        """Step 3b: The button must have a pill shape (border-radius close to 999px)."""
        styles = hero.upload_cta_computed_styles()
        border_radius = styles.get("borderTopLeftRadius", "")
        assert border_radius not in ("0px", "0", "", "none"), (
            f"CTA button does not have a pill shape.\n"
            f"Expected a large border-radius (Tailwind rounded-full / 999px).\n"
            f"Actual borderTopLeftRadius: {border_radius!r}"
        )

    def test_upload_cta_has_green_box_shadow(self, hero: HeroSectionComponent) -> None:
        """Step 3c: The button must carry the green glow box-shadow."""
        styles = hero.upload_cta_computed_styles()
        box_shadow = styles.get("boxShadow", "")
        assert _has_green_box_shadow(box_shadow), (
            f"CTA button does not have the expected green box-shadow.\n"
            f"Expected box-shadow to contain rgba(98, 194, 53, ...).\n"
            f"Actual boxShadow: {box_shadow!r}"
        )

    def test_upload_cta_has_white_text(self, hero: HeroSectionComponent) -> None:
        """Step 3d: The button text must be white (--text-cta: #ffffff)."""
        styles = hero.upload_cta_computed_styles()
        color = styles.get("color", "")
        assert color == _EXPECTED_TEXT_COLOR, (
            f"CTA button text colour mismatch.\n"
            f"Expected: {_EXPECTED_TEXT_COLOR!r}\n"
            f"Actual:   {color!r}"
        )

    def test_upload_cta_href_points_to_upload(
        self, hero: HeroSectionComponent
    ) -> None:
        """Step 4 (href check): The href attribute must point to /upload."""
        href = hero.upload_cta_href()
        assert "/upload" in href, (
            f"CTA button href does not point to /upload.\n"
            f"Actual href: {href!r}"
        )

    def test_upload_cta_click_navigates_to_upload_page(
        self, hero: HeroSectionComponent, browser_page: Page, config: WebConfig
    ) -> None:
        """Step 4 (click): Clicking the CTA must navigate the browser to /upload."""
        hero.click_upload_cta()
        browser_page.wait_for_url(
            lambda url: "/upload" in url,
            timeout=15_000,
        )
        current = browser_page.url
        assert "/upload" in current, (
            f"After clicking 'Upload Your First Video', the browser did not navigate "
            f"to the /upload page.\n"
            f"Expected URL to contain '/upload'.\n"
            f"Actual URL: {current!r}"
        )
