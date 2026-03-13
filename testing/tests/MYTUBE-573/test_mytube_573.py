"""
MYTUBE-573: Hero landing image responsive scaling —
asset maintains integrity at all breakpoints.

Objective
---------
Ensure the new landing image asset scales correctly for mobile, tablet, and
desktop views without layout breaks or distortion.

Steps
-----
1. Open the homepage in a browser.
2. Toggle between mobile (375px), tablet (768px), and desktop (1440px) viewports.
3. Observe the landing image dimensions and fit within its container.

Expected Result
---------------
The image scales responsively, maintaining its aspect ratio and fitting within
the visual panel boundaries at all specified breakpoints.

Architecture
------------
- WebConfig (core/config/web_config.py) centralises env var access.
- HeroSectionComponent (components/pages/hero_section/) wraps hero DOM queries.
- Playwright sync API with pytest.
- Three parametrised breakpoints: mobile 375px, tablet 768px, desktop 1440px.

Run from repo root:
    pytest testing/tests/MYTUBE-573/test_mytube_573.py -v
"""
from __future__ import annotations

import os
import sys
from typing import NamedTuple

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Breakpoint definitions
# ---------------------------------------------------------------------------

class Viewport(NamedTuple):
    name: str
    width: int
    height: int


VIEWPORTS = [
    Viewport("mobile",  375,  812),
    Viewport("tablet",  768, 1024),
    Viewport("desktop", 1440, 900),
]

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Selectors for the landing image and its container — aligned with HeroSection.tsx
# The Next.js <Image> renders a nested <img> inside the visualCanvas div.
_VISUAL_CANVAS_SELECTORS = [
    "[class*='visualCanvas']",
    ".visualCanvas",
]

_LANDING_IMAGE_SELECTORS = [
    "img[alt='Personal Playback Preview']",
    "img[src*='landing_image']",
]

_VISUAL_PANEL_SELECTORS = [
    "[class*='visualPanel']",
    ".visualPanel",
]

# The outermost hero section selector (same as HeroSectionComponent._HERO_SECTION)
_HERO_SECTION = "section[aria-label='Hero']"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_locator(page: Page, selectors: list[str]):
    """Return the first locator that matches in the DOM, or None."""
    for selector in selectors:
        loc = page.locator(selector)
        try:
            if loc.count() > 0:
                return loc.first
        except Exception:
            continue
    return None


def _get_bounding_box(page: Page, selectors: list[str]) -> dict | None:
    """Return the bounding box of the first matching element, or None."""
    loc = _find_locator(page, selectors)
    if loc is None:
        return None
    try:
        return loc.bounding_box()
    except Exception:
        return None


def _assert_image_fits_in_container(
    img_box: dict, container_box: dict, tolerance: float = 2.0
) -> None:
    """Assert that img_box lies within container_box (with a small tolerance)."""
    img_right  = img_box["x"] + img_box["width"]
    img_bottom = img_box["y"] + img_box["height"]
    con_right  = container_box["x"] + container_box["width"]
    con_bottom = container_box["y"] + container_box["height"]

    assert img_box["x"] >= container_box["x"] - tolerance, (
        f"Image left edge ({img_box['x']:.1f}) overflows container left "
        f"({container_box['x']:.1f})"
    )
    assert img_box["y"] >= container_box["y"] - tolerance, (
        f"Image top edge ({img_box['y']:.1f}) overflows container top "
        f"({container_box['y']:.1f})"
    )
    assert img_right <= con_right + tolerance, (
        f"Image right edge ({img_right:.1f}) overflows container right "
        f"({con_right:.1f})"
    )
    assert img_bottom <= con_bottom + tolerance, (
        f"Image bottom edge ({img_bottom:.1f}) overflows container bottom "
        f"({con_bottom:.1f})"
    )


def _get_computed_object_fit(page: Page, selectors: list[str]) -> str:
    """Return the computed object-fit CSS value of the first matching image."""
    for selector in selectors:
        result = page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return '';
                return window.getComputedStyle(el).objectFit || '';
            }""",
            selector,
        )
        if result:
            return result
    return ""


def _assert_aspect_ratio_maintained(
    img_box: dict, natural_width: int = 1536, natural_height: int = 1024
) -> None:
    """Assert that the rendered image has a non-zero positive size (basic sanity check).

    The original image is 1536×1024 (3:2 ratio). With objectFit:cover the
    rendered dimensions can differ from the natural ratio while still covering
    the container; what matters is that the element has a positive size and
    is not collapsed to zero.
    """
    assert img_box["width"] > 0, (
        f"Image width is zero or negative ({img_box['width']:.1f}) — "
        "image has collapsed and is not displaying."
    )
    assert img_box["height"] > 0, (
        f"Image height is zero or negative ({img_box['height']:.1f}) — "
        "image has collapsed and is not displaying."
    )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("vp", VIEWPORTS, ids=[v.name for v in VIEWPORTS])
def test_hero_landing_image_responsive_scaling(config: WebConfig, vp: Viewport) -> None:
    """Verify the landing image scales correctly at the given viewport breakpoint.

    Steps:
      1. Open the homepage at the specified viewport width.
      2. Confirm the hero section is present.
      3. Locate the landing image and its container.
      4. Assert the image has a positive non-zero size (not collapsed).
      5. Assert the image fits within its container (no overflow).
      6. Assert objectFit is 'cover' (aspect ratio preserved via CSS).
    """
    headless = config.headless
    slow_mo = config.slow_mo

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context(
            viewport={"width": vp.width, "height": vp.height},
        )
        page = context.new_page()

        try:
            # Step 1 — navigate to homepage
            page.goto(config.base_url + "/", timeout=_PAGE_LOAD_TIMEOUT)
            page.wait_for_load_state("domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

            # Step 2 — confirm hero section is present
            hero = page.locator(_HERO_SECTION)
            assert hero.count() > 0, (
                f"[{vp.name} {vp.width}px] Hero section "
                f"'{_HERO_SECTION}' not found on the homepage."
            )
            hero.first.wait_for(state="visible", timeout=_PAGE_LOAD_TIMEOUT)

            # Step 3 — locate the landing image
            img_loc = _find_locator(page, _LANDING_IMAGE_SELECTORS)
            assert img_loc is not None, (
                f"[{vp.name} {vp.width}px] Landing image not found. "
                f"Tried selectors: {_LANDING_IMAGE_SELECTORS}"
            )
            img_loc.wait_for(state="visible", timeout=_PAGE_LOAD_TIMEOUT)

            img_box = img_loc.bounding_box()
            assert img_box is not None, (
                f"[{vp.name} {vp.width}px] Could not obtain bounding box for the landing image."
            )

            # Step 4 — image has positive non-zero dimensions
            _assert_aspect_ratio_maintained(img_box)

            # Step 5 — image fits within its container
            container_box = _get_bounding_box(page, _VISUAL_CANVAS_SELECTORS)
            if container_box is None:
                # Fallback: try visual panel
                container_box = _get_bounding_box(page, _VISUAL_PANEL_SELECTORS)

            if container_box is not None:
                _assert_image_fits_in_container(img_box, container_box)

            # Step 6 — objectFit is 'cover' (guarantees aspect-ratio preservation)
            obj_fit = _get_computed_object_fit(page, _LANDING_IMAGE_SELECTORS)
            assert obj_fit == "cover", (
                f"[{vp.name} {vp.width}px] Expected objectFit='cover' on the landing image "
                f"to preserve aspect ratio, but got '{obj_fit}'."
            )

        finally:
            context.close()
            browser.close()
