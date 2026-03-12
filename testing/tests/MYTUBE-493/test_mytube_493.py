"""
MYTUBE-493: Homepage hero section rendering — 'Browse Library' button is visible
with ghost styling and correct text.

Objective
---------
Verify that the 'Browse Library' CTA button is correctly rendered in the hero section
with the specified text and ghost styling tokens.

Steps
-----
1. Navigate to the homepage: https://ai-teammate.github.io/mytube/
2. Locate the button or anchor element situated below the hero sub-text paragraph.
3. Verify that the button text is exactly "Browse Library".
4. Inspect the element's CSS properties to confirm it uses 'ghost' styling
   (transparent background, visible border, and a non-transparent text color).

Expected Result
---------------
The "Browse Library" button is present, displays the correct text, and adheres
to the design system's ghost styling specifications.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- HomePage from testing/components/pages/home_page/home_page.py encapsulates all
  selectors and interactions (component layer).
- Tests use only semantic methods from the component; no raw Playwright APIs in tests.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.home_page.home_page import HomePage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        yield page
        browser.close()


@pytest.fixture(scope="module")
def home(browser_page: Page) -> HomePage:
    return HomePage(browser_page)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBrowseLibraryButtonRendering:
    """MYTUBE-493: 'Browse Library' hero CTA button is visible, has correct text,
    and uses ghost styling tokens."""

    def test_browse_library_button_is_present(self, home: HomePage) -> None:
        """
        Step 2/3: The 'Browse Library' button or anchor must be present in the
        hero section and visible.
        """
        btn = home.browse_library_button()
        assert btn.count() > 0, (
            "No 'Browse Library' button (button or anchor) found on the homepage. "
            "The hero section CTA was not rendered. "
            f"Page URL: {home._page.url}"
        )
        btn.first.wait_for(state="visible", timeout=5_000)

    def test_browse_library_button_text_is_exact(self, home: HomePage) -> None:
        """
        Step 3: The button must display exactly the text 'Browse Library'.
        """
        btn = home.browse_library_button().first
        btn.wait_for(state="visible", timeout=5_000)
        actual_text = btn.inner_text().strip()
        assert actual_text == "Browse Library", (
            f"Button text mismatch. "
            f"Expected: 'Browse Library', "
            f"Actual: '{actual_text}'"
        )

    def test_browse_library_button_has_ghost_styling(self, home: HomePage) -> None:
        """
        Step 4: The button must use ghost styling:
          - Background is transparent (rgba(0,0,0,0) or 'transparent').
          - A visible border (border-color is not transparent).
          - Text color is not transparent.
        """
        btn_locator = home.browse_library_button().first
        btn_locator.wait_for(state="visible", timeout=5_000)

        styles: dict = btn_locator.evaluate(
            """(el) => {
                const s = window.getComputedStyle(el);
                return {
                    backgroundColor: s.backgroundColor,
                    borderColor: s.borderColor,
                    color: s.color,
                    borderTopWidth: s.borderTopWidth,
                    borderBottomWidth: s.borderBottomWidth,
                    borderLeftWidth: s.borderLeftWidth,
                    borderRightWidth: s.borderRightWidth,
                };
            }"""
        )

        assert styles is not None, (
            "Could not compute styles for 'Browse Library' button."
        )

        bg = styles["backgroundColor"]
        border_color = styles["borderColor"]
        text_color = styles["color"]
        border_widths = [
            styles["borderTopWidth"],
            styles["borderBottomWidth"],
            styles["borderLeftWidth"],
            styles["borderRightWidth"],
        ]

        # --- Ghost: background must be transparent ---
        assert bg in ("rgba(0, 0, 0, 0)", "transparent"), (
            f"Ghost styling check failed: background should be transparent. "
            f"Actual backgroundColor='{bg}'. "
            f"Expected 'rgba(0, 0, 0, 0)' or 'transparent'."
        )

        # --- Ghost: border must be visible (non-zero width and non-transparent color) ---
        has_border_width = any(
            w not in ("0px", "0", "") for w in border_widths
        )
        border_is_transparent = border_color in ("rgba(0, 0, 0, 0)", "transparent")

        assert has_border_width, (
            f"Ghost styling check failed: button has no visible border. "
            f"Border widths: top={border_widths[0]}, bottom={border_widths[1]}, "
            f"left={border_widths[2]}, right={border_widths[3]}. "
            "A ghost button must have a visible border."
        )
        assert not border_is_transparent, (
            f"Ghost styling check failed: border color is fully transparent. "
            f"Actual borderColor='{border_color}'. "
            "A ghost button must have a non-transparent border color."
        )

        # --- Ghost: text color must be visible (non-transparent) ---
        assert text_color not in ("rgba(0, 0, 0, 0)", "transparent"), (
            f"Ghost styling check failed: text color is fully transparent. "
            f"Actual color='{text_color}'. "
            "A ghost button must have a non-transparent text color."
        )
