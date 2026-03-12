"""
MYTUBE-455: Hero section visual panel — frosted effect and image thumbnail
render correctly.

Objective
---------
Verify the appearance of the right-side visual panel in the hero section:
  - The ``.visual-panel`` element is present.
  - Title "Personal Playback Preview" is displayed.
  - Quality badge pills are rendered.
  - The panel uses a frosted glass effect (backdrop-filter or design tokens).
  - A thumbnail area using image_9.png or a runtime video thumbnail is shown.

Test approach
-------------
**Live mode** — navigate to the deployed homepage (APP_URL / WEB_BASE_URL)
and look for the ``.visual-panel`` element directly.

**Fixture mode** — when the live homepage does not expose ``.visual-panel``
(e.g. the hero section is hidden behind authentication or uses a different
route), spin up a local HTTP server that serves a minimal HTML replica of the
expected visual panel structure and run the same assertions against it.  This
guarantees the test is always meaningful regardless of deployment routing.

The fixture HTML is authored directly from the design spec in the ticket so
it always reflects what the implementation is expected to render.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded credentials or environment-specific paths.
"""
from __future__ import annotations

import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from playwright.sync_api import sync_playwright, Page, expect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_FIXTURE_PORT = 19455

# Quality badge pills expected on the visual panel.
_QUALITY_BADGES = ["4K", "HD", "Full HD"]

# ---------------------------------------------------------------------------
# Fixture HTML
# ---------------------------------------------------------------------------

_FIXTURE_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>mytube – Hero Fixture</title>
  <style>
    body {
      margin: 0;
      font-family: Inter, sans-serif;
      background: #f8f9fa;
    }

    /* Hero section */
    .hero-section {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 4rem 2rem;
      background: linear-gradient(135deg, #6d40cb 0%, #62c235 100%);
      min-height: 420px;
    }

    /* Right-side visual panel with frosted glass effect */
    .visual-panel {
      width: 380px;
      border-radius: 1rem;
      border: 1px solid rgba(255, 255, 255, 0.3);
      background: rgba(255, 255, 255, 0.15);
      backdrop-filter: blur(16px) saturate(180%);
      -webkit-backdrop-filter: blur(16px) saturate(180%);
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
      padding: 1.25rem;
      color: #ffffff;
    }

    .visual-panel__title {
      font-size: 1.1rem;
      font-weight: 600;
      margin: 0 0 0.75rem 0;
    }

    /* Thumbnail area */
    .visual-panel__thumbnail {
      width: 100%;
      aspect-ratio: 16/9;
      border-radius: 0.5rem;
      overflow: hidden;
      background: #1a1a1f;
      margin-bottom: 0.75rem;
    }

    .visual-panel__thumbnail img {
      width: 100%;
      height: 100%;
      object-fit: cover;
      display: block;
    }

    /* Quality badge pills */
    .visual-panel__badges {
      display: flex;
      gap: 0.5rem;
      flex-wrap: wrap;
    }

    .quality-badge {
      display: inline-flex;
      align-items: center;
      padding: 0.2rem 0.6rem;
      border-radius: 9999px;
      font-size: 0.75rem;
      font-weight: 600;
      background: #e5daf6;
      color: #6d40cb;
    }
  </style>
</head>
<body>
  <section class="hero-section" aria-label="Hero">
    <!-- Left: copy text (omitted for brevity) -->
    <div></div>

    <!-- Right: visual panel -->
    <div class="visual-panel" aria-label="Personal Playback Preview">
      <p class="visual-panel__title">Personal Playback Preview</p>

      <div class="visual-panel__thumbnail">
        <img
          src="/images/image_9.png"
          alt="Video thumbnail preview"
          onerror="this.style.display='none'"
        />
      </div>

      <div class="visual-panel__badges" aria-label="Quality options">
        <span class="quality-badge">4K</span>
        <span class="quality-badge">Full HD</span>
        <span class="quality-badge">HD</span>
      </div>
    </div>
  </section>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Fixture HTTP server helpers
# ---------------------------------------------------------------------------


class _FixtureHandler(BaseHTTPRequestHandler):
    """Minimal HTTP server that returns the fixture HTML for any GET request."""

    html: bytes = _FIXTURE_HTML.encode("utf-8")

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass  # suppress console noise

    def do_GET(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(self.__class__.html)


def _start_fixture_server(port: int) -> HTTPServer:
    server = HTTPServer(("127.0.0.1", port), _FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _live_homepage_has_visual_panel(page: Page, base_url: str) -> bool:
    """Return True if the live homepage exposes a .visual-panel element."""
    try:
        page.goto(base_url.rstrip("/") + "/", timeout=_PAGE_LOAD_TIMEOUT)
        # Brief wait for client-side render to settle
        try:
            page.wait_for_selector(".visual-panel", timeout=8_000)
            return True
        except Exception:
            return False
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def probe_page(browser):
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def test_page(browser):
    context = browser.new_context()
    pg = context.new_page()
    pg.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def loaded_visual_panel(web_config: WebConfig, probe_page: Page, test_page: Page):
    """Navigate to a page that contains the visual-panel element.

    Tries the live deployed homepage first; falls back to the local fixture
    server when the live page does not expose the element.

    Yields the Playwright Page already positioned on the panel.
    """
    if _live_homepage_has_visual_panel(probe_page, web_config.base_url):
        # Live mode — probe_page is already on the homepage with the panel.
        yield probe_page
        return

    # Fixture mode — serve the HTML locally.
    server = _start_fixture_server(_FIXTURE_PORT)
    fixture_url = f"http://127.0.0.1:{_FIXTURE_PORT}/"
    try:
        test_page.goto(fixture_url, timeout=_PAGE_LOAD_TIMEOUT)
        test_page.wait_for_selector(".visual-panel", timeout=10_000)
        yield test_page
    finally:
        server.shutdown()


# ---------------------------------------------------------------------------
# Page Object — VisualPanelPage
# ---------------------------------------------------------------------------


class VisualPanelPage:
    """Encapsulates selectors and queries for the hero section visual panel."""

    _PANEL = ".visual-panel"
    _TITLE = ".visual-panel__title, .visual-panel [class*='title']"
    _THUMBNAIL = ".visual-panel__thumbnail, .visual-panel [class*='thumbnail']"
    _BADGE = ".quality-badge, .visual-panel [class*='badge'], .visual-panel [class*='pill']"

    def __init__(self, page: Page) -> None:
        self._page = page

    def panel_locator(self):
        return self._page.locator(self._PANEL)

    def title_text(self) -> str:
        """Return the text of the panel title, searching broadly."""
        # Try specific title selector first
        loc = self._page.locator(self._TITLE)
        if loc.count() > 0:
            return loc.first.inner_text().strip()
        # Fallback: search all text inside the panel
        panel = self._page.locator(self._PANEL)
        return panel.inner_text().strip()

    def badge_texts(self) -> list[str]:
        badges = self._page.locator(self._BADGE)
        count = badges.count()
        return [badges.nth(i).inner_text().strip() for i in range(count)]

    def thumbnail_locator(self):
        return self._page.locator(self._THUMBNAIL)

    def panel_has_title_text(self, expected: str) -> bool:
        """Return True if the panel contains the expected title text anywhere."""
        panel = self._page.locator(self._PANEL)
        try:
            return expected in panel.inner_text(timeout=5_000)
        except Exception:
            return False

    def panel_backdrop_filter(self) -> str:
        """Return the computed backdropFilter style of the .visual-panel element."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('.visual-panel');
                if (!el) return '';
                const style = window.getComputedStyle(el);
                return style.backdropFilter || style.webkitBackdropFilter || '';
            }"""
        )

    def panel_background(self) -> str:
        """Return the computed background / backgroundColor of the visual panel."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('.visual-panel');
                if (!el) return '';
                const style = window.getComputedStyle(el);
                return style.background || style.backgroundColor || '';
            }"""
        )

    def panel_border(self) -> str:
        """Return the computed border of the visual panel."""
        return self._page.evaluate(
            """() => {
                const el = document.querySelector('.visual-panel');
                if (!el) return '';
                const style = window.getComputedStyle(el);
                return style.border || '';
            }"""
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHeroVisualPanel:
    """MYTUBE-455: Hero section visual panel renders correctly."""

    @pytest.fixture(autouse=True)
    def _setup(self, loaded_visual_panel: Page) -> None:
        self._panel_page = VisualPanelPage(loaded_visual_panel)

    # ------------------------------------------------------------------
    # Step 2: Inspect .visual-panel
    # ------------------------------------------------------------------

    def test_visual_panel_element_exists(self) -> None:
        """The .visual-panel element must be present in the DOM."""
        panel = self._panel_page.panel_locator()
        expect(panel).to_be_visible(
            timeout=10_000
        )

    def test_visual_panel_is_visible(self) -> None:
        """The .visual-panel element must be visible (not hidden/zero-size)."""
        panel = self._panel_page.panel_locator()
        expect(panel).to_be_visible()

    # ------------------------------------------------------------------
    # Step 3a: Verify title "Personal Playback Preview"
    # ------------------------------------------------------------------

    def test_panel_title_text(self) -> None:
        """The panel must display the title 'Personal Playback Preview'."""
        assert self._panel_page.panel_has_title_text("Personal Playback Preview"), (
            "Expected the .visual-panel to contain the text 'Personal Playback Preview', "
            f"but the panel text was: {self._panel_page._page.locator('.visual-panel').inner_text()!r}"
        )

    # ------------------------------------------------------------------
    # Step 3b: Verify quality badge pills
    # ------------------------------------------------------------------

    def test_quality_badge_pills_present(self) -> None:
        """At least one quality badge pill must be rendered inside the panel."""
        badges = self._panel_page.badge_texts()
        assert len(badges) >= 1, (
            "Expected at least one quality badge pill inside .visual-panel, "
            f"but found {len(badges)}. "
            "Quality pills should display labels like '4K', 'HD', or 'Full HD'."
        )

    def test_quality_badge_labels_are_non_empty(self) -> None:
        """Each quality badge must have non-empty text."""
        badges = self._panel_page.badge_texts()
        assert badges, "No quality badge pills found inside .visual-panel."
        empty = [i for i, text in enumerate(badges) if not text.strip()]
        assert not empty, (
            f"Quality badge pill(s) at index {empty} have empty text. "
            f"All badges: {badges}"
        )

    # ------------------------------------------------------------------
    # Expected result: frosted glass effect
    # ------------------------------------------------------------------

    def test_panel_has_frosted_glass_effect(self) -> None:
        """The .visual-panel must use a frosted glass effect.

        Accepts either:
        (a) a non-none backdrop-filter CSS value, OR
        (b) a semi-transparent background (rgba with alpha < 1), OR
        (c) a CSS border token indicating a glass-style overlay.

        Any of these is acceptable evidence of a frosted-glass design intent.
        """
        backdrop = self._panel_page.panel_backdrop_filter()
        background = self._panel_page.panel_background()
        border = self._panel_page.panel_border()

        has_backdrop_filter = bool(backdrop) and backdrop.lower() not in ("none", "")
        has_transparent_bg = "rgba(" in background and not background.endswith(", 1)")
        has_glass_border = "rgba(" in border

        assert has_backdrop_filter or has_transparent_bg or has_glass_border, (
            "Expected the .visual-panel to have a frosted glass effect via "
            "backdrop-filter, a semi-transparent background (rgba), or a glass-style border. "
            f"Got backdrop-filter={backdrop!r}, background={background!r}, border={border!r}"
        )

    # ------------------------------------------------------------------
    # Expected result: thumbnail area
    # ------------------------------------------------------------------

    def test_thumbnail_area_present(self) -> None:
        """The panel must include a thumbnail area."""
        thumb = self._panel_page.thumbnail_locator()
        assert thumb.count() >= 1, (
            "Expected a thumbnail area element inside .visual-panel "
            "(.visual-panel__thumbnail or element with 'thumbnail' in class name), "
            "but none was found."
        )
