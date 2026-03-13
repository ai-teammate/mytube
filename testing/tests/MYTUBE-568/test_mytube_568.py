"""
MYTUBE-568: Video player container — fixed 16:9 aspect ratio prevents layout jump during mount.

Objective
---------
Verify that the video player container uses a fixed aspect ratio to eliminate
layout shifts (CLS) when the Video.js player mounts asynchronously.

Steps (per test spec)
---------------------
1. Navigate to a video watch page.
2. Observe the player container area while the player is loading/mounting.
3. Inspect the CSS properties of the player wrapper.
4. Monitor for any vertical movement of the metadata content below the player
   as it initialises.

Expected Result
---------------
The container maintains a fixed aspect ratio using ``aspect-ratio: 16/9`` or
``padding-top: 56.25%``. No layout jump occurs when the async player content
resolves.

Architecture
------------
- Dual-mode: static CSS class analysis (always) + live Playwright (when APP_URL set).
- WebConfig (testing/core/config/web_config.py) centralises env-var access.
- WatchPage page object (testing/components/pages/watch_page/watch_page.py).
- VideoApiService discovers a real video ID from the API.
- No hardcoded URLs; no time.sleep — Playwright auto-wait handles async init.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
API_BASE_URL             Backend API base URL for video discovery.
                         Default: http://localhost:8081
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-568/test_mytube_568.py -v
"""
from __future__ import annotations

import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import Optional

import pytest
from playwright.sync_api import Browser, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.core.config.api_config import APIConfig
from testing.components.pages.watch_page.watch_page import WatchPage
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WATCH_PAGE_CSS = (
    _REPO_ROOT / "web" / "src" / "app" / "v" / "[id]" / "WatchPageClient.module.css"
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_PLAYER_INIT_TIMEOUT = 10_000  # ms — wait for Video.js to partially init

# Fallback video ID used when the API is unreachable
_FALLBACK_VIDEO_ID = "_"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _is_app_reachable(url: str) -> bool:
    try:
        urllib.request.urlopen(url, timeout=10)
        return True
    except Exception:
        return False


def _resolve_video_id() -> str:
    """Return a ready video ID via VideoApiService, or the fallback placeholder."""
    video_svc = VideoApiService(APIConfig())
    result = video_svc.find_ready_video(override_id=os.getenv("TEST_VIDEO_ID", ""))
    return result[0] if result else _FALLBACK_VIDEO_ID


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def playwright_browser(config: WebConfig) -> Browser:
    """Start a Chromium browser for the duration of the test module."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless, slow_mo=config.slow_mo
        )
        yield browser
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMytube568AspectRatioNoCLS:
    """MYTUBE-568 — Player container has fixed 16:9 aspect ratio (no CLS)."""

    # ──────────────────────────────────────────────────────────────────────────
    # Static analysis (always runs — no browser required)
    # ──────────────────────────────────────────────────────────────────────────

    def test_static_player_has_aspect_ratio_css(self) -> None:
        """WatchPageClient.module.css must define aspect-ratio:16/9 on .player.

        The CSS comment in the source explicitly states this prevents CLS.
        """
        css = _read_file(_WATCH_PAGE_CSS)
        assert css, (
            f"WatchPageClient.module.css not found at {_WATCH_PAGE_CSS}. "
            "The file is required to verify the player aspect-ratio fix."
        )

        # Extract the .player { } block from the CSS source
        player_block_match = re.search(
            r"\.player\s*\{([^}]*)\}", css, re.DOTALL
        )
        assert player_block_match, (
            "No '.player { }' rule found in WatchPageClient.module.css. "
            "Expected a .player class that wraps the Video.js player container."
        )
        player_block = player_block_match.group(1)

        # Must have aspect-ratio: 16 / 9 (spaces optional) OR padding-top fallback
        has_aspect_ratio = re.search(
            r"aspect-ratio\s*:\s*16\s*/\s*9", player_block
        )
        has_padding_top_fallback = re.search(
            r"padding-top\s*:\s*56\.25%", player_block
        )
        assert has_aspect_ratio or has_padding_top_fallback, (
            "Expected '.player' to declare 'aspect-ratio: 16 / 9' or "
            "'padding-top: 56.25%' in WatchPageClient.module.css, but neither "
            "was found.\n"
            f"Actual .player block:\n{player_block.strip()}\n\n"
            "Without a fixed aspect ratio, the player container has zero height "
            "before Video.js mounts, causing a large CLS layout shift when the "
            "player initialises asynchronously."
        )

    def test_static_player_has_width_100_percent(self) -> None:
        """The .player block must set width:100% to fill the column."""
        css = _read_file(_WATCH_PAGE_CSS)
        assert css, f"WatchPageClient.module.css not found at {_WATCH_PAGE_CSS}"

        player_block_match = re.search(r"\.player\s*\{([^}]*)\}", css, re.DOTALL)
        assert player_block_match, "No '.player { }' rule found in WatchPageClient.module.css."
        player_block = player_block_match.group(1)

        assert re.search(r"width\s*:\s*100%", player_block), (
            "Expected '.player' block to include 'width: 100%' in "
            "WatchPageClient.module.css.\n"
            f"Actual .player block:\n{player_block.strip()}"
        )

    def test_static_player_has_overflow_hidden(self) -> None:
        """The .player block must set overflow:hidden so the rounded corners clip the video."""
        css = _read_file(_WATCH_PAGE_CSS)
        assert css, f"WatchPageClient.module.css not found at {_WATCH_PAGE_CSS}"

        player_block_match = re.search(r"\.player\s*\{([^}]*)\}", css, re.DOTALL)
        assert player_block_match, "No '.player { }' rule found in WatchPageClient.module.css."
        player_block = player_block_match.group(1)

        assert re.search(r"overflow\s*:\s*hidden", player_block), (
            "Expected '.player' block to include 'overflow: hidden' in "
            "WatchPageClient.module.css.\n"
            f"Actual .player block:\n{player_block.strip()}"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Live Playwright (skipped when app unreachable)
    # ──────────────────────────────────────────────────────────────────────────

    def test_live_player_container_computed_aspect_ratio(
        self, config: WebConfig, playwright_browser: Browser
    ) -> None:
        """The computed aspect-ratio of the player wrapper is ~16/9 on the live page.

        We measure the width and height of the container element (matching the
        CSS module .player class via [class*='player']) and verify their ratio
        is between 1.70 and 1.80, which covers 16/9 ≈ 1.7778.
        """
        if not _is_app_reachable(config.base_url):
            pytest.skip(f"Deployed app unreachable ({config.base_url})")

        video_id = _resolve_video_id()
        page = playwright_browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            watch = WatchPage(page)
            watch.navigate_to_video(config.base_url, video_id)

            # Wait for the player wrapper to appear in the DOM
            watch.wait_for_player_wrapper(timeout=_PAGE_LOAD_TIMEOUT)

            # Read bounding rect and computed styles of the player wrapper
            metrics = watch.get_player_metrics()

            assert metrics is not None, (
                f"No element matching [class*='player'] found on {config.base_url}/v/{video_id}. "
                "The player wrapper may not be rendered."
            )

            width = metrics["width"]
            height = metrics["height"]
            aspect_ratio_prop = metrics.get("aspectRatioProp", "")
            padding_top = metrics.get("paddingTop", "")

            # Check computed aspect-ratio property explicitly
            has_correct_aspect_ratio_prop = (
                aspect_ratio_prop and "16" in aspect_ratio_prop and "9" in aspect_ratio_prop
            )

            # Fallback: check the width/height ratio geometrically
            if width > 0 and height > 0:
                ratio = width / height
                has_correct_geometric_ratio = 1.70 <= ratio <= 1.80
            else:
                has_correct_geometric_ratio = False

            # Fallback: padding-top 56.25% technique
            has_padding_top_fallback = "56.25%" in (padding_top or "")

            assert has_correct_aspect_ratio_prop or has_correct_geometric_ratio or has_padding_top_fallback, (
                f"Player container does not have a 16:9 aspect ratio on "
                f"{config.base_url}/v/{video_id}.\n"
                f"  Computed aspect-ratio property: {aspect_ratio_prop!r}\n"
                f"  Bounding box — width: {width}px, height: {height}px, "
                f"ratio: {width/height:.4f} (expected ~1.7778)\n"
                f"  padding-top: {padding_top!r}\n"
                "Without a fixed aspect ratio, Video.js mount causes a layout shift "
                "as the player container initially has zero height."
            )
        finally:
            page.close()

    def test_live_player_container_stable_height_during_mount(
        self, config: WebConfig, playwright_browser: Browser
    ) -> None:
        """The player container height does not change after Video.js mounts.

        Measures the player wrapper height immediately after DOM load (before
        Video.js has had time to inject its elements) and again after a brief
        delay for async player init. The heights must be identical — confirming
        the CSS aspect-ratio holds the space before and during mount.

        If no ready video is available (e.g., in a bare CI environment), the
        test verifies the initial non-zero height only and skips the post-mount
        comparison with an explanatory message.
        """
        if not _is_app_reachable(config.base_url):
            pytest.skip(f"Deployed app unreachable ({config.base_url})")

        video_id = _resolve_video_id()
        page = playwright_browser.new_page(viewport={"width": 1280, "height": 800})
        try:
            # Navigate and capture the initial player height immediately
            watch = WatchPage(page)
            watch.navigate_to_video(config.base_url, video_id)
            watch.wait_for_player_wrapper(timeout=_PAGE_LOAD_TIMEOUT)

            height_before = watch.get_player_height()
            assert height_before is not None, (
                "Player wrapper not found after DOM content loaded."
            )
            assert height_before > 0, (
                f"Player container height is {height_before}px immediately after DOM load. "
                "Expected a non-zero height from the aspect-ratio CSS before Video.js mounts. "
                "This indicates the aspect-ratio fix is not applied."
            )

            # Allow Video.js async init to complete
            watch.wait_for_player_container(timeout=_PLAYER_INIT_TIMEOUT)

            height_after = watch.get_player_height()

            if height_after is None:
                # The player wrapper was removed — this happens when the SPA
                # navigates to a "video not found" state (e.g., fallback video ID).
                # The critical assertion (height_before > 0) already passed,
                # confirming the aspect-ratio fix establishes height pre-mount.
                pytest.skip(
                    f"Player wrapper removed after init (video_id={video_id!r} likely not found). "
                    "Pre-mount height check passed. Set TEST_VIDEO_ID to a ready video ID "
                    "to validate post-mount height stability."
                )

            delta = abs(height_after - height_before)
            assert delta < 5, (
                f"Player container height changed by {delta:.1f}px during Video.js mount "
                f"(before: {height_before:.1f}px, after: {height_after:.1f}px).\n"
                "A height change > 5px indicates a CLS layout shift. "
                "The CSS aspect-ratio should hold the container dimensions stable "
                "before and after the player initialises."
            )
        finally:
            page.close()
