"""
MYTUBE-571: Lazy-load transitions — smooth 0.2s fade-in transition
applied to appearing components.

Objective
---------
Verify that lazily loaded images and components appear with the specified
CSS fade-in animation.

Steps
-----
1. Navigate to the homepage or dashboard.
2. Scroll down to trigger the lazy loading of VideoCard components or images.
3. Observe the visual transition as items appear on the screen.

Expected Result
---------------
Components do not appear instantly; they transition using opacity: 0 to
opacity: 1 over 0.2s with an ease function.

Architecture
------------
The CSS is declared in VideoCard.module.css:
    .thumb img        { opacity: 0; transition: opacity 0.2s ease; }
    .thumb img.loaded { opacity: 1; }

When the <Image> element fires its onLoad event, VideoCard appends the
"loaded" CSS module class to the <img> tag, transitioning opacity 0 → 1.

Navigation is handled by the HomePage component; all DOM/CSS inspection
is delegated to VideoCardComponent — following the project's OOP component
abstraction architecture.

Run from repo root:
    pytest testing/tests/MYTUBE-571/test_mytube_571.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.home_page.home_page import HomePage
from testing.components.pages.home_page.video_card_component import VideoCardComponent
from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_NETWORK_IDLE_TIMEOUT = 15_000  # ms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMytube571LazyLoadFadeTransition:
    """MYTUBE-571 — Verify the 0.2s opacity fade-in on VideoCard thumbnail images."""

    def test_thumbnail_images_have_fade_in_transition(self, config: WebConfig) -> None:
        """
        Full E2E test:

        1. Navigate to the homepage via the HomePage component.
        2. Assert the CSS fade-in rule is present in the loaded stylesheets
           (VideoCard.module.css: .thumb img { opacity: 0; transition: opacity 0.2s; }).
        3. Wait for VideoCard images inside the video grid to appear.
        4. Assert that those images have a CSS transition on 'opacity' with a
           duration of 0.2s and timing function 'ease'.
        5. Assert that images initially have opacity: 0 (before loading).
        6. Scroll down to trigger more cards and verify the same properties.
        """
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=config.headless,
                slow_mo=config.slow_mo,
            )
            try:
                page = browser.new_page(viewport={"width": 1280, "height": 800})

                # ── Step 1: Navigate to homepage ─────────────────────────────
                home = HomePage(page)
                home.navigate(config.home_url())

                # Wait for the video grid to render (skeleton → real cards)
                try:
                    page.wait_for_selector(
                        "#video-grid img",
                        timeout=_NETWORK_IDLE_TIMEOUT,
                    )
                except Exception:
                    try:
                        page.wait_for_selector("main img", timeout=5000)
                    except Exception:
                        pass

                vc = VideoCardComponent(page)

                # ── Step 2: Verify CSS fade-in rule in stylesheets ───────────
                fade_rule = vc.find_fade_css_rule()

                assert fade_rule is not None, (
                    "The CSS fade-in rule for VideoCard thumbnail images was NOT found "
                    "in any loaded stylesheet. "
                    "Expected a rule matching the pattern: "
                    "'.VideoCard_thumb__XXXX img { opacity: 0; transition: opacity ... }' "
                    "(from VideoCard.module.css). "
                    "This suggests the CSS module was not bundled or deployed correctly."
                )

                assert "opacity" in fade_rule["cssText"].lower(), (
                    f"Found a CSS rule containing 'img' and 'transition' but it does not "
                    f"include 'opacity'. Rule: {fade_rule['cssText'][:300]}. "
                    "Expected: the transition must target the opacity property."
                )

                assert "0.2" in fade_rule["cssText"], (
                    f"The CSS fade-in rule does not specify a 0.2s duration. "
                    f"Rule: {fade_rule['cssText'][:300]}. "
                    "Expected: 'transition: opacity 0.2s' (or 'opacity 0.2s ease')."
                )

                # ── Step 3: Inspect images in the video grid ─────────────────
                images_with_transition = vc.get_images_with_opacity_transition()

                if not images_with_transition:
                    # Fallback: try to find any VideoCard image and check it
                    fallback_img = vc.find_any_thumbnail_image()

                    assert fallback_img is not None, (
                        "No <img> elements were found in VideoCard thumbnail containers "
                        "on the homepage. The page may not have loaded any videos, or "
                        "the component structure has changed. "
                        "Expected at least one VideoCard with a thumbnail image."
                    )

                    transition_prop = fallback_img.get("transitionProperty", "") or ""
                    transition_dur = fallback_img.get("transitionDuration", "") or ""
                    transition_fn = fallback_img.get("transitionTimingFunction", "") or ""

                    assert "opacity" in transition_prop.lower() or transition_prop == "all", (
                        f"Thumbnail <img> (selector: {fallback_img['selector']}) does not have "
                        "an opacity CSS transition in computed styles. "
                        f"Got transitionProperty='{transition_prop}'. "
                        "Expected: 'opacity' (from .thumb img { transition: opacity 0.2s ease; })."
                    )
                    if "opacity" in transition_prop.lower():
                        _assert_transition_values(
                            transition_dur, transition_fn, fallback_img["selector"]
                        )
                else:
                    # ── Step 4: Assert transition duration and timing ─────────
                    for img_info in images_with_transition:
                        _assert_transition_values(
                            img_info["transitionDuration"],
                            img_info["transitionTimingFunction"],
                            img_info.get("src", "unknown"),
                        )

                    # ── Step 5: Assert initial opacity is 0 ──────────────────
                    not_yet_loaded = [
                        img for img in images_with_transition
                        if not img.get("complete") or img.get("naturalWidth", 0) == 0
                    ]
                    if not_yet_loaded:
                        for img_info in not_yet_loaded[:3]:
                            initial_opacity = float(img_info.get("opacity", 1))
                            assert initial_opacity == pytest.approx(0.0, abs=0.05), (
                                f"Thumbnail image that has NOT yet finished loading has "
                                f"opacity={initial_opacity}, but expected opacity=0. "
                                f"src: {str(img_info.get('src', ''))[:80]}. "
                                "Expected: before the image loads, VideoCard sets opacity: 0 "
                                "so the image is invisible until the onLoad callback fires."
                            )

                    # Give images time to load then verify opacity: 1
                    page.wait_for_timeout(1000)
                    loaded_results = vc.get_loaded_images_opacity()
                    if loaded_results:
                        for result in loaded_results:
                            assert result["opacity"] == pytest.approx(1.0, abs=0.05), (
                                f"Thumbnail image that has finished loading has "
                                f"opacity={result['opacity']}, expected opacity=1. "
                                f"src: {result['src']}. classes: '{result['classList']}'. "
                                "Expected: after loading, VideoCard adds the 'loaded' CSS "
                                "module class (onLoad callback), transitioning opacity 0 → 1."
                            )

                # ── Step 6: Scroll and verify more images ─────────────────────
                page.mouse.wheel(0, 600)
                page.wait_for_timeout(800)

                scrolled_images = vc.get_images_with_opacity_transition()
                for img_info in scrolled_images:
                    _assert_transition_values(
                        img_info["transitionDuration"],
                        img_info["transitionTimingFunction"],
                        img_info.get("src", "unknown"),
                    )

            finally:
                browser.close()


# ---------------------------------------------------------------------------
# Assertion helper
# ---------------------------------------------------------------------------


def _assert_transition_values(duration: str, timing_fn: str, context: str) -> None:
    """Assert that transition-duration is 0.2s and timing-function is ease."""
    normalised_duration = duration.strip().lower()
    normalised_fn = timing_fn.strip().lower()

    is_correct_duration = normalised_duration in ("0.2s", "200ms")
    assert is_correct_duration, (
        f"Image transition-duration is '{duration}' (context: {str(context)[:80]}). "
        "Expected: '0.2s' (200 ms). "
        "Defined in VideoCard.module.css: .thumb img { transition: opacity 0.2s ease; }"
    )

    # 'ease' is the cubic-bezier(0.25, 0.1, 0.25, 1) preset — browsers may
    # report either form.
    is_ease = (
        normalised_fn == "ease"
        or "cubic-bezier(0.25, 0.1, 0.25, 1)" in normalised_fn
        or "cubic-bezier(0.25,0.1,0.25,1)" in normalised_fn
    )
    assert is_ease, (
        f"Image transition-timing-function is '{timing_fn}' (context: {str(context)[:80]}). "
        "Expected: 'ease' (or its cubic-bezier equivalent). "
        "Defined in VideoCard.module.css: .thumb img { transition: opacity 0.2s ease; }"
    )
