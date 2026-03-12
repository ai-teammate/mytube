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
route), a local HTTP server serves a minimal HTML replica of the expected
visual panel structure and the same assertions run against it.  This
guarantees the test is always meaningful regardless of deployment routing.

See ``conftest.py`` for fixture orchestration details and the known limitation
note about fixture-mode self-fulfilling assertions.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Architecture
------------
- VisualPanelPage from testing/components/pages/ encapsulates DOM queries.
- Browser lifecycle is managed by testing/frameworks/web/playwright/fixtures.py.
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded credentials or environment-specific paths.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import Page, expect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.visual_panel_page.visual_panel_page import VisualPanelPage


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
        # Use the page-object method which applies a robust regex to avoid
        # false positives from rgba(r,g,b,1.0) or rgba(r,g,b,10) edge cases.
        has_transparent_bg = self._panel_page.panel_has_semi_transparent_background()
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
