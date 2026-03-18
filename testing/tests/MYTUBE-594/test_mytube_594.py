"""
MYTUBE-594: Upload video in dark theme — Choose File button is clearly visible and styled

Objective
---------
Verify that the native Choose File button (``::file-selector-button`` pseudo-element)
on the upload page is visible and correctly styled using design tokens when the dark
theme is active.

Preconditions
-------------
The application is in dark theme (``body[data-theme="dark"]``).

Steps
-----
1. Navigate to the /upload page.
2. Locate the file input field within the upload card.
3. Observe the appearance of the button (the ``::file-selector-button`` pseudo-element).

Expected Result
---------------
The button is clearly visible against the card background (--bg-card = #242428 in dark mode).
It is styled using the specified design tokens (--accent-cta, --text-cta), ensuring
high contrast and visibility in dark mode.

Test Strategy
-------------
Dual-mode approach:

**Static analysis** (always runs): Parses ``upload.module.css`` to verify the
``::file-selector-button`` rule contains ``var(--accent-cta)`` and ``var(--text-cta)``.
This ensures the fix from MYTUBE-591 is present in the source file.

**Fixture mode** (Playwright, always runs): Renders a self-contained HTML page
embedding the exact CSS from ``upload.module.css`` and ``globals.css`` with
``data-theme="dark"`` set on the ``<body>`` element.  Uses
``getComputedStyle(el, "::file-selector-button")`` to assert the resolved
background-color and color match the expected dark-mode token values.

Architecture
------------
- UploadCSSModule from testing/components/pages/upload_page/upload_css_module.py
  for CSS static analysis.
- WebConfig from testing/core/config/web_config.py for environment config.
- Playwright sync API with pytest module-scoped fixtures.
- HTML fixture mode uses page.set_content() with inline CSS -- no external deps.

Linked bugs
-----------
MYTUBE-591 (Done): ::file-selector-button styling was missing from
upload.module.css. Fix added background: var(--accent-cta), color: var(--text-cta),
border-radius, padding, font-weight and a hover rule.
"""
from __future__ import annotations

import pathlib
import sys
import os

import pytest
from playwright.sync_api import Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.upload_page.upload_css_module import UploadCSSModule

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_UPLOAD_CSS = _REPO_ROOT / "web" / "src" / "app" / "upload" / "upload.module.css"
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Expected resolved values (dark theme)
# In dark mode:  --accent-cta = #62c235  --text-cta = #ffffff  --bg-card = #242428
# ---------------------------------------------------------------------------

_EXPECTED_ACCENT_CTA_RGB = "rgb(98, 194, 53)"    # #62c235
_EXPECTED_TEXT_CTA_RGB = "rgb(255, 255, 255)"    # #ffffff
_EXPECTED_BG_CARD_DARK_RGB = "rgb(36, 36, 40)"  # #242428

# CSS token names as they appear in source
_TOKEN_ACCENT_CTA = "var(--accent-cta)"
_TOKEN_TEXT_CTA = "var(--text-cta)"


# ---------------------------------------------------------------------------
# HTML fixture builder
# ---------------------------------------------------------------------------

def _load_css(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _build_dark_theme_fixture() -> str:
    """Return a self-contained HTML page with dark theme and the file input styled."""
    globals_css = _load_css(_GLOBALS_CSS)
    module_css = _load_css(_UPLOAD_CSS)
    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>File Input Dark Theme Fixture MYTUBE-594</title>\n"
        "  <style>" + globals_css + "</style>\n"
        "  <style>" + module_css + "</style>\n"
        "</head>\n"
        "<body data-theme=\"dark\">\n"
        "  <section class=\"uploadCard\" id=\"upload-card\">\n"
        "    <input type=\"file\" class=\"fileInput\" id=\"file-input\" />\n"
        "  </section>\n"
        "</body>\n"
        "</html>"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


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

def _get_pseudo_style(page: Page, selector: str, pseudo: str, prop: str) -> str:
    """Return the computed style of a pseudo-element for the first matched element."""
    return page.evaluate(
        """([sel, pseudo, prop]) => {
            const el = document.querySelector(sel);
            if (!el) return '';
            return getComputedStyle(el, pseudo).getPropertyValue(prop).trim();
        }""",
        [selector, pseudo, prop],
    )


def _get_computed(page: Page, selector: str, prop: str) -> str:
    """Return the computed CSS property of the element itself."""
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

class TestFileInputButtonStaticCSS:
    """Step 3 static analysis: verify ::file-selector-button rules exist in CSS source."""

    def test_file_selector_button_rule_exists(self) -> None:
        """
        The ::file-selector-button rule must be present in upload.module.css.

        This verifies the MYTUBE-591 fix is in the source file.
        """
        css_text = _UPLOAD_CSS.read_text(encoding="utf-8")
        assert "::file-selector-button" in css_text, (
            "No ::file-selector-button rule found in upload.module.css. "
            "The fix from MYTUBE-591 may be missing."
        )

    def test_file_selector_button_background_uses_accent_cta_token(self) -> None:
        """
        The ::file-selector-button rule must set background to var(--accent-cta).

        Ensures the button has the CTA green background for visibility in dark mode.
        """
        css_text = _UPLOAD_CSS.read_text(encoding="utf-8")
        import re
        # Find the ::file-selector-button block
        pattern = r"::file-selector-button\s*\{([^}]*)\}"
        match = re.search(pattern, css_text, re.DOTALL | re.IGNORECASE)
        assert match, (
            "::file-selector-button rule block not found in upload.module.css."
        )
        rule_body = match.group(1).lower()
        assert "var(--accent-cta)" in rule_body, (
            f"::file-selector-button rule does not contain 'var(--accent-cta)'. "
            f"Found rule body: {rule_body.strip()!r}. "
            "The button background must use the --accent-cta design token for "
            "correct visibility in dark mode."
        )

    def test_file_selector_button_color_uses_text_cta_token(self) -> None:
        """
        The ::file-selector-button rule must set color to var(--text-cta).

        Ensures the button text is white (#ffffff) for readability in both themes.
        """
        css_text = _UPLOAD_CSS.read_text(encoding="utf-8")
        import re
        pattern = r"::file-selector-button\s*\{([^}]*)\}"
        match = re.search(pattern, css_text, re.DOTALL | re.IGNORECASE)
        assert match, (
            "::file-selector-button rule block not found in upload.module.css."
        )
        rule_body = match.group(1).lower()
        assert "var(--text-cta)" in rule_body, (
            f"::file-selector-button rule does not contain 'var(--text-cta)'. "
            f"Found rule body: {rule_body.strip()!r}. "
            "The button text color must use the --text-cta token."
        )

    def test_dark_theme_accent_cta_is_green(self) -> None:
        """
        In globals.css, the dark theme --accent-cta must be set to #62c235.

        This confirms the button will have sufficient contrast against --bg-card (#242428).
        """
        css_text = _GLOBALS_CSS.read_text(encoding="utf-8")
        import re
        # Find the dark theme block
        dark_block_match = re.search(
            r'body\[data-theme="dark"\]\s*\{([^}]*)\}',
            css_text,
            re.DOTALL | re.IGNORECASE,
        )
        assert dark_block_match, (
            'body[data-theme="dark"] block not found in globals.css.'
        )
        dark_block = dark_block_match.group(1)
        assert "--accent-cta" in dark_block, (
            "--accent-cta token not defined in the dark theme block of globals.css."
        )
        assert "#62c235" in dark_block.lower() or "62c235" in dark_block.lower(), (
            f"Expected --accent-cta: #62c235 in dark theme block but did not find it. "
            f"Dark theme block excerpt: {dark_block[:300]!r}"
        )


# ---------------------------------------------------------------------------
# Tests — Playwright fixture (dark theme computed styles)
# ---------------------------------------------------------------------------

class TestFileInputButtonDarkThemeComputed:
    """
    Step 3 Playwright: verify computed styles of ::file-selector-button in dark theme.

    Uses an HTML fixture that loads the actual CSS files with data-theme="dark"
    to resolve CSS variables and check the computed button styles.
    """

    def test_dark_theme_is_active_on_card(self, dark_fixture_page: Page) -> None:
        """
        Precondition: body[data-theme="dark"] is set, card background resolves
        to --bg-card dark value (#242428 = rgb(36, 36, 40)).
        """
        bg = _get_computed(dark_fixture_page, "#upload-card", "background-color")
        assert bg == _EXPECTED_BG_CARD_DARK_RGB, (
            f"Upload card background-color in dark theme expected "
            f"'{_EXPECTED_BG_CARD_DARK_RGB}' (--bg-card = #242428) but got '{bg}'. "
            "Check that body[data-theme='dark'] is active and globals.css defines "
            "--bg-card: #242428 in the dark theme block."
        )

    def test_file_input_element_is_present(self, dark_fixture_page: Page) -> None:
        """
        Step 2: the file input element (id=file-input) must be present in the DOM.
        """
        count = dark_fixture_page.evaluate(
            "() => document.querySelectorAll('#file-input').length"
        )
        assert count == 1, (
            f"Expected 1 file input element with id='file-input' but found {count}. "
            "Check the HTML fixture or the upload page template."
        )

    def test_file_selector_button_background_resolves_to_accent_cta(
        self, dark_fixture_page: Page
    ) -> None:
        """
        Step 3: ::file-selector-button background-color must resolve to
        --accent-cta = #62c235 = rgb(98, 194, 53) in dark mode.

        This is the primary visibility assertion: the green button stands out
        against the dark card background rgb(36, 36, 40).
        """
        bg = _get_pseudo_style(
            dark_fixture_page, "#file-input", "::file-selector-button", "background-color"
        )
        assert bg == _EXPECTED_ACCENT_CTA_RGB, (
            f"::file-selector-button background-color in dark theme expected "
            f"'{_EXPECTED_ACCENT_CTA_RGB}' (--accent-cta = #62c235) but got '{bg}'. "
            "The Choose File button is not using the CTA green colour — it may be "
            "invisible against the dark card background (#242428). "
            "Check upload.module.css .fileInput::file-selector-button {{ background }}."
        )

    def test_file_selector_button_color_resolves_to_text_cta(
        self, dark_fixture_page: Page
    ) -> None:
        """
        Step 3: ::file-selector-button color must resolve to
        --text-cta = #ffffff = rgb(255, 255, 255) in dark mode.

        White text on the green button ensures readable label in dark theme.
        """
        color = _get_pseudo_style(
            dark_fixture_page, "#file-input", "::file-selector-button", "color"
        )
        assert color == _EXPECTED_TEXT_CTA_RGB, (
            f"::file-selector-button color in dark theme expected "
            f"'{_EXPECTED_TEXT_CTA_RGB}' (--text-cta = #ffffff) but got '{color}'. "
            "Check upload.module.css .fileInput::file-selector-button {{ color }}."
        )

    def test_file_selector_button_has_border_radius(
        self, dark_fixture_page: Page
    ) -> None:
        """
        Step 3: ::file-selector-button must have a border-radius (8px) for
        consistent styling with other CTA buttons on the page.
        """
        br = _get_pseudo_style(
            dark_fixture_page, "#file-input", "::file-selector-button", "border-radius"
        )
        assert br and br != "0px", (
            f"::file-selector-button border-radius expected '8px' but got '{br}'. "
            "Check upload.module.css .fileInput::file-selector-button {{ border-radius }}."
        )

    def test_file_selector_button_background_contrasts_with_dark_card(
        self, dark_fixture_page: Page
    ) -> None:
        """
        Step 3: The button background (rgb(98, 194, 53)) must be visually distinct
        from the dark card background (rgb(36, 36, 40)).

        Passes as a sanity check that the button does NOT blend into the background.
        """
        btn_bg = _get_pseudo_style(
            dark_fixture_page, "#file-input", "::file-selector-button", "background-color"
        )
        card_bg = _get_computed(dark_fixture_page, "#upload-card", "background-color")
        assert btn_bg != card_bg, (
            f"::file-selector-button background-color ('{btn_bg}') is identical to "
            f"the card background-color ('{card_bg}'). "
            "The button is invisible — it blends into the dark card background."
        )
