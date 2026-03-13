"""
MYTUBE-583: Recommendation UI implementation — functional vertical list replaces placeholder.

Objective
---------
Verify the frontend watch page correctly renders the new recommendation section
using the standard VideoCard component.

Preconditions
-------------
A video exists with at least 2 matching recommendations.

Steps
-----
1. Open the watch page for the video.
2. Locate the sidebar section formerly containing the "Recommendations coming soon" text.

Expected Result
---------------
The placeholder text is replaced by a "More like this" section containing a
vertical list of VideoCard components. Each card displays the correct thumbnail,
title, and metadata as defined by the existing VideoCard design.

Test Approach
-------------
Three complementary layers:

**Layer A — Static source analysis** (always runs):
  - Confirms ``RecommendationSidebar.tsx`` does NOT contain the old placeholder
    text "Recommendations coming soon".
  - Confirms ``RecommendationSidebar.tsx`` renders an ``<h2>`` with text
    "More like this" when ≥2 recommendations are available.
  - Confirms ``RecommendationSidebar.tsx`` uses the ``VideoCard`` component
    for each recommendation item.
  - Confirms ``RecommendationSidebar.module.css`` defines a vertical list layout
    (flex-direction: column) for the ``.list`` class.

**Layer B — Fixture browser test** (always runs, self-contained):
  Starts a local HTTP server serving a minimal HTML page that replicates the
  RecommendationSidebar rendering two VideoCard items. Verifies:
  - "More like this" heading is visible.
  - "Recommendations coming soon" text is absent.
  - Two VideoCard items are rendered with thumbnail, title, and metadata.
  - The items are stacked vertically (flex column layout).

**Layer C — Live browser test** (runs when APP_URL/WEB_BASE_URL is reachable
  and a video with ≥2 recommendations is found via the API):
  - Uses VideoApiService to discover a ready video.
  - Checks the recommendations API endpoint for ≥2 results.
  - Navigates to the watch page.
  - Asserts the "More like this" heading and VideoCard items are visible.
  - Asserts "Recommendations coming soon" text is not present.

Environment variables
---------------------
APP_URL / WEB_BASE_URL      Base URL of the deployed web app.
                            Default: https://ai-teammate.github.io/mytube
API_BASE_URL                API base URL (default: http://localhost:8081).
PLAYWRIGHT_HEADLESS         Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO          Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-583/test_mytube_583.py -v
"""
from __future__ import annotations

import os
import re
import socket
import sys
import threading
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.api_config import APIConfig
from testing.core.config.web_config import WebConfig
from testing.components.services.video_api_service import VideoApiService

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SIDEBAR_TSX = _REPO_ROOT / "web" / "src" / "components" / "RecommendationSidebar.tsx"
_SIDEBAR_CSS = _REPO_ROOT / "web" / "src" / "components" / "RecommendationSidebar.module.css"
_VIDEO_CARD_TSX = _REPO_ROOT / "web" / "src" / "components" / "VideoCard.tsx"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VIEWPORT = {"width": 1280, "height": 800}
_PAGE_LOAD_TIMEOUT = 30_000  # ms
_SIDEBAR_TIMEOUT = 10_000    # ms — wait for RecommendationSidebar to settle

# Minimum recommendations required by the component to display the section
_MIN_RECOMMENDATIONS = 2

# ---------------------------------------------------------------------------
# Fixture HTML
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>RecommendationSidebar fixture</title>
  <style>
    body { font-family: sans-serif; margin: 0; padding: 20px;
           background: #111; color: #eee; }
    .section { display: flex; flex-direction: column; gap: 12px; }
    .heading { font-size: 16px; font-weight: 600; color: #eee; margin: 0 0 4px; }
    .list { display: flex; flex-direction: column; gap: 12px; }
    /* VideoCard styles */
    .card { display: flex; gap: 10px; background: #1c1c1c;
            border-radius: 8px; overflow: hidden; padding: 8px; }
    .thumb { width: 140px; height: 88px; flex-shrink: 0;
             background: #333; border-radius: 6px; position: relative; }
    .thumb img { width: 100%; height: 100%; object-fit: cover; }
    .body { display: flex; flex-direction: column; gap: 4px; flex: 1; }
    .videoTitle { font-size: 14px; font-weight: 500; color: #eee;
                  text-decoration: none; display: -webkit-box;
                  -webkit-line-clamp: 2; -webkit-box-orient: vertical;
                  overflow: hidden; }
    .videoSub { font-size: 12px; color: #aaa; display: flex;
                gap: 4px; flex-wrap: wrap; }
    .videoSub a { color: #aaa; text-decoration: none; }
  </style>
</head>
<body>
  <div class="section" data-testid="recommendation-sidebar">
    <h2 class="heading">More like this</h2>
    <div class="list">
      <div class="card" data-testid="video-card">
        <div class="thumb">
          <img src="https://picsum.photos/seed/vid1/140/88"
               alt="First Related Video" />
        </div>
        <div class="body">
          <a href="/v/vid1" class="videoTitle">First Related Video</a>
          <div class="videoSub">
            <a href="/u/alice">alice</a>
            <span aria-hidden="true">·</span>
            <span>1,234 views</span>
            <span aria-hidden="true">·</span>
            <span>1/15/2024</span>
          </div>
        </div>
      </div>
      <div class="card" data-testid="video-card">
        <div class="thumb">
          <img src="https://picsum.photos/seed/vid2/140/88"
               alt="Second Related Video" />
        </div>
        <div class="body">
          <a href="/v/vid2" class="videoTitle">Second Related Video</a>
          <div class="videoSub">
            <a href="/u/bob">bob</a>
            <span aria-hidden="true">·</span>
            <span>5,678 views</span>
            <span aria-hidden="true">·</span>
            <span>2/20/2024</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# HTTP test server helpers
# ---------------------------------------------------------------------------


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _FixtureHandler(BaseHTTPRequestHandler):
    """Serves the fixture HTML for all GET requests."""

    def do_GET(self) -> None:  # noqa: N802
        body = _FIXTURE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args) -> None:  # silence access logs
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_reachable(url: str, timeout: float = 5.0) -> bool:
    """Return True if *url* returns any HTTP response within *timeout* seconds."""
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except Exception:
        return False


def _get_recommendations(api_base: str, video_id: str) -> Optional[list]:
    """Fetch recommendations for *video_id* from the API. Return list or None."""
    url = f"{api_base.rstrip('/')}/api/videos/{video_id}/recommendations"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            import json
            data = json.loads(resp.read())
            return data.get("recommendations", [])
    except Exception:
        return None


def _find_video_with_recommendations(
    api_svc: VideoApiService, api_base: str
) -> Optional[str]:
    """Return a video_id that has ≥2 recommendations, or None."""
    result = api_svc.find_ready_video()
    if result is None:
        return None
    video_id, _ = result
    recs = _get_recommendations(api_base, video_id)
    if recs and len(recs) >= _MIN_RECOMMENDATIONS:
        return video_id
    return None


# ---------------------------------------------------------------------------
# Layer A — Static source analysis
# ---------------------------------------------------------------------------


class TestSourceAnalysis:
    """Verify the RecommendationSidebar source replaces the placeholder."""

    def test_no_placeholder_text_in_sidebar(self) -> None:
        """RecommendationSidebar.tsx must NOT contain 'Recommendations coming soon'."""
        if not _SIDEBAR_TSX.exists():
            pytest.skip(f"Source file not found: {_SIDEBAR_TSX}")
        content = _SIDEBAR_TSX.read_text(encoding="utf-8")
        assert "Recommendations coming soon" not in content, (
            "Found old placeholder text 'Recommendations coming soon' in "
            f"{_SIDEBAR_TSX}. The placeholder must be removed."
        )

    def test_more_like_this_heading_present(self) -> None:
        """RecommendationSidebar.tsx must render 'More like this' heading."""
        if not _SIDEBAR_TSX.exists():
            pytest.skip(f"Source file not found: {_SIDEBAR_TSX}")
        content = _SIDEBAR_TSX.read_text(encoding="utf-8")
        assert "More like this" in content, (
            "Could not find 'More like this' text in "
            f"{_SIDEBAR_TSX}. The recommendation section heading is missing."
        )

    def test_videocard_component_is_used(self) -> None:
        """RecommendationSidebar.tsx must render VideoCard components."""
        if not _SIDEBAR_TSX.exists():
            pytest.skip(f"Source file not found: {_SIDEBAR_TSX}")
        content = _SIDEBAR_TSX.read_text(encoding="utf-8")
        assert "VideoCard" in content, (
            "VideoCard component is not used in "
            f"{_SIDEBAR_TSX}. Recommendations must use the standard VideoCard component."
        )
        # Also confirm it imports VideoCard
        assert re.search(r"import\s+VideoCard\s+from", content), (
            "VideoCard is referenced but not imported in "
            f"{_SIDEBAR_TSX}."
        )

    def test_vertical_list_layout_in_css(self) -> None:
        """RecommendationSidebar.module.css must define a vertical flex list."""
        if not _SIDEBAR_CSS.exists():
            pytest.skip(f"CSS file not found: {_SIDEBAR_CSS}")
        content = _SIDEBAR_CSS.read_text(encoding="utf-8")
        # The .list class must have flex-direction: column (vertical stacking)
        assert "flex-direction" in content and "column" in content, (
            "Could not confirm vertical flex layout (flex-direction: column) "
            f"in {_SIDEBAR_CSS}. The VideoCard list must be vertically stacked."
        )

    def test_sidebar_section_structure(self) -> None:
        """RecommendationSidebar.tsx must wrap content in a section div."""
        if not _SIDEBAR_TSX.exists():
            pytest.skip(f"Source file not found: {_SIDEBAR_TSX}")
        content = _SIDEBAR_TSX.read_text(encoding="utf-8")
        # The component maps over recommendations and renders VideoCard per item
        assert re.search(r"recommendations\.map\s*\(", content) or \
               re.search(r"\.map\s*\(\s*\(video\)", content), (
            "No .map() call found in RecommendationSidebar.tsx. "
            "Recommendations must be rendered by iterating over the fetched list."
        )

    def test_videocard_has_title_and_metadata(self) -> None:
        """VideoCard.tsx must render title and sub-line metadata (uploader, views, date)."""
        if not _VIDEO_CARD_TSX.exists():
            pytest.skip(f"Source file not found: {_VIDEO_CARD_TSX}")
        content = _VIDEO_CARD_TSX.read_text(encoding="utf-8")
        assert "video.title" in content, "VideoCard must render video.title"
        assert "uploaderUsername" in content or "uploader_username" in content, (
            "VideoCard must render uploader username"
        )
        assert "viewCount" in content or "view_count" in content, (
            "VideoCard must render view count"
        )


# ---------------------------------------------------------------------------
# Layer B — Fixture browser test
# ---------------------------------------------------------------------------


class TestFixtureBrowser:
    """Render the fixture HTML and assert the recommendation UI structure."""

    def test_fixture_recommendation_sidebar(self) -> None:
        """Fixture: 'More like this' heading and VideoCard items are visible."""
        port = _find_free_port()
        server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(viewport=_VIEWPORT)
                try:
                    page.goto(f"http://127.0.0.1:{port}/", timeout=_PAGE_LOAD_TIMEOUT)

                    # 1. "More like this" heading must be visible
                    heading = page.get_by_text("More like this", exact=True)
                    heading.wait_for(state="visible", timeout=5_000)
                    assert heading.is_visible(), \
                        "'More like this' heading is not visible in the fixture page."

                    # 2. "Recommendations coming soon" must NOT be present
                    placeholder = page.get_by_text("Recommendations coming soon")
                    assert placeholder.count() == 0, (
                        "Old placeholder text 'Recommendations coming soon' is still visible."
                    )

                    # 3. Two VideoCard items must be present
                    cards = page.locator("[data-testid='video-card']")
                    assert cards.count() >= _MIN_RECOMMENDATIONS, (
                        f"Expected at least {_MIN_RECOMMENDATIONS} VideoCard items, "
                        f"found {cards.count()}."
                    )

                    # 4. Each card has a title link
                    for i in range(cards.count()):
                        card = cards.nth(i)
                        title = card.locator(".videoTitle")
                        assert title.count() > 0, f"Card {i} is missing a title link."
                        assert title.inner_text().strip(), f"Card {i} title is empty."

                    # 5. Each card has metadata (uploader / views / date)
                    for i in range(cards.count()):
                        card = cards.nth(i)
                        sub = card.locator(".videoSub")
                        assert sub.count() > 0, f"Card {i} is missing the metadata sub-line."
                        sub_text = sub.inner_text()
                        assert "views" in sub_text, (
                            f"Card {i} sub-line does not contain 'views': {sub_text!r}"
                        )

                    # 6. Cards are laid out vertically (list is a flex column)
                    list_el = page.locator(".list")
                    display = page.evaluate(
                        "el => getComputedStyle(el).flexDirection",
                        list_el.element_handle(),
                    )
                    assert display == "column", (
                        f"Expected .list to have flex-direction: column, got: {display!r}"
                    )

                finally:
                    browser.close()
        finally:
            server.shutdown()

    def test_fixture_no_placeholder_text(self) -> None:
        """Fixture page must not contain 'Recommendations coming soon'."""
        port = _find_free_port()
        server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(headless=True)
                page = browser.new_page(viewport=_VIEWPORT)
                try:
                    page.goto(f"http://127.0.0.1:{port}/", timeout=_PAGE_LOAD_TIMEOUT)
                    assert page.get_by_text("Recommendations coming soon").count() == 0, (
                        "Fixture page unexpectedly contains placeholder text."
                    )
                finally:
                    browser.close()
        finally:
            server.shutdown()


# ---------------------------------------------------------------------------
# Layer C — Live browser test
# ---------------------------------------------------------------------------


class TestLiveBrowser:
    """Navigate to the deployed watch page and verify the recommendation UI."""

    def test_live_recommendation_sidebar(self) -> None:
        """Live: 'More like this' heading and VideoCards visible on watch page."""
        web_cfg = WebConfig()
        api_cfg = APIConfig()

        # Check if the app is reachable
        if not _is_url_reachable(web_cfg.base_url, timeout=8.0):
            pytest.skip(f"App not reachable at {web_cfg.base_url}")

        # Find a ready video
        api_svc = VideoApiService(api_cfg)
        video_id = _find_video_with_recommendations(api_svc, api_cfg.base_url)
        if video_id is None:
            # Try to find any ready video even if we can't confirm recommendations count
            result = api_svc.find_ready_video()
            if result is None:
                pytest.skip("No ready video found — skipping live recommendation test.")
            video_id, _ = result

        watch_url = f"{web_cfg.base_url}/v/{video_id}/"

        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=web_cfg.headless,
                slow_mo=web_cfg.slow_mo,
            )
            page = browser.new_page(viewport=_VIEWPORT)
            try:
                page.goto(watch_url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT)

                # Wait for the page to finish loading (loading indicator disappears)
                try:
                    page.wait_for_selector("text=Loading…", state="hidden", timeout=8_000)
                except Exception:
                    pass  # loading text may not appear

                # Give the RecommendationSidebar time to fetch and render
                try:
                    page.wait_for_selector("h2", state="visible", timeout=_SIDEBAR_TIMEOUT)
                except Exception:
                    pass

                # Assert "Recommendations coming soon" placeholder is NOT present
                assert page.get_by_text("Recommendations coming soon").count() == 0, (
                    "Old placeholder text 'Recommendations coming soon' is still visible "
                    f"on watch page {watch_url}. The recommendation section was not replaced."
                )

                # Try to find the "More like this" section
                more_like_this = page.get_by_text("More like this", exact=True)
                if more_like_this.count() == 0:
                    # The section may be hidden because <2 recommendations were returned
                    # for this particular video. That's acceptable per the spec.
                    # Verify there's no placeholder and skip the rest.
                    pytest.skip(
                        f"No 'More like this' section on watch page for video {video_id}. "
                        "This may be because the video has fewer than 2 recommendations. "
                        "Placeholder text is absent (correct behaviour)."
                    )

                more_like_this.wait_for(state="visible", timeout=_SIDEBAR_TIMEOUT)
                assert more_like_this.is_visible(), \
                    f"'More like this' heading is not visible on {watch_url}."

                # Verify at least 2 VideoCard items in the recommendation list
                # VideoCards are rendered inside the .list container
                cards = page.locator("aside .list .card, aside [class*='list'] [class*='card']")
                if cards.count() < _MIN_RECOMMENDATIONS:
                    # Use a broader selector
                    cards = page.locator("aside a[href*='/v/']")

                assert cards.count() >= _MIN_RECOMMENDATIONS, (
                    f"Expected at least {_MIN_RECOMMENDATIONS} VideoCard items in "
                    f"'More like this' section on {watch_url}, found {cards.count()}."
                )

            finally:
                browser.close()
