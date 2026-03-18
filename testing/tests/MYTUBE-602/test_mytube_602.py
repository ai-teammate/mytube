"""
MYTUBE-602: Dashboard edit modal and tables — backgrounds respect dark theme tokens

Objective
---------
Verify that the edit-video modal and the playlist management table backgrounds
correctly switch to dark theme tokens instead of hardcoded white classes.

Preconditions
-------------
Dark theme is enabled (``body[data-theme="dark"]``).

Steps
-----
1. Navigate to the Dashboard.
2. Open the Edit Video modal.
3. Switch to the Playlists tab to view the management table.

Expected Result
---------------
The modal (``.modalCard``) and table (``.playlistTable``) backgrounds are updated
to use design tokens like ``var(--bg-content)`` / ``var(--bg-card)``.
No hardcoded ``bg-white`` or ``bg-gray-50`` Tailwind classes appear on these elements.

Test Strategy
-------------
Two complementary layers:

**Layer A — Static CSS analysis** (always runs):
  - Parses ``_content.module.css`` to verify ``.modalCard`` background uses
    ``var(--bg-content)`` or another CSS variable (not hardcoded white).
  - Parses ``.playlistTable`` background uses ``var(--bg-content)`` or another
    CSS variable (not hardcoded white).
  - Verifies ``_content.tsx`` does NOT contain hardcoded ``bg-white`` or
    ``bg-gray-50`` Tailwind classes on the modal or playlist table elements.

**Layer B — HTML fixture (Playwright, always runs)**:
  - Renders a self-contained HTML page embedding the actual ``_content.module.css``
    and ``globals.css`` with ``data-theme="dark"`` set on ``<body>``.
  - Uses ``getComputedStyle()`` to assert that the resolved background-color of
    the modal card and playlist table wrapper matches the dark token values
    (``--bg-content = #1a1a1f``), NOT ``rgb(255, 255, 255)`` (white).

Architecture
------------
- Playwright sync API with pytest module-scoped fixtures.
- HTML fixture mode uses page.set_content() with inline CSS — no external deps.

Linked bugs
-----------
MYTUBE-593 (Done): Dashboard My Videos and Playlists look broken in dark theme.
  Fix replaced all hardcoded Tailwind colour classes and inline hex values in
  ``_content.tsx`` and ``DashboardVideoCard.module.css`` with CSS design tokens.
  The modal (``bg-white rounded-2xl``) and playlist table (``rounded-2xl bg-white``)
  were specifically called out as unthemed elements that now use ``var(--bg-content)``.
"""
from __future__ import annotations

import pathlib
import re
import sys
import os

import pytest
from playwright.sync_api import Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_CONTENT_CSS = _REPO_ROOT / "web" / "src" / "app" / "dashboard" / "_content.module.css"
_CONTENT_TSX = _REPO_ROOT / "web" / "src" / "app" / "dashboard" / "_content.tsx"
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Expected resolved values (dark theme)
# In dark mode:  --bg-content = #1a1a1f  --bg-card = #242428
# ---------------------------------------------------------------------------

_EXPECTED_BG_CONTENT_DARK_RGB = "rgb(26, 26, 31)"    # #1a1a1f
_EXPECTED_BG_CARD_DARK_RGB    = "rgb(36, 36, 40)"    # #242428
_WHITE_RGB                     = "rgb(255, 255, 255)"  # hardcoded white — must NOT appear


# ---------------------------------------------------------------------------
# CSS helpers
# ---------------------------------------------------------------------------

def _read_css(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _get_rule_body(css_text: str, selector: str) -> str:
    """Return the rule body for the given CSS selector, or empty string if not found."""
    # Match `.selector { ... }` — handles multi-line bodies
    pattern = re.compile(
        r"\." + re.escape(selector) + r"\s*\{([^}]*)\}",
        re.DOTALL,
    )
    m = pattern.search(css_text)
    return m.group(1) if m else ""


def _rule_contains(css_text: str, selector: str, token: str) -> bool:
    body = _get_rule_body(css_text, selector)
    return token in body


# ---------------------------------------------------------------------------
# HTML fixture builder
# ---------------------------------------------------------------------------

def _build_dark_theme_fixture() -> str:
    """Return a self-contained HTML page with dark theme, modal card, and playlist table."""
    globals_css = _read_css(_GLOBALS_CSS)
    content_css = _read_css(_CONTENT_CSS)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>Dashboard Dark Theme Fixture MYTUBE-602</title>\n"
        "  <style>" + globals_css + "</style>\n"
        "  <style>" + content_css + "</style>\n"
        "</head>\n"
        "<body data-theme=\"dark\">\n"
        "  <!-- Edit Video modal -->\n"
        "  <div class=\"modalCard\" id=\"modal-card\"\n"
        "       role=\"dialog\" aria-modal=\"true\">\n"
        "    <h2 class=\"modalTitle\">Edit Video</h2>\n"
        "  </div>\n"
        "  <!-- Playlist management table wrapper -->\n"
        "  <div class=\"playlistTable\" id=\"playlist-table\">\n"
        "    <table class=\"playlistTableEl\">\n"
        "      <thead>\n"
        "        <tr class=\"playlistTableHead\">\n"
        "          <th class=\"playlistTableHeadCell\">Name</th>\n"
        "          <th class=\"playlistTableHeadCell\">Date</th>\n"
        "          <th class=\"playlistTableHeadCell\">Actions</th>\n"
        "        </tr>\n"
        "      </thead>\n"
        "      <tbody>\n"
        "        <tr class=\"playlistTableRow\">\n"
        "          <td class=\"playlistTableCellTitle\">My Playlist</td>\n"
        "          <td class=\"playlistTableCellDate\">Jan 1, 2026</td>\n"
        "          <td class=\"playlistTableCellActions\">Rename</td>\n"
        "        </tr>\n"
        "      </tbody>\n"
        "    </table>\n"
        "  </div>\n"
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

def _get_computed_bg(page: Page, selector: str) -> str:
    """Return the computed background-color of the first element matching selector."""
    return page.evaluate(
        """([sel]) => {
            const el = document.querySelector(sel);
            if (!el) return '';
            return getComputedStyle(el).getPropertyValue('background-color').trim();
        }""",
        [selector],
    )


# ---------------------------------------------------------------------------
# Layer A — Static CSS analysis
# ---------------------------------------------------------------------------

class TestDashboardModalAndTableStaticCSS:
    """Layer A: Verify that _content.module.css uses CSS tokens for modal and table."""

    def setup_method(self) -> None:
        assert _CONTENT_CSS.exists(), (
            f"_content.module.css not found at {_CONTENT_CSS}. "
            "The file may have been moved or renamed."
        )
        self.css = _read_css(_CONTENT_CSS)

    def test_content_css_file_exists(self) -> None:
        """_content.module.css must exist in the dashboard source directory."""
        assert _CONTENT_CSS.exists(), (
            f"_content.module.css not found at {_CONTENT_CSS}."
        )

    def test_modal_card_rule_exists(self) -> None:
        """A `.modalCard` rule must be defined in _content.module.css."""
        body = _get_rule_body(self.css, "modalCard")
        assert body, (
            "No '.modalCard { ... }' rule found in _content.module.css. "
            "The edit-video modal card style may be missing."
        )

    def test_modal_card_background_uses_css_token(self) -> None:
        """`.modalCard` background must use a CSS variable, not a hardcoded colour.

        The MYTUBE-593 fix replaced `bg-white rounded-2xl` with
        `var(--bg-content)` to support dark theme. This test ensures the rule
        references a CSS custom property for the background.
        """
        body = _get_rule_body(self.css, "modalCard")
        assert "var(" in body and "background" in body, (
            f"'.modalCard' rule does not use a CSS variable for background. "
            f"Found rule body: {body!r}. "
            "The edit-video modal must use a design token (e.g. var(--bg-content)) "
            "instead of a hardcoded colour so it adapts to the active theme."
        )

    def test_modal_card_background_uses_bg_content_or_bg_card_token(self) -> None:
        """`.modalCard` background must reference `--bg-content` or `--bg-card`.

        These are the canonical dark-mode surface tokens. Any other variable
        could still render white in dark mode.
        """
        uses_bg_content = _rule_contains(self.css, "modalCard", "--bg-content")
        uses_bg_card    = _rule_contains(self.css, "modalCard", "--bg-card")
        assert uses_bg_content or uses_bg_card, (
            f"'.modalCard' background does not reference '--bg-content' or '--bg-card'. "
            f"Found rule body: {_get_rule_body(self.css, 'modalCard')!r}. "
            "The modal card must use one of these surface tokens for correct dark-mode rendering."
        )

    def test_modal_card_background_not_hardcoded_white(self) -> None:
        """`.modalCard` must NOT contain hardcoded white colour values (#fff, #ffffff, white)."""
        body = _get_rule_body(self.css, "modalCard")
        for forbidden in ("#fff", "#ffffff", " white", ":white", "rgb(255"):
            assert forbidden not in body.lower(), (
                f"'.modalCard' rule contains a hardcoded white colour ({forbidden!r}). "
                f"Found rule body: {body!r}. "
                "Use var(--bg-content) or var(--bg-card) instead of hardcoded white."
            )

    def test_playlist_table_rule_exists(self) -> None:
        """A `.playlistTable` rule must be defined in _content.module.css."""
        body = _get_rule_body(self.css, "playlistTable")
        assert body, (
            "No '.playlistTable { ... }' rule found in _content.module.css. "
            "The playlist table wrapper style may be missing."
        )

    def test_playlist_table_background_uses_css_token(self) -> None:
        """`.playlistTable` background must use a CSS variable, not a hardcoded colour.

        The MYTUBE-593 fix replaced the `rounded-2xl bg-white` playlist table with
        `var(--bg-content)` to support dark theme.
        """
        body = _get_rule_body(self.css, "playlistTable")
        assert "var(" in body and "background" in body, (
            f"'.playlistTable' rule does not use a CSS variable for background. "
            f"Found rule body: {body!r}. "
            "The playlist management table must use a design token (e.g. var(--bg-content)) "
            "instead of a hardcoded colour so it adapts to the active theme."
        )

    def test_playlist_table_background_uses_bg_content_or_bg_card_token(self) -> None:
        """`.playlistTable` background must reference `--bg-content` or `--bg-card`."""
        uses_bg_content = _rule_contains(self.css, "playlistTable", "--bg-content")
        uses_bg_card    = _rule_contains(self.css, "playlistTable", "--bg-card")
        assert uses_bg_content or uses_bg_card, (
            f"'.playlistTable' background does not reference '--bg-content' or '--bg-card'. "
            f"Found rule body: {_get_rule_body(self.css, 'playlistTable')!r}. "
            "The playlist table must use one of these surface tokens for correct dark-mode rendering."
        )

    def test_playlist_table_background_not_hardcoded_white(self) -> None:
        """`.playlistTable` must NOT contain hardcoded white colour values."""
        body = _get_rule_body(self.css, "playlistTable")
        for forbidden in ("#fff", "#ffffff", " white", ":white", "rgb(255"):
            assert forbidden not in body.lower(), (
                f"'.playlistTable' rule contains a hardcoded white colour ({forbidden!r}). "
                f"Found rule body: {body!r}. "
                "Use var(--bg-content) or var(--bg-card) instead of hardcoded white."
            )

    def test_content_tsx_no_hardcoded_bg_white_on_modal(self) -> None:
        """_content.tsx must not pass `bg-white` as a className to the modal element.

        Prior to the MYTUBE-593 fix the modal was rendered as
        ``<div className="bg-white rounded-2xl ...">`` which bypassed all theme
        tokens. After the fix, the modal uses the CSS module class ``.modalCard``
        with ``var(--bg-content)``.
        """
        if not _CONTENT_TSX.exists():
            pytest.skip(f"_content.tsx not found at {_CONTENT_TSX}")
        tsx_text = _CONTENT_TSX.read_text(encoding="utf-8")
        # We allow bg-white to appear in comments or string literals elsewhere,
        # but it must NOT appear as an active className that could affect the modal.
        # The simplest check: count occurrences of bg-white in className= attributes.
        classname_bg_white = re.findall(r'className=["\'][^"\']*bg-white[^"\']*["\']', tsx_text)
        assert len(classname_bg_white) == 0, (
            f"_content.tsx still contains {len(classname_bg_white)} className attribute(s) "
            f"with hardcoded 'bg-white': {classname_bg_white}. "
            "The MYTUBE-593 fix should have replaced these with CSS module classes "
            "that use design tokens."
        )

    def test_content_tsx_no_hardcoded_bg_gray_50_on_modal_or_table(self) -> None:
        """_content.tsx must not pass `bg-gray-50` as a className to modal or table elements.

        Prior to the MYTUBE-593 fix, `bg-gray-50` was used as the modal overlay
        or table background in light mode, and did not adapt to dark theme.
        """
        if not _CONTENT_TSX.exists():
            pytest.skip(f"_content.tsx not found at {_CONTENT_TSX}")
        tsx_text = _CONTENT_TSX.read_text(encoding="utf-8")
        classname_bg_gray_50 = re.findall(r'className=["\'][^"\']*bg-gray-50[^"\']*["\']', tsx_text)
        assert len(classname_bg_gray_50) == 0, (
            f"_content.tsx still contains {len(classname_bg_gray_50)} className attribute(s) "
            f"with hardcoded 'bg-gray-50': {classname_bg_gray_50}. "
            "The MYTUBE-593 fix should have replaced these with CSS module classes "
            "that use design tokens."
        )

    def test_globals_css_defines_bg_content_in_dark_theme(self) -> None:
        """globals.css must define `--bg-content` inside `body[data-theme=\"dark\"]`.

        This confirms the dark-mode surface colour that the modal and table
        will resolve to is defined and not inherited from the light theme.
        """
        assert _GLOBALS_CSS.exists(), f"globals.css not found at {_GLOBALS_CSS}"
        css_text = _GLOBALS_CSS.read_text(encoding="utf-8")
        dark_block_match = re.search(
            r'body\[data-theme="dark"\]\s*\{([^}]*)\}',
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        assert dark_block_match, (
            'body[data-theme="dark"] block not found in globals.css.'
        )
        dark_block = dark_block_match.group(1)
        assert "--bg-content" in dark_block, (
            "--bg-content token not defined in the dark theme block of globals.css. "
            "The modal and playlist table will not render correctly in dark mode."
        )
        assert "#1a1a1f" in dark_block.lower(), (
            "Expected --bg-content: #1a1a1f in dark theme block but did not find it. "
            f"Dark theme block excerpt: {dark_block[:300]!r}"
        )


# ---------------------------------------------------------------------------
# Layer B — Playwright HTML fixture (dark theme computed styles)
# ---------------------------------------------------------------------------

class TestDashboardModalAndTableDarkThemeComputed:
    """Layer B: Verify computed background-color values of modal and table in dark theme.

    Uses a self-contained HTML fixture with actual CSS files and
    body[data-theme="dark"] to resolve CSS variables.
    """

    def test_dark_theme_is_active_on_body(self, dark_fixture_page: Page) -> None:
        """Precondition: body[data-theme="dark"] is set.

        Verified by checking the body's own background-color resolves to
        --bg-page = #0f0f11 = rgb(15, 15, 17).
        """
        bg = _get_computed_bg(dark_fixture_page, "body")
        assert bg == "rgb(15, 15, 17)", (
            f"body background-color in dark theme expected 'rgb(15, 15, 17)' "
            f"(--bg-page = #0f0f11) but got '{bg}'. "
            "Check that body[data-theme='dark'] is active and globals.css defines "
            "--bg-page: #0f0f11 in the dark theme block."
        )

    def test_modal_card_element_present(self, dark_fixture_page: Page) -> None:
        """Step 2: the modal card element (#modal-card) must be present in the DOM."""
        count = dark_fixture_page.evaluate(
            "() => document.querySelectorAll('#modal-card').length"
        )
        assert count == 1, (
            f"Expected 1 modal card element with id='modal-card' but found {count}."
        )

    def test_modal_card_background_is_dark_not_white(
        self, dark_fixture_page: Page
    ) -> None:
        """Step 2: Modal card background must NOT be white in dark theme.

        The MYTUBE-593 fix replaced the hardcoded 'bg-white' class on the modal
        with 'var(--bg-content)'. In dark mode, --bg-content resolves to #1a1a1f
        (rgb(26, 26, 31)), NOT rgb(255, 255, 255) (white).
        """
        bg = _get_computed_bg(dark_fixture_page, "#modal-card")
        assert bg != _WHITE_RGB, (
            f"Modal card background-color in dark theme is '{bg}' which equals white "
            f"({_WHITE_RGB}). The modal is NOT adapting to dark theme. "
            "Check that .modalCard in _content.module.css uses var(--bg-content) "
            "instead of a hardcoded white colour."
        )

    def test_modal_card_background_matches_bg_content_dark_token(
        self, dark_fixture_page: Page
    ) -> None:
        """Step 2: Modal card background must resolve to --bg-content = #1a1a1f in dark mode."""
        bg = _get_computed_bg(dark_fixture_page, "#modal-card")
        assert bg == _EXPECTED_BG_CONTENT_DARK_RGB, (
            f"Modal card background-color in dark theme expected "
            f"'{_EXPECTED_BG_CONTENT_DARK_RGB}' (--bg-content = #1a1a1f) but got '{bg}'. "
            "The edit-video modal background must use var(--bg-content) to correctly "
            "render in dark theme. Check .modalCard in _content.module.css."
        )

    def test_playlist_table_element_present(self, dark_fixture_page: Page) -> None:
        """Step 3: the playlist table wrapper (#playlist-table) must be present in the DOM."""
        count = dark_fixture_page.evaluate(
            "() => document.querySelectorAll('#playlist-table').length"
        )
        assert count == 1, (
            f"Expected 1 playlist table element with id='playlist-table' but found {count}."
        )

    def test_playlist_table_background_is_dark_not_white(
        self, dark_fixture_page: Page
    ) -> None:
        """Step 3: Playlist table wrapper background must NOT be white in dark theme.

        The MYTUBE-593 fix replaced the hardcoded 'bg-white rounded-2xl' classes
        on the playlist table with 'var(--bg-content)'. In dark mode, --bg-content
        resolves to #1a1a1f, NOT white.
        """
        bg = _get_computed_bg(dark_fixture_page, "#playlist-table")
        assert bg != _WHITE_RGB, (
            f"Playlist table background-color in dark theme is '{bg}' which equals white "
            f"({_WHITE_RGB}). The playlist table is NOT adapting to dark theme. "
            "Check that .playlistTable in _content.module.css uses var(--bg-content) "
            "instead of a hardcoded white colour."
        )

    def test_playlist_table_background_matches_bg_content_dark_token(
        self, dark_fixture_page: Page
    ) -> None:
        """Step 3: Playlist table background must resolve to --bg-content = #1a1a1f in dark mode."""
        bg = _get_computed_bg(dark_fixture_page, "#playlist-table")
        assert bg == _EXPECTED_BG_CONTENT_DARK_RGB, (
            f"Playlist table background-color in dark theme expected "
            f"'{_EXPECTED_BG_CONTENT_DARK_RGB}' (--bg-content = #1a1a1f) but got '{bg}'. "
            "The playlist management table background must use var(--bg-content) to correctly "
            "render in dark theme. Check .playlistTable in _content.module.css."
        )

    def test_modal_background_contrasts_with_page_background(
        self, dark_fixture_page: Page
    ) -> None:
        """Modal card background must be visually distinct from the page background.

        In dark mode:
          --bg-page    = #0f0f11 = rgb(15, 15, 17)
          --bg-content = #1a1a1f = rgb(26, 26, 31)

        If both are the same, the modal will be invisible.
        """
        modal_bg = _get_computed_bg(dark_fixture_page, "#modal-card")
        page_bg  = _get_computed_bg(dark_fixture_page, "body")
        assert modal_bg != page_bg, (
            f"Modal card background ('{modal_bg}') is identical to the page background "
            f"('{page_bg}'). The modal would be invisible against the dark page background."
        )

    def test_playlist_table_background_contrasts_with_page_background(
        self, dark_fixture_page: Page
    ) -> None:
        """Playlist table background must be visually distinct from the page background.

        Same contrast requirement as the modal.
        """
        table_bg = _get_computed_bg(dark_fixture_page, "#playlist-table")
        page_bg  = _get_computed_bg(dark_fixture_page, "body")
        assert table_bg != page_bg, (
            f"Playlist table background ('{table_bg}') is identical to the page background "
            f"('{page_bg}'). The playlist management table would be invisible against the "
            "dark page background."
        )
