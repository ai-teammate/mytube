"""
MYTUBE-514: Video metadata and tags — meta line styling and pill components

Objective
---------
Verify the styling of the metadata line (category, views, date) and ensure tags
are rendered as pills matching the VideoCard component style.

Steps
-----
1. Navigate to the video watch page.
2. Inspect the .meta-line containing category, view count, and upload date.
3. Observe the rendering of video tags.

Expected Result
---------------
The meta line uses font-size: 14px and color: var(--text-secondary).
Tags are rendered as pills matching the VideoCard component style.

Architecture
------------
Dual-mode:

1. **Static Mode** (primary / fallback): Reads ``WatchPageClient.module.css``
   and ``VideoCard.module.css`` directly from the web source tree and asserts
   that the correct CSS tokens are present.  This works in every environment
   and requires no live server.

2. **Live Mode** (when APP_URL / WEB_BASE_URL is set): Uses Playwright to
   navigate to the deployed watch page, discover a real video from the
   homepage, inspect computed styles of the meta-line element, and confirm
   tag pills are rendered with rounded styling.

Run from repo root:
    pytest testing/tests/MYTUBE-514/test_mytube_514.py -v
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WEB_SRC = _REPO_ROOT / "web" / "src"
_WATCH_CSS = _WEB_SRC / "app" / "v" / "[id]" / "WatchPageClient.module.css"
_VIDEO_CARD_CSS = _WEB_SRC / "components" / "VideoCard.module.css"

# ---------------------------------------------------------------------------
# Expected values (from design specification)
# ---------------------------------------------------------------------------

_EXPECTED_META_FONT_SIZE = "14px"
_EXPECTED_META_COLOR_TOKEN = "var(--text-secondary)"
_EXPECTED_TAG_BG_TOKEN = "var(--accent-pill-bg)"
_EXPECTED_TAG_COLOR_TOKEN = "var(--text-pill)"
_EXPECTED_TAG_BORDER_RADIUS = "999px"

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


def _read_css(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_rule_block(css: str, selector: str) -> str:
    """Return the CSS declarations block for a given class selector."""
    pattern = re.compile(
        r"\." + re.escape(selector) + r"\s*\{([^}]*)\}", re.DOTALL
    )
    match = pattern.search(css)
    return match.group(1) if match else ""


def _parse_declarations(block: str) -> dict[str, str]:
    """Parse CSS declaration block into {property: value} dict."""
    result: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip().rstrip(";")
        if ":" in line:
            prop, _, val = line.partition(":")
            result[prop.strip()] = val.strip()
    return result


# ---------------------------------------------------------------------------
# Static analysis tests
# ---------------------------------------------------------------------------


class TestMetaLineStylingStatic:
    """Verify .metaLine styling in WatchPageClient.module.css (source analysis)."""

    def test_watch_css_file_exists(self):
        assert _WATCH_CSS.exists(), (
            f"WatchPageClient.module.css not found at {_WATCH_CSS}"
        )

    def test_meta_line_font_size(self):
        css = _read_css(_WATCH_CSS)
        block = _extract_rule_block(css, "metaLine")
        assert block, "'.metaLine' rule block not found in WatchPageClient.module.css"
        decls = _parse_declarations(block)
        actual = decls.get("font-size", "")
        assert actual == _EXPECTED_META_FONT_SIZE, (
            f"Expected .metaLine font-size: {_EXPECTED_META_FONT_SIZE!r}, "
            f"got: {actual!r}"
        )

    def test_meta_line_color_token(self):
        css = _read_css(_WATCH_CSS)
        block = _extract_rule_block(css, "metaLine")
        assert block, "'.metaLine' rule block not found in WatchPageClient.module.css"
        decls = _parse_declarations(block)
        actual = decls.get("color", "")
        assert actual == _EXPECTED_META_COLOR_TOKEN, (
            f"Expected .metaLine color: {_EXPECTED_META_COLOR_TOKEN!r}, "
            f"got: {actual!r}"
        )

    def test_tag_pill_border_radius(self):
        css = _read_css(_WATCH_CSS)
        block = _extract_rule_block(css, "tagPill")
        assert block, "'.tagPill' rule block not found in WatchPageClient.module.css"
        decls = _parse_declarations(block)
        actual = decls.get("border-radius", "")
        assert actual == _EXPECTED_TAG_BORDER_RADIUS, (
            f"Expected .tagPill border-radius: {_EXPECTED_TAG_BORDER_RADIUS!r}, "
            f"got: {actual!r}"
        )

    def test_tag_pill_background_token(self):
        css = _read_css(_WATCH_CSS)
        block = _extract_rule_block(css, "tagPill")
        assert block, "'.tagPill' rule block not found in WatchPageClient.module.css"
        decls = _parse_declarations(block)
        actual = decls.get("background", "")
        assert actual == _EXPECTED_TAG_BG_TOKEN, (
            f"Expected .tagPill background: {_EXPECTED_TAG_BG_TOKEN!r}, "
            f"got: {actual!r}"
        )

    def test_tag_pill_color_token(self):
        css = _read_css(_WATCH_CSS)
        block = _extract_rule_block(css, "tagPill")
        assert block, "'.tagPill' rule block not found in WatchPageClient.module.css"
        decls = _parse_declarations(block)
        actual = decls.get("color", "")
        assert actual == _EXPECTED_TAG_COLOR_TOKEN, (
            f"Expected .tagPill color: {_EXPECTED_TAG_COLOR_TOKEN!r}, "
            f"got: {actual!r}"
        )


class TestTagPillMatchesVideoCard:
    """Verify .tagPill styling in WatchPageClient matches VideoCard component."""

    def test_video_card_css_file_exists(self):
        assert _VIDEO_CARD_CSS.exists(), (
            f"VideoCard.module.css not found at {_VIDEO_CARD_CSS}"
        )

    def test_watch_page_tag_pill_matches_video_card_pill_background(self):
        watch_css = _read_css(_WATCH_CSS)
        vc_css = _read_css(_VIDEO_CARD_CSS)

        watch_block = _extract_rule_block(watch_css, "tagPill")
        vc_block = _extract_rule_block(vc_css, "tagPill")

        assert watch_block, "'.tagPill' not found in WatchPageClient.module.css"
        assert vc_block, "'.tagPill' not found in VideoCard.module.css"

        watch_decls = _parse_declarations(watch_block)
        vc_decls = _parse_declarations(vc_block)

        watch_bg = watch_decls.get("background", "")
        vc_bg = vc_decls.get("background", "")

        assert watch_bg == vc_bg, (
            f"tagPill background mismatch: WatchPage={watch_bg!r}, "
            f"VideoCard={vc_bg!r}"
        )

    def test_watch_page_tag_pill_matches_video_card_pill_color(self):
        watch_css = _read_css(_WATCH_CSS)
        vc_css = _read_css(_VIDEO_CARD_CSS)

        watch_block = _extract_rule_block(watch_css, "tagPill")
        vc_block = _extract_rule_block(vc_css, "tagPill")

        watch_decls = _parse_declarations(watch_block)
        vc_decls = _parse_declarations(vc_block)

        watch_color = watch_decls.get("color", "")
        vc_color = vc_decls.get("color", "")

        assert watch_color == vc_color, (
            f"tagPill color mismatch: WatchPage={watch_color!r}, "
            f"VideoCard={vc_color!r}"
        )

    def test_watch_page_tag_pill_matches_video_card_pill_border_radius(self):
        watch_css = _read_css(_WATCH_CSS)
        vc_css = _read_css(_VIDEO_CARD_CSS)

        watch_block = _extract_rule_block(watch_css, "tagPill")
        vc_block = _extract_rule_block(vc_css, "tagPill")

        watch_decls = _parse_declarations(watch_block)
        vc_decls = _parse_declarations(vc_block)

        watch_radius = watch_decls.get("border-radius", "")
        vc_radius = vc_decls.get("border-radius", "")

        assert watch_radius == vc_radius, (
            f"tagPill border-radius mismatch: WatchPage={watch_radius!r}, "
            f"VideoCard={vc_radius!r}"
        )


# ---------------------------------------------------------------------------
# Live mode tests
# ---------------------------------------------------------------------------


def _discover_watch_url(config: WebConfig) -> str | None:
    """Try to find a usable watch page URL from the homepage video cards."""
    import urllib.request
    import urllib.error
    import json

    api_base = config.api_base_url
    try:
        url = f"{api_base}/api/users/tester"
        with urllib.request.urlopen(url, timeout=8) as resp:
            data = json.loads(resp.read().decode())
        for v in data.get("videos", []):
            if v.get("status") == "ready" or "id" in v:
                return f"{config.base_url}/v/{v['id']}/"
    except Exception:
        pass
    return None


class TestMetaLineStylingLive:
    """Live Playwright tests — skipped when no APP_URL/WEB_BASE_URL is set."""

    @pytest.fixture(scope="class")
    def watch_url(self) -> str:
        if not _should_use_live_mode():
            pytest.skip("Live mode disabled: APP_URL/WEB_BASE_URL not set.")
        config = WebConfig()
        url = _discover_watch_url(config)
        if not url:
            pytest.skip("Could not discover a live video URL from the API.")
        return url

    @pytest.fixture(scope="class")
    def loaded_page(self, watch_url: str):
        config = WebConfig()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
            page = browser.new_page(viewport={"width": 1280, "height": 720})
            page.goto(watch_url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
            yield page
            browser.close()

    def test_meta_line_font_size_live(self, loaded_page: Page):
        """The meta-line element must have computed font-size of 14px."""
        # Find the meta-line element (div containing views/date spans)
        meta_el = loaded_page.locator("[class*='metaLine']").first
        if meta_el.count() == 0:
            # Fallback: find by content (div containing " views" and "·")
            meta_el = loaded_page.locator("div").filter(
                has_text=re.compile(r"\d+ views")
            ).first
        assert meta_el.count() > 0, "meta-line element not found on watch page"
        font_size = loaded_page.evaluate(
            "(el) => window.getComputedStyle(el).fontSize", meta_el.element_handle()
        )
        assert font_size == "14px", (
            f"Expected meta-line font-size: 14px, got: {font_size!r}"
        )

    def test_tag_pills_rendered_live(self, loaded_page: Page):
        """Tag pill elements must be present and have rounded border styling."""
        pill_locator = loaded_page.locator("[class*='tagPill']")
        if pill_locator.count() == 0:
            pytest.skip("No tag pills found on this watch page (video may have no tags).")
        first_pill = pill_locator.first
        border_radius = loaded_page.evaluate(
            "(el) => window.getComputedStyle(el).borderRadius",
            first_pill.element_handle(),
        )
        # 999px computes to a very large value but Playwright may simplify it
        assert border_radius not in ("", "0px"), (
            f"Expected tag pill to have rounded border-radius, got: {border_radius!r}"
        )
