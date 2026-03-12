"""
MYTUBE-450: VideoCard hover state — shadow lifts when mouse enters card area

Objective
---------
Verify that the VideoCard component provides visual feedback via a shadow lift
effect on hover.

Steps
-----
1. Navigate to the homepage.
2. Hover the mouse cursor over a VideoCard component.
3. Move the mouse cursor away from the card.

Expected Result
---------------
The card's box-shadow changes on hover to create a "lift" effect. The transition
is smooth and reverts once the mouse leaves the card area.

Test Approach
-------------
Two complementary strategies are used:

1. CSS source check (fast, no browser):
   Reads VideoCard.module.css directly and verifies that:
   - The .card rule has a box-shadow property (default state).
   - The .card:hover rule has box-shadow: 0 12px 28px rgba(0,0,0,0.14).
   - The .card rule includes transition: box-shadow ... (smooth animation).

2. Playwright live check (browser, against deployed app):
   - Navigates to the homepage.
   - Locates the first VideoCard element.
   - Reads the computed box-shadow BEFORE hovering.
   - Hovers over the card and reads the computed box-shadow AFTER hovering.
   - Asserts the shadow changed to the hover value.
   - Moves the mouse away from the card and reads the box-shadow again.
   - Asserts the shadow reverted to the non-hover value.

Run from repo root:
    pytest testing/tests/MYTUBE-450/test_mytube_450.py -v
"""
from __future__ import annotations

import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.normpath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", )
)
_CSS_PATH = os.path.join(
    _REPO_ROOT, "web", "src", "components", "VideoCard.module.css"
)

# ---------------------------------------------------------------------------
# Expected CSS values
# ---------------------------------------------------------------------------

_EXPECTED_HOVER_SHADOW = "0 12px 28px rgba(0, 0, 0, 0.14)"
_TRANSITION_PROPERTY = "box-shadow"

# Playwright timeout
_PAGE_LOAD_TIMEOUT = 30_000   # ms
_HOVER_SETTLE_MS = 400        # wait for CSS transition to complete (0.2s + buffer)

# VideoCard selector: the outer card div uses the CSS module class which compiles
# to something like "VideoCard_card__<hash>". We match it by its rounded-lg
# structural class OR by the module class pattern.
# The home_page.py component uses: _VIDEO_CARD = "div.rounded-lg"
# But VideoCard.module.css uses .card with border-radius: 16px; the compiled
# class will contain "card" in the name.  We locate by the section + structural
# role: a div that wraps a thumbnail Link and a body div.
_VIDEO_CARD_SELECTOR = "div[class*='card']"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_css() -> str:
    with open(_CSS_PATH, "r", encoding="utf-8") as fh:
        return fh.read()


def _extract_rule(css: str, selector: str) -> str:
    """Return the declaration block for a given CSS selector (best-effort)."""
    pattern = re.compile(
        r"" + re.escape(selector) + r"\s*\{([^}]*)\}",
        re.DOTALL,
    )
    m = pattern.search(css)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Part 1: CSS source analysis (no browser needed)
# ---------------------------------------------------------------------------

class TestVideoCardCSSHoverState:
    """Verify hover shadow CSS is correctly defined in VideoCard.module.css."""

    def test_css_file_exists(self) -> None:
        """The VideoCard.module.css file must exist."""
        assert os.path.isfile(_CSS_PATH), (
            f"CSS module not found: {_CSS_PATH}"
        )

    def test_card_has_default_box_shadow(self) -> None:
        """The .card rule must declare a box-shadow (default / non-hover state)."""
        css = _read_css()
        card_block = _extract_rule(css, ".card")
        assert card_block, "Could not find .card rule in VideoCard.module.css"
        assert "box-shadow" in card_block, (
            ".card rule does not define box-shadow. "
            f"Block found:\n{card_block.strip()}"
        )

    def test_card_hover_has_lift_shadow(self) -> None:
        """The .card:hover rule must set box-shadow to the expected lift value."""
        css = _read_css()
        hover_block = _extract_rule(css, ".card:hover")
        assert hover_block, (
            "Could not find .card:hover rule in VideoCard.module.css. "
            "The hover shadow lift effect appears to be missing."
        )
        assert "box-shadow" in hover_block, (
            ".card:hover rule exists but does not define box-shadow. "
            f"Block found:\n{hover_block.strip()}"
        )
        # Normalise whitespace for comparison
        normalised = re.sub(r"\s+", " ", hover_block).strip()
        assert "0 12px 28px rgba(0, 0, 0, 0.14)" in normalised, (
            f"Expected hover box-shadow '0 12px 28px rgba(0, 0, 0, 0.14)' "
            f"not found in .card:hover block:\n{hover_block.strip()}"
        )

    def test_card_has_box_shadow_transition(self) -> None:
        """The .card rule must include a transition on box-shadow for smooth animation."""
        css = _read_css()
        card_block = _extract_rule(css, ".card")
        assert card_block, "Could not find .card rule in VideoCard.module.css"
        assert "transition" in card_block, (
            ".card rule does not define a transition property. "
            "The hover animation requires 'transition: box-shadow ...'."
        )
        assert "box-shadow" in card_block.split("transition")[1].split(";")[0], (
            "The transition property in .card does not include box-shadow. "
            f"Card block:\n{card_block.strip()}"
        )


# ---------------------------------------------------------------------------
# Part 2: Playwright live check
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context()
        page = context.new_page()
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        yield page
        browser.close()


class TestVideoCardHoverPlaywright:
    """Playwright tests verifying the box-shadow changes on hover in the browser."""

    def test_homepage_has_video_cards(self, browser_page: Page) -> None:
        """The homepage must render at least one VideoCard."""
        cards = browser_page.locator(_VIDEO_CARD_SELECTOR)
        count = cards.count()
        assert count > 0, (
            f"No VideoCard elements found on the homepage using selector "
            f"'{_VIDEO_CARD_SELECTOR}'. "
            "Ensure the homepage is accessible and renders video content."
        )

    def test_box_shadow_changes_on_hover(self, browser_page: Page) -> None:
        """Box-shadow must change to the lift value when hovering over a VideoCard."""
        card = browser_page.locator(_VIDEO_CARD_SELECTOR).first

        # Read shadow BEFORE hover
        shadow_before: str = card.evaluate(
            "el => window.getComputedStyle(el).boxShadow"
        )

        # Hover over the card
        card.hover()
        # Wait for the CSS transition to complete (0.2s transition + buffer)
        browser_page.wait_for_timeout(_HOVER_SETTLE_MS)

        # Read shadow AFTER hover
        shadow_after: str = card.evaluate(
            "el => window.getComputedStyle(el).boxShadow"
        )

        assert shadow_before != shadow_after, (
            f"box-shadow did not change on hover.\n"
            f"  Before hover: {shadow_before!r}\n"
            f"  After hover:  {shadow_after!r}\n"
            "Expected the shadow to change to the lift value."
        )

        # The hover shadow is "0 12px 28px rgba(0, 0, 0, 0.14)".
        # Browsers may normalise colours, e.g. rgba(0, 0, 0, 0.14) →
        # rgba(0, 0, 0, 0.137255) or similar.  We check key numeric values.
        assert "12px" in shadow_after and "28px" in shadow_after, (
            f"Hover box-shadow does not match the expected lift value "
            f"'0 12px 28px rgba(0, 0, 0, 0.14)'.\n"
            f"  Actual computed shadow after hover: {shadow_after!r}"
        )

    def test_box_shadow_reverts_after_mouse_leave(self, browser_page: Page) -> None:
        """Box-shadow must revert to the default value when mouse leaves the card."""
        card = browser_page.locator(_VIDEO_CARD_SELECTOR).first

        # Hover to trigger the lift
        card.hover()
        browser_page.wait_for_timeout(_HOVER_SETTLE_MS)

        shadow_on_hover: str = card.evaluate(
            "el => window.getComputedStyle(el).boxShadow"
        )

        # Move mouse away (to top-left corner of the viewport, outside any card)
        browser_page.mouse.move(0, 0)
        browser_page.wait_for_timeout(_HOVER_SETTLE_MS)

        shadow_after_leave: str = card.evaluate(
            "el => window.getComputedStyle(el).boxShadow"
        )

        assert shadow_on_hover != shadow_after_leave, (
            f"box-shadow did NOT revert after the mouse left the card.\n"
            f"  Shadow on hover:      {shadow_on_hover!r}\n"
            f"  Shadow after leaving: {shadow_after_leave!r}\n"
            "The lift shadow should disappear once the cursor leaves the card."
        )

        # After leaving, the shadow should NOT contain the hover lift values
        assert not ("12px" in shadow_after_leave and "28px" in shadow_after_leave), (
            f"Shadow still contains lift values after mouse left the card.\n"
            f"  Shadow after leaving: {shadow_after_leave!r}"
        )
