"""
MYTUBE-573: Hero landing image responsive scaling —
asset maintains integrity at all breakpoints.

Objective
---------
Ensure the new landing image asset scales correctly for mobile, tablet, and
desktop views without layout breaks or distortion.

Steps
-----
1. Open the homepage in a browser at the specified viewport.
2. Confirm the hero section is present and visible.
3. Locate the landing image and assert it has a positive non-zero size.
4. Assert the image fits within its container (hard assertion — no silent skip).
5. Assert object-fit is 'cover' (aspect-ratio preservation via CSS).

Expected Result
---------------
The image scales responsively, maintaining its aspect ratio and fitting within
the visual panel boundaries at all specified breakpoints.

Architecture
------------
- WebConfig (core/config/web_config.py) centralises env var access.
- HeroSectionComponent (components/pages/hero_section/) wraps all hero DOM
  queries — no raw Playwright API in the test body.
- Browser lifecycle is managed by the conftest.py hero_page fixture.
- Tests use only semantic methods from the component; no raw Playwright APIs
  in tests.
- Three parametrised breakpoints: mobile 375px, tablet 768px, desktop 1440px.

Run from repo root:
    pytest testing/tests/MYTUBE-573/test_mytube_573.py -v
"""
from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.hero_section.hero_section_component import (
    HeroSectionComponent,
)

# (hero_page fixture comes from conftest.py; it is parametrised by viewport)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOLERANCE = 2.0  # pixels — tolerance for sub-pixel rounding in container check


def _assert_image_fits_in_container(
    img_box: dict, container_box: dict, label: str, tolerance: float = _TOLERANCE
) -> None:
    """Assert that *img_box* lies within *container_box* (with a small tolerance)."""
    img_right  = img_box["x"] + img_box["width"]
    img_bottom = img_box["y"] + img_box["height"]
    con_right  = container_box["x"] + container_box["width"]
    con_bottom = container_box["y"] + container_box["height"]

    assert img_box["x"] >= container_box["x"] - tolerance, (
        f"[{label}] Image left edge ({img_box['x']:.1f}) overflows container left "
        f"({container_box['x']:.1f})"
    )
    assert img_box["y"] >= container_box["y"] - tolerance, (
        f"[{label}] Image top edge ({img_box['y']:.1f}) overflows container top "
        f"({container_box['y']:.1f})"
    )
    assert img_right <= con_right + tolerance, (
        f"[{label}] Image right edge ({img_right:.1f}) overflows container right "
        f"({con_right:.1f})"
    )
    assert img_bottom <= con_bottom + tolerance, (
        f"[{label}] Image bottom edge ({img_bottom:.1f}) overflows container bottom "
        f"({con_bottom:.1f})"
    )


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_hero_landing_image_responsive_scaling(hero_page) -> None:
    """Verify the landing image scales correctly at the given viewport breakpoint.

    Steps:
      1. Open the homepage at the specified viewport width (handled by fixture).
      2. Confirm the hero section is present.
      3. Locate the landing image and assert it has a positive non-zero size.
      4. Assert the image fits within its container (hard assertion).
      5. Assert object-fit is 'cover' (aspect ratio preserved via CSS).
    """
    hero: HeroSectionComponent
    hero, vp = hero_page
    label = f"{vp.name} {vp.width}px"

    # Step 2 — hero section must be present
    assert hero.is_hero_visible(), (
        f"[{label}] Hero section (section[aria-label='Hero']) not found on the homepage."
    )

    # Step 3 — landing image must be visible with positive dimensions
    img_box = hero.get_landing_image_box()
    assert img_box is not None, (
        f"[{label}] Landing image not found or bounding box unavailable. "
        f"Tried selectors: {HeroSectionComponent._LANDING_IMAGE_SELECTORS}"
    )
    assert img_box["width"] > 0, (
        f"[{label}] Landing image width is zero or negative ({img_box['width']:.1f}) — "
        "image has collapsed and is not displaying."
    )
    assert img_box["height"] > 0, (
        f"[{label}] Landing image height is zero or negative ({img_box['height']:.1f}) — "
        "image has collapsed and is not displaying."
    )

    # Step 4 — image must fit within its container (hard assertion)
    container_box = hero.get_visual_canvas_box()
    assert container_box is not None, (
        f"[{label}] Container element not found. "
        f"Tried: {HeroSectionComponent._VISUAL_CANVAS_SELECTORS + HeroSectionComponent._VISUAL_PANEL_SELECTORS}"
    )
    _assert_image_fits_in_container(img_box, container_box, label)

    # Step 5 — object-fit must be 'cover' (guarantees aspect-ratio preservation)
    obj_fit = hero.get_landing_image_object_fit()
    assert obj_fit == "cover", (
        f"[{label}] Expected object-fit='cover' on the landing image "
        f"to preserve aspect ratio, but got '{obj_fit}'."
    )
