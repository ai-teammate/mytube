"""
MYTUBE-362: Type text in search bar — typed text and placeholder are visible.

Objective
---------
Verify that the search bar placeholder and the text typed by the user are
legible and follow contrast rules.  Specifically:
  - The placeholder text ("Search videos…") is clearly visible.
  - The typed text "Visibility Test" uses a dark color token and is NOT
    white-on-white (i.e. the computed text color is sufficiently dark to be
    readable against the white input background).

Steps
-----
1. Navigate to the homepage.
2. Observe the search bar in the header before any interaction.
3. Click into the search bar and type "Visibility Test".

Expected Result
---------------
The placeholder text (e.g., "Search videos…") is clearly visible.
The typed text "Visibility Test" is visible (not white-on-white) and uses a
dark color token like ``text-gray-600`` or similar.

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web application.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).

Architecture
------------
- Uses SearchPage (Page Object) from testing/components/pages/search_page/ for
  all search input interaction and state-query methods.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs, credentials, or time.sleep calls.
- Raw locators and page.evaluate() calls are encapsulated in SearchPage;
  test methods never call Playwright APIs directly.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Tuple

import pytest
from playwright.sync_api import sync_playwright, Browser, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.search_page.search_page import SearchPage

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_SEARCH_TEXT = "Visibility Test"
_EXPECTED_PLACEHOLDER = "Search videos\u2026"

# Any channel value >= this threshold (0-255) is considered "too light" for
# use as the sole or dominant channel.  A dark color should have a *low*
# average brightness.  We accept text colors whose perceived brightness is
# <= 200 (out of 255), i.e. clearly not pure white (255,255,255).
_MAX_ALLOWED_BRIGHTNESS = 200


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_rgb(color_str: str) -> Tuple[int, int, int]:
    """Parse a computed CSS color string into an (R, G, B) tuple.

    Handles:
    - ``rgb(r, g, b)`` and ``rgba(r, g, b, a)`` — standard format
    - ``oklch(L C H)`` — modern CSS Color 4 format returned by Chromium 112+;
      estimated via L (lightness in [0,1]) multiplied to [0,255].

    Returns (-1, -1, -1) on parse failure so callers can detect it.
    """
    try:
        inner = color_str.strip()
        if inner.startswith("rgba("):
            inner = inner[5:-1]
            parts = [p.strip() for p in inner.split(",")]
            return int(parts[0]), int(parts[1]), int(parts[2])
        if inner.startswith("rgb("):
            inner = inner[4:-1]
            parts = [p.strip() for p in inner.split(",")]
            return int(parts[0]), int(parts[1]), int(parts[2])
        if inner.lower().startswith("oklch("):
            # oklch(L C H [/ alpha]) — L in [0,1], 0=black, 1=white
            # We use L as an approximate luminance; map to [0,255] for R=G=B.
            inner = inner[6:].rstrip(")").split("/")[0].strip()
            parts = inner.split()
            lightness = float(parts[0])
            approx = int(round(lightness * 255))
            return approx, approx, approx
        return -1, -1, -1
    except Exception:
        return -1, -1, -1


def _perceived_brightness(r: int, g: int, b: int) -> float:
    """Return perceived brightness in [0, 255] using the standard luminance formula."""
    return 0.299 * r + 0.587 * g + 0.114 * b


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestSearchBarVisibility:
    """Tests for MYTUBE-362: search bar placeholder and typed-text visibility."""

    def test_search_input_is_present(self, page: Page, web_config: WebConfig) -> None:
        """Step 1 & 2 — Navigate to the homepage; the search bar must be present.

        Verifies:
        - The search input (type="search") exists in the header.
        - The placeholder attribute equals the expected placeholder text.
        """
        search_page = SearchPage(page)
        search_page.navigate_to_home(web_config.base_url)

        _logger.info("Checking search input is present on %s", page.url)

        # Placeholder must be visible and correct
        placeholder = search_page.get_search_input_placeholder()
        assert placeholder, (
            "The search input has no placeholder attribute or the placeholder is empty. "
            f"URL: {page.url}"
        )
        assert placeholder == _EXPECTED_PLACEHOLDER, (
            f"Expected placeholder to be {_EXPECTED_PLACEHOLDER!r}, "
            f"got {placeholder!r}. URL: {page.url}"
        )

        _logger.info("Placeholder text: %r — OK", placeholder)

    def test_placeholder_is_visible_and_has_contrast(
        self, page: Page, web_config: WebConfig
    ) -> None:
        """Step 2 — the placeholder must be visible with sufficient contrast.

        Checks:
        - The input element is visible on the page.
        - The input background is light (white / near-white) so that the
          browser's default grey placeholder is readable.
        """
        search_page = SearchPage(page)

        # Input must be visible
        assert search_page.is_search_input_visible(), (
            "The search input is not visible on the homepage. "
            f"URL: {page.url}"
        )

        # Check background-color of the input is light (white or near-white),
        # which ensures the placeholder grey text will be readable.
        bg_color = search_page.get_search_input_background_color()
        _logger.info("Search input background-color: %s", bg_color)

        assert bg_color not in ("", "not-found"), (
            f"Could not retrieve background-color for search input. Got: {bg_color!r}. "
            f"URL: {page.url}"
        )

        # Accept white (#fff), near-white, or transparent backgrounds.
        # Check for transparent BEFORE parsing because rgba(0,0,0,0) parses
        # to (0,0,0) which looks dark despite being fully transparent.
        allowed = {"rgba(0, 0, 0, 0)", "transparent"}
        if bg_color in allowed:
            _logger.info("Background is transparent — acceptable for contrast")
        else:
            r, g, b = _parse_rgb(bg_color)
            if (r, g, b) == (-1, -1, -1):
                assert False, (
                    f"Unexpected background-color: {bg_color!r}. URL: {page.url}"
                )
            else:
                bg_brightness = _perceived_brightness(r, g, b)
                assert bg_brightness >= 200, (
                    f"Search input background {bg_color!r} (brightness={bg_brightness:.1f}) "
                    "is too dark; the placeholder may not have sufficient contrast. "
                    f"URL: {page.url}"
                )

    def test_typed_text_is_visible_and_dark(
        self, page: Page, web_config: WebConfig
    ) -> None:
        """Step 3 — type text and verify the typed text is dark (not white-on-white).

        Steps:
        1. Click the search input.
        2. Type "Visibility Test".
        3. Assert the input value equals "Visibility Test".
        4. Assert the computed text color is dark (brightness <= _MAX_ALLOWED_BRIGHTNESS).
        """
        search_page = SearchPage(page)

        # Click into the search bar and type
        search_page.fill_search_input(_SEARCH_TEXT)

        # Assert value is reflected in the DOM
        actual_value = search_page.get_search_input_value()
        assert actual_value == _SEARCH_TEXT, (
            f"Expected search input value {_SEARCH_TEXT!r}, got {actual_value!r}. "
            f"URL: {page.url}"
        )
        _logger.info("Search input value: %r — OK", actual_value)

        # Retrieve computed text color — ask the browser to convert to rgb() via canvas
        text_color = search_page.get_search_input_text_color_rgb()
        _logger.info("Search input computed color: %s", text_color)

        assert text_color not in ("", "not-found"), (
            f"Could not retrieve computed text color for search input. "
            f"Got: {text_color!r}. URL: {page.url}"
        )

        r, g, b = _parse_rgb(text_color)
        assert (r, g, b) != (-1, -1, -1), (
            f"Failed to parse computed color {text_color!r} as an RGB value. "
            f"URL: {page.url}"
        )

        brightness = _perceived_brightness(r, g, b)
        _logger.info(
            "Computed color %s → rgb(%d,%d,%d), brightness=%.1f (threshold ≤ %d)",
            text_color, r, g, b, brightness, _MAX_ALLOWED_BRIGHTNESS,
        )

        assert brightness <= _MAX_ALLOWED_BRIGHTNESS, (
            f"Search input typed text color {text_color!r} (brightness={brightness:.1f}) "
            f"is too light — the text may not be readable against a white background. "
            f"Expected brightness ≤ {_MAX_ALLOWED_BRIGHTNESS} (out of 255). "
            f"The CSS on the input should include a dark color class such as "
            f"'text-gray-600' or 'text-gray-900'. URL: {page.url}"
        )

        _logger.info("Text color brightness=%.1f — within acceptable range ✓", brightness)
