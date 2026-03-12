"""
MYTUBE-494: Hero 'Browse Library' button accessibility — focus and activation
via keyboard triggers smooth scroll to video grid.

Objective
---------
Verify that the "Browse Library" button is keyboard-accessible and that pressing
Enter while it is focused triggers the smooth scroll animation to the video grid.

Steps
-----
1. Navigate to the homepage.
2. Press the Tab key to navigate through the page elements until the "Browse Library"
   button is focused.
3. Verify the button has a visible focus state (:focus-visible).
4. Press the Enter key.

Expected Result
---------------
The button receives focus correctly and has a visible focus indicator; pressing Enter
triggers a smooth scroll animation that positions the viewport at the top of the
video grid section (scrollY increases and the video grid section is near the viewport).

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- HomePage from testing/components/pages/home_page/home_page.py encapsulates all
  selectors, keyboard helpers, and interaction methods.
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

_PAGE_LOAD_TIMEOUT = 30_000   # ms
_SCROLL_WAIT_MS = 1_500       # ms — allow smooth-scroll animation to finish
_MAX_TABS = 40                # safety limit for tab navigation


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

class TestHeroBrowseLibraryKeyboardAccessibility:
    """MYTUBE-494: Browse Library button is keyboard-focusable and Enter triggers scroll."""

    def test_browse_library_button_exists(self, home: HomePage) -> None:
        """Pre-condition: the 'Browse Library' button must be present on the page."""
        btn = home.browse_library_button()
        assert btn.count() > 0, (
            "No 'Browse Library' button (button or anchor) found on the homepage. "
            "The hero section CTA was not rendered. "
            f"Page URL: {home.current_url()}"
        )
        btn.first.wait_for(state="visible", timeout=5_000)

    def test_browse_library_button_keyboard_focus_and_scroll(
        self, home: HomePage
    ) -> None:
        """
        Steps 2-4: Tab to 'Browse Library', verify focus-visible state, press Enter,
        and confirm scroll to video grid.

        Strategy:
          - Scroll to top to get a clean baseline.
          - Reset focus to document start (body).
          - Tab through page elements until 'Browse Library' gains focus (up to _MAX_TABS).
          - Assert the focused element matches :focus-visible.
          - Record scrollY, press Enter, wait for scroll animation.
          - Assert scrollY increased (page scrolled down).
          - Assert video grid section is within or near the visible viewport.
        """
        # Scroll to top and reset focus so tab order starts from the beginning
        home.scroll_to_top()
        home.reset_focus_to_document_start()

        # Tab to the "Browse Library" button
        found = home.tab_to_element_with_text("Browse Library", max_tabs=_MAX_TABS)
        assert found, (
            f"Could not reach the 'Browse Library' button via Tab key "
            f"within {_MAX_TABS} presses. "
            "The button may not be in the natural tab order or may be missing from the page. "
            f"Page URL: {home.current_url()}"
        )

        # Step 3: Verify visible focus state
        focus_info = home.get_focused_element_info()
        assert focus_info.get("focusVisible", False), (
            "The 'Browse Library' button does not have a visible focus state "
            "(:focus-visible does not match). "
            f"Focused element: tag={focus_info.get('tagName')!r}, "
            f"text={focus_info.get('textContent')!r}, "
            f"outline-width={focus_info.get('outlineWidth')!r}, "
            f"outline-style={focus_info.get('outlineStyle')!r}. "
            "Expected the button to be styled with a visible focus indicator when "
            "reached via keyboard navigation."
        )

        # Record scroll position before pressing Enter
        initial_scroll_y = home.current_scroll_y()

        # Step 4: Press Enter to activate the button
        home.press_enter()

        # Wait for smooth-scroll animation to complete
        home.wait_for_scroll_animation(_SCROLL_WAIT_MS)

        final_scroll_y = home.current_scroll_y()

        # Assert the page scrolled down
        assert final_scroll_y > initial_scroll_y, (
            f"Page did not scroll after pressing Enter on the 'Browse Library' button. "
            f"Initial scrollY={initial_scroll_y}, Final scrollY={final_scroll_y}. "
            "Expected the viewport to scroll down to the video grid section."
        )

        # Assert video grid section is near the viewport top
        grid_section = home.video_grid_section().first
        assert grid_section.is_visible() or grid_section.count() > 0, (
            "Video grid section not found on page after keyboard-triggered scroll. "
            "Expected a section with aria-labelledby='recently-uploaded-heading' "
            "or 'most-viewed-heading' or id='video-grid' to be present."
        )

        viewport_height = home.viewport_height()
        bbox = grid_section.bounding_box()
        assert bbox is not None, (
            "Could not get bounding box of the video grid section. "
            "The section may not be rendered or visible."
        )
        section_top = bbox["y"]

        assert -viewport_height <= section_top <= viewport_height * 1.5, (
            f"Video grid section is not near the viewport after keyboard-activated scroll. "
            f"Section bounding box top: {section_top}px (relative to viewport). "
            f"Viewport height: {viewport_height}px. "
            "Expected the section to be positioned at or near the top of the viewport "
            "after pressing Enter on the 'Browse Library' button."
        )
