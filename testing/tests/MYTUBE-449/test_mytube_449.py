"""
MYTUBE-449: Redesigned VideoCard layout — card displays with shadow, HD label, and tags

Objective
---------
Verify the redesigned VideoCard component correctly applies the new visual styles,
thumbnail labels, and tag pills according to the design spec.

Steps
-----
1. Navigate to the homepage where the video grid is rendered.
2. Locate a video card containing tags.
3. Inspect the outer card element styling.
4. Observe the thumbnail area and the "HD" overlay.
5. Inspect the tag pills at the bottom of the card.

Expected Result
---------------
* Outer card has background: var(--bg-card), border-radius: 16px, and
  box-shadow: var(--shadow-card).
* Thumbnail has aspect-ratio: 16/9 and border-radius: 12px 12px 0 0.
* A small pill labeled "HD" is visible in the top-right of the thumbnail with
  white text and semi-transparent background.
* Tags are rendered as small pills with background: var(--accent-pill-bg) and
  color: var(--text-pill).

Test Approach
-------------
Playwright navigates to the deployed homepage and:
  1. Waits for video cards to be visible.
  2. Uses JavaScript evaluate() to locate card elements by DOM structure
     (thumbnail anchors with aria-label pointing to /v/...).
  3. Reads getComputedStyle() values and compares against the expected design
     token values defined in globals.css and VideoCard.module.css.
  4. For tag pills: finds the first card that has tag spans and verifies their
     computed colours.

CSS design tokens (globals.css light theme):
  --bg-card:        #f3f4f8  → rgb(243, 244, 248)
  --shadow-card:    0 8px 20px rgba(0, 0, 0, 0.08)
  --accent-pill-bg: #e5daf6  → rgb(229, 218, 246)
  --text-pill:      #6d40cb  → rgb(109, 64, 203)

Architecture
------------
- Uses WebConfig from testing/core/config/web_config.py.
- Uses HomePage page-object from testing/components/pages/home_page/.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or environment values.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.home_page.home_page import HomePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Expected computed colour values (CSS variables resolved from globals.css).
# Values are the browser-normalised rgb() form of the hex colour.
_EXPECTED_BG_CARD = "rgb(243, 244, 248)"     # --bg-card: #f3f4f8
_EXPECTED_BORDER_RADIUS_CARD = "16px"
_EXPECTED_THUMB_BORDER_RADIUS = "12px 12px 0px 0px"
_EXPECTED_HD_COLOR = "rgb(255, 255, 255)"    # white text on HD label
_EXPECTED_TAG_BG = "rgb(229, 218, 246)"      # --accent-pill-bg: #e5daf6
_EXPECTED_TAG_COLOR = "rgb(109, 64, 203)"    # --text-pill: #6d40cb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    """Launch Chromium, navigate to homepage, and yield the loaded page."""
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context()
        page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        home = HomePage(page)
        home.navigate(config.base_url)

        # Wait until at least one thumbnail anchor is present.
        page.wait_for_selector(
            "a[href*='/v/'][aria-label]",
            state="visible",
            timeout=_PAGE_LOAD_TIMEOUT,
        )
        yield page
        context.close()
        browser.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_card_styles(page: Page) -> Optional[dict]:
    """Return computed styles of the first VideoCard outer div.

    Locates the card via the thumbnail anchor (a[href*='/v/'][aria-label]) and
    walks up to its parent element (the card div).
    """
    return page.evaluate(
        """() => {
            const thumbLink = document.querySelector('a[href*="/v/"][aria-label]');
            if (!thumbLink) return null;
            const card = thumbLink.parentElement;
            if (!card) return null;
            const cs = getComputedStyle(card);
            return {
                backgroundColor: cs.backgroundColor,
                borderRadius: cs.borderRadius,
                boxShadow: cs.boxShadow,
            };
        }"""
    )


def _get_thumb_styles(page: Page) -> Optional[dict]:
    """Return computed styles of the first VideoCard thumbnail anchor."""
    return page.evaluate(
        """() => {
            const thumbLink = document.querySelector('a[href*="/v/"][aria-label]');
            if (!thumbLink) return null;
            const cs = getComputedStyle(thumbLink);
            return {
                aspectRatio: cs.aspectRatio,
                borderRadius: cs.borderRadius,
            };
        }"""
    )


def _get_hd_label_styles(page: Page) -> Optional[dict]:
    """Return computed styles and visibility of the HD label span.

    Finds the HD overlay span using the CSS-module class name pattern
    'VideoCard_thumbLabel' (Next.js generates 'VideoCard_thumbLabel__<hash>').
    Falls back to finding a span with text 'HD' inside a thumbnail anchor.
    """
    return page.evaluate(
        """() => {
            // Primary: use CSS-module generated class name pattern
            let hdSpan = document.querySelector('span[class*="thumbLabel"]');

            // Fallback: span with text "HD" inside a thumbnail anchor
            if (!hdSpan) {
                const allSpans = Array.from(document.querySelectorAll('span'));
                hdSpan = allSpans.find(
                    s => s.textContent.trim() === 'HD' &&
                         s.closest('a[href*="/v/"][aria-label]')
                ) || null;
            }

            if (!hdSpan) return null;
            const cs = getComputedStyle(hdSpan);
            const rect = hdSpan.getBoundingClientRect();
            return {
                color: cs.color,
                backgroundColor: cs.backgroundColor,
                visible: rect.width > 0 && rect.height > 0,
                text: hdSpan.textContent.trim(),
            };
        }"""
    )


def _get_tag_pill_styles(page: Page) -> Optional[dict]:
    """Return computed styles of the first tag pill found across all cards.

    Uses the CSS-module generated class name pattern 'VideoCard_tagPill'
    (Next.js generates 'VideoCard_tagPill__<hash>') to precisely identify tag
    pill spans. Falls back to a structural heuristic if the class pattern is
    unavailable.
    """
    return page.evaluate(
        """() => {
            // Primary approach: CSS-module class name contains "tagPill"
            const tagPillSpan = document.querySelector('span[class*="tagPill"]');
            if (tagPillSpan) {
                const cs = getComputedStyle(tagPillSpan);
                return {
                    backgroundColor: cs.backgroundColor,
                    color: cs.color,
                    text: tagPillSpan.textContent.trim(),
                };
            }

            // Fallback: structural heuristic — find spans inside a card body
            // that are NOT inside the thumbnail anchor and NOT in the sub-line
            // (videoSub). The videoTags div comes after the videoSub div and
            // contains spans with a non-transparent background.
            const thumbLinks = Array.from(
                document.querySelectorAll('a[href*="/v/"][aria-label]')
            );
            for (const thumbLink of thumbLinks) {
                const card = thumbLink.parentElement;
                if (!card) continue;

                // Gather all spans not in the thumb anchor
                const bodySpans = Array.from(card.querySelectorAll('span')).filter(
                    s => !thumbLink.contains(s)
                );

                // Tag pill spans have a coloured (non-transparent) background
                for (const span of bodySpans) {
                    const bg = getComputedStyle(span).backgroundColor;
                    if (bg && bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') {
                        const cs = getComputedStyle(span);
                        return {
                            backgroundColor: cs.backgroundColor,
                            color: cs.color,
                            text: span.textContent.trim(),
                        };
                    }
                }
            }
            return null;
        }"""
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestVideoCardLayout:
    """MYTUBE-449: Redesigned VideoCard — visual styles, HD label, and tag pills."""

    def test_card_background_and_border_radius(self, browser_page: Page) -> None:
        """
        Step 3 — Inspect the outer card element styling.

        Expected:
          background: var(--bg-card)  → rgb(243, 244, 248)
          border-radius: 16px
        """
        styles = _get_card_styles(browser_page)
        assert styles is not None, (
            "Could not locate any VideoCard element on the homepage. "
            "Expected to find <a href*='/v/' aria-label='...'> — ensure the "
            "homepage is reachable and at least one video is published."
        )
        assert styles["backgroundColor"] == _EXPECTED_BG_CARD, (
            f"VideoCard outer div background-color mismatch.\n"
            f"  Expected: {_EXPECTED_BG_CARD!r}  (var(--bg-card) = #f3f4f8)\n"
            f"  Actual:   {styles['backgroundColor']!r}\n"
            f"  Check VideoCard.module.css '.card' rule and globals.css --bg-card token."
        )
        assert styles["borderRadius"] == _EXPECTED_BORDER_RADIUS_CARD, (
            f"VideoCard outer div border-radius mismatch.\n"
            f"  Expected: {_EXPECTED_BORDER_RADIUS_CARD!r}\n"
            f"  Actual:   {styles['borderRadius']!r}\n"
            f"  Check '.card {{ border-radius: 16px }}' in VideoCard.module.css."
        )

    def test_card_box_shadow(self, browser_page: Page) -> None:
        """
        Step 3 (continued) — box-shadow: var(--shadow-card).

        The shadow-card token is: 0 8px 20px rgba(0, 0, 0, 0.08).
        We verify the computed box-shadow is non-empty and contains the expected
        offset/spread/colour signature rather than an exact string match, because
        browsers may normalise the rgba notation slightly.
        """
        styles = _get_card_styles(browser_page)
        assert styles is not None, (
            "Could not locate any VideoCard element — see previous test for details."
        )
        box_shadow = styles["boxShadow"]
        assert box_shadow and box_shadow.lower() != "none", (
            f"VideoCard outer div has no box-shadow.\n"
            f"  Expected a shadow matching var(--shadow-card): "
            f"0 8px 20px rgba(0, 0, 0, 0.08)\n"
            f"  Actual: {box_shadow!r}\n"
            f"  Check '.card {{ box-shadow: var(--shadow-card) }}' and "
            f"--shadow-card token in globals.css."
        )
        # Verify the shadow contains "8px" as the Y-offset — key identifier.
        assert "8px" in box_shadow, (
            f"VideoCard box-shadow does not contain expected 8px Y-offset.\n"
            f"  Expected --shadow-card: 0 8px 20px rgba(0,0,0,0.08)\n"
            f"  Actual: {box_shadow!r}"
        )

    def test_thumbnail_aspect_ratio_and_border_radius(self, browser_page: Page) -> None:
        """
        Step 4 — Observe the thumbnail area.

        Expected:
          aspect-ratio: 16 / 9
          border-radius: 12px 12px 0 0
        """
        styles = _get_thumb_styles(browser_page)
        assert styles is not None, (
            "Could not locate any VideoCard thumbnail anchor element. "
            "Expected <a href*='/v/' aria-label='...'> on the homepage."
        )

        aspect = styles["aspectRatio"]
        # Browsers may report as "16 / 9" or "1.7778" — check for 16 / 9 ratio.
        assert "16" in aspect and "9" in aspect, (
            f"Thumbnail aspect-ratio does not match 16/9 spec.\n"
            f"  Expected: '16 / 9' (or browser-normalised equivalent)\n"
            f"  Actual:   {aspect!r}\n"
            f"  Check '.thumb {{ aspect-ratio: 16 / 9 }}' in VideoCard.module.css."
        )

        thumb_br = styles["borderRadius"]
        assert thumb_br == _EXPECTED_THUMB_BORDER_RADIUS, (
            f"Thumbnail border-radius mismatch.\n"
            f"  Expected: {_EXPECTED_THUMB_BORDER_RADIUS!r}\n"
            f"  Actual:   {thumb_br!r}\n"
            f"  Check '.thumb {{ border-radius: 12px 12px 0 0 }}' in VideoCard.module.css."
        )

    def test_hd_label_is_visible_with_correct_styling(self, browser_page: Page) -> None:
        """
        Step 4 (continued) — Verify the HD overlay label.

        Expected:
          - Visible in the top-right of the thumbnail.
          - Text content: "HD".
          - color: #fff  → rgb(255, 255, 255)
          - background: rgba(0, 0, 0, 0.55)  (semi-transparent dark pill)
        """
        styles = _get_hd_label_styles(browser_page)
        assert styles is not None, (
            "Could not find an 'HD' label span inside any VideoCard thumbnail anchor. "
            "Expected <span class='..thumbLabel..'>HD</span> inside "
            "<a href*='/v/' aria-label='...'>."
        )
        assert styles["text"] == "HD", (
            f"HD label text is not 'HD'. Got: {styles['text']!r}"
        )
        assert styles["visible"], (
            "HD label span has zero dimensions — it is not visible on screen. "
            "Check that .thumbLabel is positioned with z-index:1 and is not hidden."
        )
        assert styles["color"] == _EXPECTED_HD_COLOR, (
            f"HD label text color mismatch.\n"
            f"  Expected: {_EXPECTED_HD_COLOR!r}  (#fff)\n"
            f"  Actual:   {styles['color']!r}\n"
            f"  Check '.thumbLabel {{ color: #fff }}' in VideoCard.module.css."
        )
        # Background is rgba(0,0,0,0.55) — semi-transparent dark.
        bg = styles["backgroundColor"]
        assert bg and bg.lower() != "transparent" and bg != "rgba(0, 0, 0, 0)", (
            f"HD label background is transparent or unset.\n"
            f"  Expected: rgba(0, 0, 0, 0.55)  (semi-transparent dark)\n"
            f"  Actual:   {bg!r}\n"
            f"  Check '.thumbLabel {{ background: rgba(0,0,0,0.55) }}' "
            f"in VideoCard.module.css."
        )

    def test_tag_pills_background_and_color(self, browser_page: Page) -> None:
        """
        Step 5 — Inspect the tag pills at the bottom of a card with tags.

        Expected:
          background: var(--accent-pill-bg) → rgb(229, 218, 246)
          color:      var(--text-pill)       → rgb(109, 64, 203)

        If no card on the homepage has tags, this test is skipped.
        """
        styles = _get_tag_pill_styles(browser_page)
        if styles is None:
            pytest.skip(
                "No video cards with tags found on the homepage. "
                "Seed at least one video with tags to exercise the tag pill styles."
            )

        assert styles["backgroundColor"] == _EXPECTED_TAG_BG, (
            f"Tag pill background-color mismatch.\n"
            f"  Expected: {_EXPECTED_TAG_BG!r}  (var(--accent-pill-bg) = #e5daf6)\n"
            f"  Actual:   {styles['backgroundColor']!r}\n"
            f"  Tag text was: {styles['text']!r}\n"
            f"  Check '.tagPill {{ background: var(--accent-pill-bg) }}' in "
            f"VideoCard.module.css and --accent-pill-bg token in globals.css."
        )
        assert styles["color"] == _EXPECTED_TAG_COLOR, (
            f"Tag pill text color mismatch.\n"
            f"  Expected: {_EXPECTED_TAG_COLOR!r}  (var(--text-pill) = #6d40cb)\n"
            f"  Actual:   {styles['color']!r}\n"
            f"  Tag text was: {styles['text']!r}\n"
            f"  Check '.tagPill {{ color: var(--text-pill) }}' in "
            f"VideoCard.module.css and --text-pill token in globals.css."
        )
