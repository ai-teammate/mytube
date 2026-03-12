"""
MYTUBE-432: Verify font stack — Inter font is imported and applied to the document

Objective
---------
Ensure that the Inter font family is successfully imported and set as the primary
font for the application.

Steps
-----
1. Open the application and inspect the html or body element.
2. Check the font-family property in the Computed styles tab.
3. Open the Network tab and filter by "Font" to check for Inter font files or
   the Google Fonts CSS import.

Expected Result
---------------
font-family is correctly set to "Inter", "Roboto", "Open Sans", sans-serif.
The Inter font (weights 400-800) is successfully loaded from the external or
local source.

Test Approach
-------------
Playwright navigates to the deployed app and:
  1. Verifies the --font-inter CSS variable is set on the <html> element.
  2. Verifies the computed font-family on <body> contains the expected fallback
     fonts ("Roboto", "Open Sans", sans-serif) — confirming globals.css was applied.
  3. Verifies the Inter font face is available via document.fonts (weights 400,
     500, 600, 700, 800) — confirming the font was loaded from the source.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_FONT_LOAD_TIMEOUT = 15_000   # ms — document.fonts.ready

# Next.js next/font/google uses weights as specified in layout.tsx
_EXPECTED_INTER_WEIGHTS = ["400", "500", "600", "700", "800"]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        page = browser.new_page()
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
        # Wait for fonts to finish loading
        page.evaluate("() => document.fonts.ready")
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestInterFontStack:
    """MYTUBE-432: Inter font is imported and applied to the document."""

    def test_font_inter_css_variable_is_set(self, browser_page: Page) -> None:
        """
        Step 1 — Inspect the <html> element.
        The --font-inter CSS variable must be set and non-empty, confirming that
        layout.tsx applied the next/font Inter variable class to <html>.
        """
        css_var = browser_page.evaluate(
            "() => getComputedStyle(document.documentElement)"
            ".getPropertyValue('--font-inter').trim()"
        )
        assert css_var, (
            "CSS variable --font-inter is empty or not set on the <html> element. "
            "layout.tsx must add the Inter font variable class to the <html> element "
            "so that globals.css can resolve var(--font-inter)."
        )

    def test_body_font_family_contains_fallback_fonts(self, browser_page: Page) -> None:
        """
        Step 2 — Check font-family property in Computed styles.
        The computed font-family on <body> must include the expected fallback chain:
        'Roboto', 'Open Sans', and the generic 'sans-serif' — matching the declaration
        in globals.css: var(--font-inter), "Roboto", "Open Sans", sans-serif.
        """
        computed_ff = browser_page.evaluate(
            "() => getComputedStyle(document.body).fontFamily"
        )
        assert computed_ff, (
            f"Computed font-family on <body> is empty. Got: '{computed_ff}'"
        )
        assert "Roboto" in computed_ff, (
            f"'Roboto' not found in computed font-family. "
            f"Expected globals.css fallback chain. Got: '{computed_ff}'"
        )
        assert "Open Sans" in computed_ff, (
            f"'Open Sans' not found in computed font-family. "
            f"Expected globals.css fallback chain. Got: '{computed_ff}'"
        )

    def test_inter_font_declared_for_all_required_weights(self, browser_page: Page) -> None:
        """
        Step 3 — Check Network tab for Font resources.
        The document.fonts FontFaceSet is enumerated to verify that the Inter font
        face is *declared* (registered) for each required weight (400–800).
        A browser performs lazy font loading, so 'unloaded' is acceptable — what
        matters is that the @font-face rules for every weight were imported and
        registered.  This confirms the font was successfully imported from the
        external or local source.
        """
        declared_weights: set[str] = browser_page.evaluate(
            """() => {
                const weights = new Set();
                document.fonts.forEach(face => {
                    if (face.family === 'Inter') {
                        weights.add(face.weight);
                    }
                });
                return Array.from(weights);
            }"""
        )
        # Normalise to strings for comparison
        declared_set = set(str(w) for w in declared_weights)

        missing_weights = [w for w in _EXPECTED_INTER_WEIGHTS if w not in declared_set]
        assert not missing_weights, (
            f"Inter font @font-face rules are NOT declared for weights: {missing_weights}. "
            f"Declared weights found: {sorted(declared_set)}. "
            f"layout.tsx must import Inter with weights [400, 500, 600, 700, 800] via "
            "next/font/google so all @font-face rules are registered in document.fonts. "
            "Verify the next/font Inter import in src/app/layout.tsx."
        )
