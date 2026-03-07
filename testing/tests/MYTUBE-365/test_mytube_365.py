"""
MYTUBE-365: Interact with inputs in mobile viewport — visibility and focus states are correct.

Objective
---------
Verify that text visibility and contrast are maintained on mobile devices and
during element focus. Specifically, the focus state must not change text or
background color in a way that makes content invisible.

Steps
-----
1. Open the site and set the viewport to mobile width (375px).
2. Open the search bar (present in the site header).
3. Focus on the input field and type text.

Expected Result
---------------
Text remains visible in mobile view. The focus state does not change the text
or background color in a way that makes the content invisible.

Test approach
-------------
Uses Playwright's sync API with a mobile-sized viewport (375 × 812, simulating
iPhone SE). The test:
  1. Navigates to the home page at 375 px width.
  2. Locates the search input (aria-label="Search query").
  3. Clicks / focuses the input and types sample text.
  4. Inspects computed CSS color and background-color via getComputedStyle to
     confirm neither the text color nor the background-color makes the typed
     content invisible (i.e., text-color ≠ effective background-color, and text
     is not transparent/invisible).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped browser fixture.
- No hardcoded URLs or credentials.
"""
from __future__ import annotations

import os
import sys
from typing import Tuple

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOBILE_VIEWPORT = {"width": 375, "height": 812}
_MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
)
_SEARCH_INPUT_LABEL = "Search query"
_SAMPLE_QUERY = "hello world"
_PAGE_LOAD_TIMEOUT_MS = 30_000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_rgba(css_value: str) -> Tuple[int, int, int, float]:
    """Parse a CSS rgb() or rgba() string into (r, g, b, a) tuple.

    Returns (0, 0, 0, 0.0) for transparent / unrecognised values.
    """
    import re

    css_value = css_value.strip().lower()
    if css_value in ("transparent", "", "none"):
        return (0, 0, 0, 0.0)

    m = re.match(
        r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*([\d.]+))?\s*\)",
        css_value,
    )
    if not m:
        return (0, 0, 0, 1.0)

    r, g, b = int(m.group(1)), int(m.group(2)), int(m.group(3))
    a = float(m.group(4)) if m.group(4) is not None else 1.0
    return (r, g, b, a)


def _relative_luminance(r: int, g: int, b: int) -> float:
    """Compute WCAG relative luminance from sRGB components (0–255)."""

    def linearize(c: int) -> float:
        s = c / 255.0
        return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

    return 0.2126 * linearize(r) + 0.7152 * linearize(g) + 0.0722 * linearize(b)


def _contrast_ratio(lum1: float, lum2: float) -> float:
    """WCAG contrast ratio between two relative luminance values."""
    lighter = max(lum1, lum2)
    darker = min(lum1, lum2)
    return (lighter + 0.05) / (darker + 0.05)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    """Launch a Chromium browser for the test module."""
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="function")
def mobile_page(browser: Browser) -> Page:
    """Open a fresh browser context with a 375 px mobile viewport."""
    context: BrowserContext = browser.new_context(
        viewport=_MOBILE_VIEWPORT,
        user_agent=_MOBILE_USER_AGENT,
    )
    context.set_default_timeout(_PAGE_LOAD_TIMEOUT_MS)
    page: Page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT_MS)
    yield page
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMobileInputVisibility:
    """MYTUBE-365: Input text must remain visible in mobile viewport and on focus."""

    def _navigate_and_get_search_input(self, page: Page, url: str):
        """Navigate to *url* and return a visible search input locator."""
        page.goto(url)
        page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT_MS)
        search_input = page.get_by_label(_SEARCH_INPUT_LABEL)
        search_input.wait_for(state="visible", timeout=_PAGE_LOAD_TIMEOUT_MS)
        return search_input

    def test_search_input_visible_on_mobile(
        self, mobile_page: Page, web_config: WebConfig
    ) -> None:
        """The search input must be present and visible at 375 px width.

        Navigates to the home page at mobile viewport width and asserts that
        the search input element is visible in the DOM.
        """
        mobile_page.goto(web_config.home_url())
        mobile_page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT_MS)

        search_input = mobile_page.get_by_label(_SEARCH_INPUT_LABEL)
        search_input.wait_for(state="visible", timeout=_PAGE_LOAD_TIMEOUT_MS)

        assert search_input.is_visible(), (
            "Search input (aria-label='Search query') is not visible "
            f"at mobile viewport width {_MOBILE_VIEWPORT['width']}px. "
            f"URL: {mobile_page.url}"
        )

    def test_typed_text_contrast_on_focus(
        self, mobile_page: Page, web_config: WebConfig
    ) -> None:
        """Text typed into the focused search input must have sufficient contrast.

        After focusing the search input and typing, the computed text color and
        background color must yield a WCAG contrast ratio > 3.0:1 (WCAG AA Large
        Text minimum). The test also asserts that the alpha channel of the text
        color is not zero (transparent text).
        """
        search_input = self._navigate_and_get_search_input(mobile_page, web_config.home_url())

        # Focus and type text to trigger focus-state CSS
        search_input.click()
        search_input.type(_SAMPLE_QUERY)

        # Read computed colors while the element has focus
        style_data = mobile_page.evaluate(
            """(selector) => {
                const el = document.activeElement || document.querySelector(selector);
                if (!el) return null;
                const cs = window.getComputedStyle(el);
                return {
                    color:           cs.color,
                    backgroundColor: cs.backgroundColor,
                    value:           el.value,
                };
            }""",
            'input[aria-label="Search query"]',
        )

        assert style_data is not None, (
            "Could not retrieve computed styles from the search input. "
            "The element may not be in the DOM."
        )

        assert style_data.get("value") == _SAMPLE_QUERY, (
            f"Expected the search input value to be {_SAMPLE_QUERY!r} after typing, "
            f"but got {style_data.get('value')!r}."
        )

        text_color_css = style_data.get("color", "")
        bg_color_css = style_data.get("backgroundColor", "")

        tr, tg, tb, ta = _parse_rgba(text_color_css)
        br_val, bg_val, bb_val, ba = _parse_rgba(bg_color_css)

        # Assert text is not transparent
        assert ta > 0.0, (
            f"Focused search input text color is fully transparent (alpha=0). "
            f"Computed color: {text_color_css!r}. "
            f"Text would be invisible to the user."
        )

        # If background is also transparent, the text renders on the white page
        # background — use white (255, 255, 255) as the effective background.
        if ba == 0.0:
            br_val, bg_val, bb_val = 255, 255, 255

        text_lum = _relative_luminance(tr, tg, tb)
        bg_lum = _relative_luminance(br_val, bg_val, bb_val)
        ratio = _contrast_ratio(text_lum, bg_lum)

        # WCAG AA Large Text minimum is 3.0:1; we assert > 3.0 to ensure text is
        # clearly readable and to guard against near-invisible text bugs.
        assert ratio > 3.0, (
            f"The focused search input has a contrast ratio of {ratio:.2f}:1, "
            f"which is below the 3.0:1 minimum — text may be very hard to read. "
            f"Text color: {text_color_css!r}, Background: {bg_color_css!r}. "
            f"Expected contrast ratio > 3.0."
        )

    def test_focus_does_not_hide_text_color(
        self, mobile_page: Page, web_config: WebConfig
    ) -> None:
        """Focus state must not override text color to make it invisible.

        Compares the computed text color before focus (placeholder visible) and
        after focus + typing to detect any CSS :focus rule that zeroes out the
        text alpha or matches the background color.
        """
        search_input = self._navigate_and_get_search_input(mobile_page, web_config.home_url())

        # Capture pre-focus color (blur the element explicitly)
        mobile_page.evaluate("() => { document.activeElement && document.activeElement.blur(); }")
        pre_focus_data = mobile_page.evaluate(
            """() => {
                const el = document.querySelector('input[aria-label="Search query"]');
                if (!el) return null;
                const cs = window.getComputedStyle(el);
                return { color: cs.color, backgroundColor: cs.backgroundColor };
            }"""
        )

        # Focus and type to trigger :focus CSS
        search_input.click()
        search_input.type(_SAMPLE_QUERY)

        post_focus_data = mobile_page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el) return null;
                const cs = window.getComputedStyle(el);
                return { color: cs.color, backgroundColor: cs.backgroundColor };
            }"""
        )

        assert pre_focus_data is not None and post_focus_data is not None, (
            "Could not retrieve computed styles from the search input."
        )

        # Post-focus text must not be transparent
        post_tr, post_tg, post_tb, post_ta = _parse_rgba(post_focus_data["color"])
        assert post_ta > 0.0, (
            f"After focusing the search input and typing text, the text color "
            f"became fully transparent (alpha=0). "
            f"Pre-focus color: {pre_focus_data['color']!r}, "
            f"Post-focus color: {post_focus_data['color']!r}. "
            f"The :focus CSS rule may be setting color to transparent."
        )

        # Post-focus background must not fully obscure the text
        post_br, post_bg_val, post_bb, post_ba = _parse_rgba(post_focus_data["backgroundColor"])
        effective_bg = (
            (post_br, post_bg_val, post_bb) if post_ba > 0.0 else (255, 255, 255)
        )

        text_lum = _relative_luminance(post_tr, post_tg, post_tb)
        bg_lum = _relative_luminance(*effective_bg)
        ratio = _contrast_ratio(text_lum, bg_lum)

        assert ratio > 3.0, (
            f"After focus the search input has contrast ratio {ratio:.2f}:1, "
            f"which is below the 3.0:1 minimum — text may be very hard to read. "
            f"Pre-focus: color={pre_focus_data['color']!r}, bg={pre_focus_data['backgroundColor']!r}. "
            f"Post-focus: color={post_focus_data['color']!r}, bg={post_focus_data['backgroundColor']!r}."
        )
