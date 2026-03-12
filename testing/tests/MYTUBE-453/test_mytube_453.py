"""
MYTUBE-453: Hero CTA Browse Library — clicking button triggers smooth scroll to video grid

Objective
---------
Verify that the "Browse Library" button in the hero section correctly scrolls the user
down to the content area (video grid section).

Steps
-----
1. Navigate to the homepage.
2. Click on the "Browse Library" ghost button in the hero section.

Expected Result
---------------
The page performs a smooth scroll animation, positioning the viewport at the top of
the video grid section.

Test Approach
-------------
Playwright navigates to the deployed app, waits for the page to fully load, then:
  1. Asserts the hero section and "Browse Library" button are present.
  2. Clicks the "Browse Library" button.
  3. Waits for the scroll animation to complete.
  4. Asserts the video grid section (recently-uploaded-heading or most-viewed-heading)
     is within the visible viewport — confirming the scroll happened.
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
_SCROLL_WAIT_MS = 1_500       # ms — allow smooth-scroll animation to finish

# Selectors
_BROWSE_LIBRARY_BUTTON = "button:has-text('Browse Library'), a:has-text('Browse Library')"
_VIDEO_GRID_SECTION = (
    "section[aria-labelledby='recently-uploaded-heading'], "
    "section[aria-labelledby='most-viewed-heading'], "
    "[id='video-grid'], "
    "[data-testid='video-grid']"
)


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
        # Use a standard viewport that forces vertical scrolling
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHeroCtaBrowseLibrary:
    """MYTUBE-453: Browse Library CTA triggers smooth scroll to video grid."""

    def test_browse_library_button_is_present(self, browser_page: Page) -> None:
        """
        Pre-condition: the "Browse Library" ghost button must exist in the hero section.
        This confirms the hero section has been rendered and contains the CTA button.
        """
        btn = browser_page.locator(_BROWSE_LIBRARY_BUTTON)
        assert btn.count() > 0, (
            "No 'Browse Library' button (button or anchor) found on the homepage. "
            "The hero section CTA was not rendered. "
            f"Page URL: {browser_page.url}"
        )
        btn.first.wait_for(state="visible", timeout=5_000)

    def test_browse_library_click_scrolls_to_video_grid(self, browser_page: Page) -> None:
        """
        Step 2: clicking "Browse Library" must scroll the viewport down to the
        video grid section.

        Verification strategy:
          - Record initial scroll position (should be near 0 for a fresh load).
          - Click "Browse Library".
          - Wait for the scroll animation to complete.
          - Assert that the scroll position has increased (page scrolled down).
          - Assert that the video grid section's top edge is now within or near
            the visible viewport — confirming the scroll target is correct.
        """
        # Scroll back to top before this assertion test to get a clean baseline
        browser_page.evaluate("window.scrollTo(0, 0)")
        browser_page.wait_for_timeout(300)

        initial_scroll_y: int = browser_page.evaluate("window.scrollY")

        # Click "Browse Library"
        btn = browser_page.locator(_BROWSE_LIBRARY_BUTTON).first
        btn.click()

        # Wait for smooth-scroll to finish
        browser_page.wait_for_timeout(_SCROLL_WAIT_MS)

        final_scroll_y: int = browser_page.evaluate("window.scrollY")

        assert final_scroll_y > initial_scroll_y, (
            f"Page did not scroll after clicking 'Browse Library'. "
            f"Initial scrollY={initial_scroll_y}, Final scrollY={final_scroll_y}. "
            "Expected the viewport to scroll down to the video grid section."
        )

        # Verify the video grid section is visible / near the viewport top
        grid_section = browser_page.locator(_VIDEO_GRID_SECTION).first
        assert grid_section.count() > 0 or grid_section.is_visible(), (
            "Video grid section not found on page after scroll. "
            "Expected a section with aria-labelledby='recently-uploaded-heading' "
            "or 'most-viewed-heading' to be present."
        )

        # Check that the section bounding box top is close to the viewport top
        viewport_height: int = browser_page.evaluate("window.innerHeight")
        section_top: float = grid_section.bounding_box()["y"]

        # The section top should be within 1.5 viewport heights of the current
        # viewport top (i.e. it is visible or just above/below it after scrolling)
        assert -viewport_height <= section_top <= viewport_height * 1.5, (
            f"Video grid section is not near the viewport after scrolling. "
            f"Section bounding box top: {section_top}px (relative to viewport). "
            f"Viewport height: {viewport_height}px. "
            "Expected the section to be positioned at or near the top of the viewport "
            "after the 'Browse Library' button scroll."
        )
