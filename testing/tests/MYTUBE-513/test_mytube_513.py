"""
MYTUBE-513: Player container and title styling — design system visual attributes applied

Objective
---------
Verify the visual styling of the video player container and the typography of
the video title match the design specification.

Steps
-----
1. Navigate to the video watch page.
2. Inspect the .player container element.
3. Inspect the video title element.

Expected Result
---------------
The player container (.player) has:
  - border-radius: 16px
  - overflow: hidden
  - background: #000
  - box-shadow: var(--shadow-card)

The video title (.videoTitle) has:
  - font-size: 22px
  - font-weight: 700
  - color: var(--text-primary)

Test Approach
-------------
Dual-mode:

1. **Static Mode** (primary) — Reads ``WatchPageClient.module.css`` and
   ``globals.css`` directly to assert the correct CSS values and tokens are
   present.  Works in any environment without a running browser.

2. **Live Mode** (secondary) — When APP_URL / WEB_BASE_URL is set, Playwright
   navigates to a deployed watch page and verifies computed styles in the DOM.

Run from repo root:
    pytest testing/tests/MYTUBE-513/test_mytube_513.py -v
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.api_config import APIConfig
from testing.components.pages.watch_page.watch_page import WatchPage
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WEB_SRC = _REPO_ROOT / "web" / "src"
_WATCH_CSS = _WEB_SRC / "app" / "v" / "[id]" / "WatchPageClient.module.css"
_GLOBALS_CSS = _WEB_SRC / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Expected values
# ---------------------------------------------------------------------------

# .player container
_EXPECTED_PLAYER_BORDER_RADIUS = "16px"
_EXPECTED_PLAYER_OVERFLOW = "hidden"
_EXPECTED_PLAYER_BACKGROUND = "#000"
_EXPECTED_PLAYER_BOX_SHADOW = "var(--shadow-card)"

# .videoTitle
_EXPECTED_TITLE_FONT_SIZE = "22px"
_EXPECTED_TITLE_FONT_WEIGHT = "700"
_EXPECTED_TITLE_COLOR = "var(--text-primary)"

_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Mode helpers
# ---------------------------------------------------------------------------


def _should_use_live_mode() -> bool:
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


# ---------------------------------------------------------------------------
# Static analysis helpers
# ---------------------------------------------------------------------------


def _read_source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_css_block(source: str, selector: str) -> str:
    """Extract the body of a CSS rule block for the given selector."""
    pattern = re.compile(
        re.escape(selector) + r"\s*\{([^}]*)\}",
        re.DOTALL,
    )
    match = pattern.search(source)
    assert match, (
        f"CSS selector '{selector}' not found in {_WATCH_CSS.name}. "
        f"Expected a rule block for '{selector}'."
    )
    return match.group(1)


def _assert_css_property(block: str, prop: str, expected_value: str, selector: str) -> None:
    """Assert that *prop* is set to *expected_value* inside *block*."""
    pattern = re.compile(
        rf"{re.escape(prop)}\s*:\s*{re.escape(expected_value)}\s*[;}}]",
        re.IGNORECASE,
    )
    assert pattern.search(block), (
        f"CSS rule '{selector}' must have '{prop}: {expected_value}'. "
        f"Actual block content:\n{block.strip()}"
    )


# ---------------------------------------------------------------------------
# Static tests (always run — no browser required)
# ---------------------------------------------------------------------------


class TestPlayerStylingStatic:
    """MYTUBE-513 (Static): Verify .player container CSS values in source."""

    def test_player_border_radius(self) -> None:
        """
        Step 2 (static) — .player must have border-radius: 16px.
        """
        source = _read_source(_WATCH_CSS)
        block = _extract_css_block(source, ".player")
        _assert_css_property(block, "border-radius", _EXPECTED_PLAYER_BORDER_RADIUS, ".player")

    def test_player_overflow_hidden(self) -> None:
        """
        Step 2 (static) — .player must have overflow: hidden.
        """
        source = _read_source(_WATCH_CSS)
        block = _extract_css_block(source, ".player")
        _assert_css_property(block, "overflow", _EXPECTED_PLAYER_OVERFLOW, ".player")

    def test_player_background_black(self) -> None:
        """
        Step 2 (static) — .player must have background: #000.
        """
        source = _read_source(_WATCH_CSS)
        block = _extract_css_block(source, ".player")
        _assert_css_property(block, "background", _EXPECTED_PLAYER_BACKGROUND, ".player")

    def test_player_box_shadow(self) -> None:
        """
        Step 2 (static) — .player must use box-shadow: var(--shadow-card).
        """
        source = _read_source(_WATCH_CSS)
        block = _extract_css_block(source, ".player")
        _assert_css_property(block, "box-shadow", _EXPECTED_PLAYER_BOX_SHADOW, ".player")


class TestVideoTitleStylingStatic:
    """MYTUBE-513 (Static): Verify .videoTitle typography values in source."""

    def test_title_font_size(self) -> None:
        """
        Step 3 (static) — .videoTitle must have font-size: 22px.
        """
        source = _read_source(_WATCH_CSS)
        block = _extract_css_block(source, ".videoTitle")
        _assert_css_property(block, "font-size", _EXPECTED_TITLE_FONT_SIZE, ".videoTitle")

    def test_title_font_weight(self) -> None:
        """
        Step 3 (static) — .videoTitle must have font-weight: 700.
        """
        source = _read_source(_WATCH_CSS)
        block = _extract_css_block(source, ".videoTitle")
        _assert_css_property(block, "font-weight", _EXPECTED_TITLE_FONT_WEIGHT, ".videoTitle")

    def test_title_color_token(self) -> None:
        """
        Step 3 (static) — .videoTitle must use color: var(--text-primary).
        """
        source = _read_source(_WATCH_CSS)
        block = _extract_css_block(source, ".videoTitle")
        _assert_css_property(block, "color", _EXPECTED_TITLE_COLOR, ".videoTitle")


class TestDesignTokensInGlobalsCss:
    """MYTUBE-513 (Static): Verify design tokens are defined in globals.css."""

    def test_globals_css_defines_shadow_card(self) -> None:
        """
        Step 2 (static) — globals.css :root block must define --shadow-card.
        The .player box-shadow depends on this token.
        """
        source = _read_source(_GLOBALS_CSS)
        root_match = re.search(r":root\s*\{([^}]*)\}", source, re.DOTALL)
        assert root_match, "globals.css :root block not found"
        root_block = root_match.group(1)
        assert "--shadow-card" in root_block, (
            "globals.css :root block must define --shadow-card token. "
            "The .player container box-shadow depends on this CSS variable."
        )

    def test_globals_css_defines_text_primary(self) -> None:
        """
        Step 3 (static) — globals.css :root block must define --text-primary.
        The video title color depends on this token.
        """
        source = _read_source(_GLOBALS_CSS)
        root_match = re.search(r":root\s*\{([^}]*)\}", source, re.DOTALL)
        assert root_match, "globals.css :root block not found"
        root_block = root_match.group(1)
        assert "--text-primary" in root_block, (
            "globals.css :root block must define --text-primary token. "
            "The .videoTitle color depends on this CSS variable."
        )


# ---------------------------------------------------------------------------
# Live Playwright tests (only run when APP_URL / WEB_BASE_URL is set)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def live_watch_page(config: WebConfig):
    """
    Yields a WatchPage already navigated to a watch page.
    Skips if no live URL is configured.

    Video discovery delegates to VideoApiService (service layer) rather than
    making raw HTTP calls inline.  Browser setup delegates to the WatchPage
    Page Object rather than calling sync_playwright() directly in the test.
    """
    if not _should_use_live_mode():
        pytest.skip("Live mode skipped: APP_URL/WEB_BASE_URL not set")

    from playwright.sync_api import sync_playwright

    # Discover a real video ID via the typed service object
    api_config = APIConfig()
    video_svc = VideoApiService(api_config)
    result = video_svc.find_ready_video()
    video_id = result[0] if result else "11111111-1111-1111-1111-111111111111"

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        page = browser.new_page()
        watch = WatchPage(page)
        watch.navigate_to_video(config.base_url, video_id)
        try:
            page.wait_for_selector('[class*="player"]', timeout=15_000)
        except Exception:
            pass
        yield watch
        browser.close()


class TestPlayerStylingLive:
    """MYTUBE-513 (Live): Verify .player computed styles in the deployed app."""

    def test_player_border_radius_live(self, live_watch_page: WatchPage) -> None:
        """
        Step 2 (live) — .player computed border-radius must be 16px.
        """
        value = live_watch_page.get_player_computed_style("borderRadius")
        assert value == "16px", (
            f".player computed border-radius is '{value}', expected '16px'."
        )

    def test_player_overflow_live(self, live_watch_page: WatchPage) -> None:
        """
        Step 2 (live) — .player computed overflow must be hidden.
        """
        value = live_watch_page.get_player_computed_style("overflow")
        assert value == "hidden", (
            f".player computed overflow is '{value}', expected 'hidden'."
        )

    def test_player_background_live(self, live_watch_page: WatchPage) -> None:
        """
        Step 2 (live) — .player computed background-color must be rgb(0, 0, 0).
        """
        value = live_watch_page.get_player_computed_style("backgroundColor")
        assert value == "rgb(0, 0, 0)", (
            f".player computed backgroundColor is '{value}', expected 'rgb(0, 0, 0)' (#000)."
        )

    def test_title_font_size_live(self, live_watch_page: WatchPage) -> None:
        """
        Step 3 (live) — .videoTitle computed font-size must be 22px.
        """
        value = live_watch_page.get_video_title_computed_style("fontSize")
        assert value == "22px", (
            f".videoTitle computed fontSize is '{value}', expected '22px'."
        )

    def test_title_font_weight_live(self, live_watch_page: WatchPage) -> None:
        """
        Step 3 (live) — .videoTitle computed font-weight must be 700.
        """
        value = live_watch_page.get_video_title_computed_style("fontWeight")
        assert value == "700", (
            f".videoTitle computed fontWeight is '{value}', expected '700'."
        )
