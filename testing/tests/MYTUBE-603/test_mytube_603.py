"""
MYTUBE-603: Playlist page layout — hardcoded Tailwind classes replaced by design tokens

Objective
---------
Confirm that the Playlist page client (PlaylistPageClient.tsx) UI elements adapt
correctly to dark theme using the design token system. Specifically, verify that
the page does not display light-gray backgrounds (bg-gray-50) or borders
(border-gray-100). All layout elements must use appropriate CSS variables
(e.g., var(--bg-page), var(--border-primary)) ensuring a consistent dark theme
appearance.

Preconditions
-------------
Dark theme is active (body[data-theme="dark"]).

Steps
-----
1. Navigate to a specific Playlist page.
2. Observe the page background, container borders, and text labels.

Expected Result
---------------
The page does not display light-gray backgrounds (bg-gray-50) or borders
(border-gray-100). All layout elements use appropriate CSS variables
(e.g., var(--bg-page), var(--border-primary)) ensuring a consistent dark theme
appearance.

Test Strategy
-------------
Dual-mode approach:

**Static analysis** (always runs): Parses ``PlaylistPageClient.module.css`` to
verify:
  - The ``.page`` rule uses ``var(--bg-page)`` for background (not a hardcoded
    light-theme color like ``#f9fafb`` or bg-gray-50 equivalent).
  - The ``.title`` rule uses ``var(--text-primary)`` for color (not ``text-gray-900``
    equivalent like ``#111827``).
  - The ``.subtitle`` rule uses ``var(--text-secondary)`` (not ``#6b7280``).
  - Queue-related container rules use ``var(--bg-content)`` / ``var(--border-light)``.
  - No hardcoded light-theme hex color values from the Tailwind gray palette appear
    in layout rules.

**Fixture mode** (Playwright, always runs): Renders a self-contained HTML page
embedding the exact CSS from ``PlaylistPageClient.module.css`` and ``globals.css``
with ``data-theme="dark"`` set on the ``<body>`` element. Uses
``getComputedStyle(el)`` to assert the resolved background-color and color
match the expected dark-mode token values:
  - ``.page`` background → ``--bg-page`` = ``#0f0f11`` → ``rgb(15, 15, 17)``
  - ``.title`` color → ``--text-primary`` = ``#f0f0f0`` → ``rgb(240, 240, 240)``
  - ``.subtitle`` color → ``--text-secondary`` = ``#a0a0ab`` → ``rgb(160, 160, 171)``
  - ``.queueCard`` background → ``--bg-content`` = ``#1a1a1f`` → ``rgb(26, 26, 31)``

Architecture
------------
- PlaylistCSSModule from testing/components/pages/playlist_page/playlist_css_module.py
  for CSS static analysis.
- Playwright sync API with pytest module-scoped fixtures.
- HTML fixture mode uses page.set_content() with inline CSS -- no external deps.

Linked bugs
-----------
MYTUBE-593 (Done): Dashboard My Videos and Playlists look broken in dark theme.
  Fix: Replaced hardcoded Tailwind colour classes and inline hex values in
  _content.tsx and DashboardVideoCard.module.css (and PlaylistPageClient.tsx)
  with CSS design tokens. Status badges, modals, banners, tab bars, playlist
  tables, and queue panels now all adapt correctly to the active theme.
"""
from __future__ import annotations

import pathlib
import re
import sys
import os

import pytest
from playwright.sync_api import Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.playlist_page.playlist_css_module import PlaylistCSSModule

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_PLAYLIST_CSS = _REPO_ROOT / "web" / "src" / "app" / "pl" / "[id]" / "PlaylistPageClient.module.css"
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Expected resolved values (dark theme)
#   --bg-page:    #0f0f11  → rgb(15, 15, 17)
#   --bg-content: #1a1a1f  → rgb(26, 26, 31)
#   --text-primary:   #f0f0f0  → rgb(240, 240, 240)
#   --text-secondary: #a0a0ab  → rgb(160, 160, 171)
#   --border-light:   #333340  → rgb(51, 51, 64)
# ---------------------------------------------------------------------------

_EXPECTED_BG_PAGE_RGB = "rgb(15, 15, 17)"          # --bg-page  #0f0f11
_EXPECTED_BG_CONTENT_RGB = "rgb(26, 26, 31)"        # --bg-content #1a1a1f
_EXPECTED_TEXT_PRIMARY_RGB = "rgb(240, 240, 240)"   # --text-primary #f0f0f0
_EXPECTED_TEXT_SECONDARY_RGB = "rgb(160, 160, 171)" # --text-secondary #a0a0ab

# Light-theme Tailwind values that must NOT appear in layout rules
_FORBIDDEN_LIGHT_COLORS = [
    "#f9fafb",   # bg-gray-50
    "#f3f4f6",   # bg-gray-100 / border-gray-100
    "#111827",   # text-gray-900
    "#6b7280",   # text-gray-500
    "bg-gray-50",
    "border-gray-100",
    "bg-white",
    "text-gray-900",
    "text-gray-500",
]


# ---------------------------------------------------------------------------
# HTML fixture builder
# ---------------------------------------------------------------------------

def _load_css(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_dark_theme_fixture() -> str:
    """Return a self-contained HTML page with dark theme and playlist layout elements."""
    globals_css = _load_css(_GLOBALS_CSS)
    module_css = _load_css(_PLAYLIST_CSS)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>Playlist Page Dark Theme Fixture MYTUBE-603</title>\n"
        "  <style>" + globals_css + "</style>\n"
        "  <style>" + module_css + "</style>\n"
        "</head>\n"
        "<body data-theme=\"dark\">\n"
        "  <main class=\"page\" id=\"playlist-page\">\n"
        "    <div class=\"header\" id=\"playlist-header\">\n"
        "      <h1 class=\"title\" id=\"playlist-title\">Test Playlist</h1>\n"
        "      <p class=\"subtitle\" id=\"playlist-subtitle\">4 videos</p>\n"
        "    </div>\n"
        "    <div class=\"splitView\">\n"
        "      <div class=\"playerArea\"></div>\n"
        "      <div class=\"queuePanel\">\n"
        "        <div class=\"queueCard\" id=\"queue-card\">\n"
        "          <div class=\"queueHeader\" id=\"queue-header\">\n"
        "            <p class=\"queueHeaderTitle\">Queue</p>\n"
        "          </div>\n"
        "        </div>\n"
        "      </div>\n"
        "    </div>\n"
        "  </main>\n"
        "</body>\n"
        "</html>"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def dark_fixture_page(browser):
    """Playwright page loaded with the dark-theme HTML fixture."""
    page = browser.new_page()
    page.set_content(
        _build_dark_theme_fixture(),
        wait_until="domcontentloaded",
    )
    yield page
    page.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_computed(page: Page, selector: str, prop: str) -> str:
    """Return the computed CSS property of the first matched element."""
    return page.evaluate(
        """([sel, prop]) => {
            const el = document.querySelector(sel);
            if (!el) return '';
            return getComputedStyle(el).getPropertyValue(prop).trim();
        }""",
        [selector, prop],
    )


# ---------------------------------------------------------------------------
# Tests — Static CSS analysis
# ---------------------------------------------------------------------------

class TestPlaylistPageStaticCSS:
    """Static analysis: verify design tokens are used in PlaylistPageClient.module.css."""

    def setup_method(self) -> None:
        self.css = PlaylistCSSModule()

    def test_css_file_exists(self) -> None:
        """PlaylistPageClient.module.css must exist in the web source tree."""
        assert self.css.file_exists(), (
            f"PlaylistPageClient.module.css not found at {_PLAYLIST_CSS}. "
            "The CSS module must exist for the playlist page to be styled."
        )

    def test_page_background_uses_bg_page_token(self) -> None:
        """
        The .page rule must use var(--bg-page) for background.

        This ensures the page background adapts to dark theme instead of
        displaying a hardcoded light color (e.g., bg-gray-50 = #f9fafb).
        """
        assert self.css.rule_contains("page", "var(--bg-page)"), (
            f".page rule does not contain 'var(--bg-page)'. "
            f"Found rule body: {self.css.get_rule_body('page')!r}. "
            "The page background must use the --bg-page design token so it "
            "renders dark (#0f0f11) in dark theme instead of light-gray."
        )

    def test_title_color_uses_text_primary_token(self) -> None:
        """
        The .title rule must use var(--text-primary) for color.

        Ensures the playlist title text is readable in dark mode (#f0f0f0)
        instead of hardcoded dark gray (#111827 / text-gray-900).
        """
        assert self.css.rule_contains("title", "var(--text-primary)"), (
            f".title rule does not contain 'var(--text-primary)'. "
            f"Found rule body: {self.css.get_rule_body('title')!r}. "
            "The title color must use the --text-primary design token."
        )

    def test_subtitle_color_uses_text_secondary_token(self) -> None:
        """
        The .subtitle rule must use var(--text-secondary) for color.

        Ensures the subtitle (e.g., '4 videos') is readable in dark mode
        instead of hardcoded medium gray (#6b7280 / text-gray-500).
        """
        assert self.css.rule_contains("subtitle", "var(--text-secondary)"), (
            f".subtitle rule does not contain 'var(--text-secondary)'. "
            f"Found rule body: {self.css.get_rule_body('subtitle')!r}. "
            "The subtitle color must use the --text-secondary design token."
        )

    def test_queue_card_uses_bg_content_token(self) -> None:
        """
        The .queueCard rule must use var(--bg-content) for background.

        The queue panel card background must adapt to dark theme
        (--bg-content = #1a1a1f) instead of hardcoded white (bg-white).
        """
        assert self.css.rule_contains("queueCard", "var(--bg-content)"), (
            f".queueCard rule does not contain 'var(--bg-content)'. "
            f"Found rule body: {self.css.get_rule_body('queueCard')!r}. "
            "The queue card background must use the --bg-content design token."
        )

    def test_queue_header_border_uses_border_light_token(self) -> None:
        """
        The .queueHeader rule must use var(--border-light) for its bottom border.

        Ensures the divider between the queue header and list adapts to dark
        theme (#333340) instead of a hardcoded light border (border-gray-100).
        """
        assert self.css.rule_contains("queueHeader", "var(--border-light)"), (
            f".queueHeader rule does not contain 'var(--border-light)'. "
            f"Found rule body: {self.css.get_rule_body('queueHeader')!r}. "
            "The queue header bottom border must use the --border-light token."
        )

    def test_no_hardcoded_bg_gray_50(self) -> None:
        """
        The stylesheet must not contain the hardcoded bg-gray-50 hex (#f9fafb).

        bg-gray-50 is a Tailwind light-theme class. Its presence would cause
        the page background to be light-gray even in dark mode.
        """
        assert not self.css.file_contains_ignorecase("#f9fafb"), (
            "PlaylistPageClient.module.css contains hardcoded '#f9fafb' (bg-gray-50). "
            "This light-theme colour must be replaced with var(--bg-page) or similar token. "
            "The fix from MYTUBE-593 should have removed all hardcoded Tailwind palette values."
        )

    def test_no_hardcoded_border_gray_100(self) -> None:
        """
        The stylesheet must not contain the hardcoded border-gray-100 hex (#f3f4f6).

        border-gray-100 / bg-gray-100 is a Tailwind light-theme class. Its
        presence would cause borders and backgrounds to appear light in dark mode.
        """
        assert not self.css.file_contains_ignorecase("#f3f4f6"), (
            "PlaylistPageClient.module.css contains hardcoded '#f3f4f6' (border-gray-100 equivalent). "
            "This light-theme colour must be replaced with var(--border-light) or similar token. "
            "The fix from MYTUBE-593 should have removed all hardcoded Tailwind palette values."
        )

    def test_dark_theme_bg_page_defined_in_globals(self) -> None:
        """
        globals.css must define --bg-page: #0f0f11 inside the dark theme block.

        This confirms the playlist page background will be near-black in dark mode.
        """
        css_text = _GLOBALS_CSS.read_text(encoding="utf-8")
        dark_block_match = re.search(
            r'body\[data-theme="dark"\]\s*\{([^}]*)\}',
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        assert dark_block_match, (
            'body[data-theme="dark"] block not found in globals.css. '
            "The dark theme CSS variables must be defined there."
        )
        dark_block = dark_block_match.group(1)
        assert "--bg-page" in dark_block, (
            "--bg-page token not defined in the dark theme block of globals.css."
        )
        assert "#0f0f11" in dark_block.lower(), (
            f"Expected --bg-page: #0f0f11 in dark theme block but did not find it. "
            f"Dark theme block excerpt: {dark_block[:300]!r}"
        )


# ---------------------------------------------------------------------------
# Tests — Playwright fixture (dark theme computed styles)
# ---------------------------------------------------------------------------

class TestPlaylistPageDarkThemeComputed:
    """
    Playwright fixture: verify computed styles of playlist page elements in dark theme.

    Uses an HTML fixture that loads the actual CSS files with data-theme="dark"
    to resolve CSS variables and check that elements render with the correct
    dark-mode colours.
    """

    def test_dark_theme_active_on_page(self, dark_fixture_page: Page) -> None:
        """
        Precondition: body[data-theme="dark"] is set, page background resolves
        to --bg-page dark value (#0f0f11 = rgb(15, 15, 17)).
        """
        bg = _get_computed(dark_fixture_page, "#playlist-page", "background-color")
        assert bg == _EXPECTED_BG_PAGE_RGB, (
            f"Playlist page (.page) background-color in dark theme expected "
            f"'{_EXPECTED_BG_PAGE_RGB}' (--bg-page = #0f0f11) but got '{bg}'. "
            "Check that body[data-theme='dark'] is active and globals.css defines "
            "--bg-page: #0f0f11 in the dark theme block. "
            "If the page background is still light (#f9fafb), the fix from MYTUBE-593 "
            "may not have been applied to PlaylistPageClient.module.css."
        )

    def test_playlist_title_element_present(self, dark_fixture_page: Page) -> None:
        """Step 2: the playlist title element must be present in the DOM."""
        count = dark_fixture_page.evaluate(
            "() => document.querySelectorAll('#playlist-title').length"
        )
        assert count == 1, (
            f"Expected 1 element with id='playlist-title' but found {count}. "
            "Check the HTML fixture."
        )

    def test_title_color_resolves_to_text_primary(self, dark_fixture_page: Page) -> None:
        """
        Step 2: .title color must resolve to --text-primary = #f0f0f0 = rgb(240, 240, 240)
        in dark mode.

        This confirms the playlist title is readable against the dark background
        instead of being invisible (e.g., if hardcoded text-gray-900 = #111827 were used).
        """
        color = _get_computed(dark_fixture_page, "#playlist-title", "color")
        assert color == _EXPECTED_TEXT_PRIMARY_RGB, (
            f"Playlist title (.title) color in dark theme expected "
            f"'{_EXPECTED_TEXT_PRIMARY_RGB}' (--text-primary = #f0f0f0) but got '{color}'. "
            "The title text color must use var(--text-primary). "
            "Check PlaylistPageClient.module.css .title {{ color }}."
        )

    def test_subtitle_color_resolves_to_text_secondary(self, dark_fixture_page: Page) -> None:
        """
        Step 2: .subtitle color must resolve to --text-secondary = #a0a0ab = rgb(160, 160, 171)
        in dark mode.

        Confirms the video count / metadata subtitle uses the correct secondary
        text token rather than hardcoded gray.
        """
        color = _get_computed(dark_fixture_page, "#playlist-subtitle", "color")
        assert color == _EXPECTED_TEXT_SECONDARY_RGB, (
            f"Playlist subtitle (.subtitle) color in dark theme expected "
            f"'{_EXPECTED_TEXT_SECONDARY_RGB}' (--text-secondary = #a0a0ab) but got '{color}'. "
            "Check PlaylistPageClient.module.css .subtitle {{ color }}."
        )

    def test_queue_card_background_resolves_to_bg_content(self, dark_fixture_page: Page) -> None:
        """
        Step 2: .queueCard background must resolve to --bg-content = #1a1a1f = rgb(26, 26, 31)
        in dark mode.

        The queue panel card must not appear white (bg-white) in dark mode.
        """
        bg = _get_computed(dark_fixture_page, "#queue-card", "background-color")
        assert bg == _EXPECTED_BG_CONTENT_RGB, (
            f"Queue card (.queueCard) background-color in dark theme expected "
            f"'{_EXPECTED_BG_CONTENT_RGB}' (--bg-content = #1a1a1f) but got '{bg}'. "
            "Check PlaylistPageClient.module.css .queueCard {{ background }}."
        )

    def test_page_background_distinct_from_light_theme(self, dark_fixture_page: Page) -> None:
        """
        Step 2: The resolved page background must be distinctly dark (not light-gray).

        bg-gray-50 = rgb(249, 250, 251). Asserts the page background is NOT
        that light value, confirming the dark theme token is in effect.
        """
        bg = _get_computed(dark_fixture_page, "#playlist-page", "background-color")
        light_gray_50_rgb = "rgb(249, 250, 251)"
        assert bg != light_gray_50_rgb, (
            f"Playlist page background-color is '{bg}', which matches the light-theme "
            f"bg-gray-50 value '{light_gray_50_rgb}'. "
            "The page is NOT rendering in dark theme — the design token fix from "
            "MYTUBE-593 may be missing."
        )
