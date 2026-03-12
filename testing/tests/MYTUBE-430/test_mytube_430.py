"""
MYTUBE-430: Inspect global CSS — light theme design tokens are correctly defined

Objective
---------
Verify that the full set of light theme CSS design tokens is correctly defined
in the global stylesheet.

Steps
-----
1. Open the application in a web browser.
2. Open Developer Tools (F12) and inspect the body or :root element.
3. Locate the CSS custom properties (variables) in the Styles pane.

Expected Result
---------------
All required tokens are present with correct values:
  --bg-page:    #f8f9fa
  --bg-content: #ffffff
  --text-primary: #222222
  --accent-cta:  #62c235
  --shadow-main: 0 8px 24px rgba(0,0,0,0.06)

Test approach
-------------
Reads web/src/app/globals.css directly and parses each CSS custom property
from the :root block using regex. No browser or HTTP server required. Any
change to globals.css that alters a token value will cause the corresponding
assertion to fail, providing genuine regression protection.
"""
from __future__ import annotations

import os
import re
import sys

import pathlib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.css_globals_page.css_globals_page import (
    CSSGlobalsPage,
)

# ---------------------------------------------------------------------------
# Shared CSS parser instance (reads the real globals.css once)
# ---------------------------------------------------------------------------

_css = CSSGlobalsPage()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLightThemeDesignTokens:
    """MYTUBE-430: Light theme CSS design tokens are correctly defined."""

    def test_bg_page_token(self) -> None:
        """--bg-page must be #f8f9fa."""
        value = _css.get_light_token("--bg-page")
        assert value == "#f8f9fa", (
            f"Expected --bg-page to be '#f8f9fa' but got '{value}'. "
            "The light theme background page token is missing or incorrect in globals.css."
        )

    def test_bg_content_token(self) -> None:
        """--bg-content must be #ffffff."""
        value = _css.get_light_token("--bg-content")
        assert value == "#ffffff", (
            f"Expected --bg-content to be '#ffffff' but got '{value}'. "
            "The light theme content background token is missing or incorrect in globals.css."
        )

    def test_text_primary_token(self) -> None:
        """--text-primary must be #222222."""
        value = _css.get_light_token("--text-primary")
        assert value == "#222222", (
            f"Expected --text-primary to be '#222222' but got '{value}'. "
            "The light theme primary text token is missing or incorrect in globals.css."
        )

    def test_accent_cta_token(self) -> None:
        """--accent-cta must be #62c235."""
        value = _css.get_light_token("--accent-cta")
        assert value == "#62c235", (
            f"Expected --accent-cta to be '#62c235' but got '{value}'. "
            "The light theme CTA accent token is missing or incorrect in globals.css."
        )

    def test_shadow_main_token(self) -> None:
        """--shadow-main must be '0 8px 24px rgba(0,0,0,0.06)'."""
        value = _css.get_light_token("--shadow-main")
        # Normalize whitespace for comparison
        normalized = " ".join(value.split())
        expected = "0 8px 24px rgba(0,0,0,0.06)"
        # Also accept the slightly different spacing variant that browsers may produce
        expected_alt = "0 8px 24px rgba(0, 0, 0, 0.06)"
        assert normalized in (expected, expected_alt), (
            f"Expected --shadow-main to be '{expected}' (or '{expected_alt}') "
            f"but got '{value}'. "
            "The light theme shadow token is missing or incorrect in globals.css."
        )
