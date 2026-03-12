"""
MYTUBE-506: Upload page responsive layout — 2-column grid collapses on mobile.

Objective
---------
Verify the upload page implements a two-column workspace layout on desktop that
collapses to a single column on mobile viewports.

Steps
-----
1. View the page on a desktop viewport (width > 1024px).
2. Inspect the outer container CSS properties.
3. Resize the viewport to mobile width (e.g., 375px).

Expected Result
---------------
* On desktop: The layout is a CSS grid with two columns
  (left: 280px–330px, right: flexible) and a 20px gap.
* On mobile: The grid collapses to a single column where the upload card and
  library area stack vertically.

Test Approach
-------------
The upload page (``/upload``) requires authentication.  To verify the CSS grid
rules in isolation — independent of auth state — a self-contained HTML fixture
is served locally via Python's ``http.server`` (encapsulated in the
UploadLayoutPage component).  That fixture replicates the CSS declared in
``web/src/app/upload/upload.module.css``.

Architecture
------------
- WebConfig from testing/core/config/web_config.py is used for browser settings
  (headless, slow_mo).
- UploadLayoutPage from testing/components/pages/upload_page/upload_layout_page.py
  encapsulates the HTML fixture server, viewport setup, and all CSS
  computed-style retrieval.
- Tests use only semantic methods from the component; no raw Playwright APIs in
  test code.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.upload_page.upload_layout_page import (
    UploadLayoutPage,
    start_fixture_server,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DESKTOP_WIDTH = 1280
_DESKTOP_HEIGHT = 720
_MOBILE_WIDTH = 375
_MOBILE_HEIGHT = 812
_PAGE_LOAD_TIMEOUT = 15_000  # ms


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def fixture_server_url():
    """Start the local HTML fixture server and yield its URL."""
    server, url = start_fixture_server()
    yield url
    server.shutdown()


@pytest.fixture(scope="module")
def playwright_instance():
    """Single Playwright instance shared across all module-scoped browser fixtures."""
    pw = sync_playwright().start()
    yield pw
    pw.stop()


@pytest.fixture(scope="module")
def desktop_layout(
    playwright_instance, config: WebConfig, fixture_server_url: str
) -> UploadLayoutPage:
    """UploadLayoutPage loaded at desktop viewport (1280 × 720)."""
    browser = playwright_instance.chromium.launch(
        headless=config.headless, slow_mo=config.slow_mo
    )
    page = browser.new_page(viewport={"width": _DESKTOP_WIDTH, "height": _DESKTOP_HEIGHT})
    page.goto(fixture_server_url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="load")
    yield UploadLayoutPage(page)
    browser.close()


@pytest.fixture(scope="module")
def mobile_layout(
    playwright_instance, config: WebConfig, fixture_server_url: str
) -> UploadLayoutPage:
    """UploadLayoutPage loaded at mobile viewport (375 × 812)."""
    browser = playwright_instance.chromium.launch(
        headless=config.headless, slow_mo=config.slow_mo
    )
    page = browser.new_page(viewport={"width": _MOBILE_WIDTH, "height": _MOBILE_HEIGHT})
    page.goto(fixture_server_url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="load")
    yield UploadLayoutPage(page)
    browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUploadPageResponsiveLayout:
    """MYTUBE-506: Upload workspace grid collapses on mobile."""

    def test_desktop_two_column_grid(self, desktop_layout: UploadLayoutPage) -> None:
        """
        Step 1–2: On a desktop viewport (1280 × 720) the workspace container
        must be a CSS grid with two columns (left ≈ 280–330 px, right flexible)
        and a 20 px column gap.
        """
        styles = desktop_layout.get_workspace_styles()

        # 1. Must be a grid
        assert styles.display == "grid", (
            f"Expected display:grid on desktop, got '{styles.display}'. "
        )

        # 2. Must have exactly 2 column tracks
        # The browser resolves minmax(280px, 330px) to a pixel value (330px at 1280px
        # wide viewport) and minmax(0, 1fr) to the remaining space.
        assert styles.column_count == 2, (
            f"Expected 2 column tracks on desktop but got {styles.column_count}: "
            f"'{styles.grid_template_columns}'. "
            "The workspace CSS should declare: "
            "grid-template-columns: minmax(280px, 330px) minmax(0, 1fr)."
        )

        # 3. Left column must be within the 280–330 px clamped range
        left_col_raw = styles.grid_template_columns.split()[0]
        assert left_col_raw.endswith("px"), (
            f"Left column track '{left_col_raw}' is not a pixel value."
        )
        left_col_px = float(left_col_raw[:-2])
        assert 280 <= left_col_px <= 330, (
            f"Left column width {left_col_px}px is outside the expected 280–330 px range. "
            "CSS rule: grid-template-columns: minmax(280px, 330px) minmax(0, 1fr)."
        )

        # 4. Column gap must be 20 px
        assert styles.column_gap == "20px", (
            f"Expected column-gap 20px on desktop, got '{styles.column_gap}'. "
            "CSS rule: gap: 20px."
        )

    def test_mobile_single_column_grid(self, mobile_layout: UploadLayoutPage) -> None:
        """
        Step 3: On a mobile viewport (375 × 812) the workspace grid must
        collapse to a single column (grid-template-columns: 1fr).

        The media query in upload.module.css fires at max-width: 639px, so a
        375 px wide viewport must trigger it.
        """
        styles = mobile_layout.get_workspace_styles()

        # Must still be a grid (display doesn't change)
        assert styles.display == "grid", (
            f"Expected display:grid on mobile, got '{styles.display}'."
        )

        # Must have exactly 1 column track
        assert styles.column_count == 1, (
            f"Expected 1 column track on mobile (375 px) but got {styles.column_count}: "
            f"'{styles.grid_template_columns}'. "
            "The @media (max-width: 639px) rule should set grid-template-columns: 1fr."
        )

        # The single track must fill the full viewport width (≈ 375 px minus padding)
        single_col_raw = styles.grid_template_columns.split()[0]
        assert single_col_raw.endswith("px"), (
            f"Mobile single column track '{single_col_raw}' is not a pixel value."
        )
        single_col_px = float(single_col_raw[:-2])
        # Container has 20 px left + right padding so inner width ≈ 335 px; just
        # ensure it's > 300 px and close to the viewport width.
        assert single_col_px > 300, (
            f"Mobile single column track {single_col_px}px seems too narrow. "
            "Expected the column to span most of the 375 px viewport width."
        )

    def test_mobile_upload_card_stacks_above_library(
        self, mobile_layout: UploadLayoutPage
    ) -> None:
        """
        Verify that on mobile the upload card appears above the library area
        (DOM order preserved: upload-card comes before library-area in the column).

        This test checks the actual rendered bounding box positions to confirm
        vertical stacking without overlap.
        """
        card_bounds = mobile_layout.get_element_bounds("upload-card")
        library_bounds = mobile_layout.get_element_bounds("library-area")

        assert card_bounds is not None, "Upload card element not found in the DOM."
        assert library_bounds is not None, "Library area element not found in the DOM."

        # On single-column layout upload card should be above library area
        assert card_bounds.top < library_bounds.top, (
            f"Upload card top ({card_bounds.top}px) is NOT above library area "
            f"top ({library_bounds.top}px) on mobile. "
            "Expected the upload card to stack vertically above the library area."
        )

        # Both elements should share roughly the same left edge (same column)
        assert abs(card_bounds.left - library_bounds.left) < 5, (
            f"Upload card left ({card_bounds.left}px) and library area left "
            f"({library_bounds.left}px) differ by more than 5 px on mobile. "
            "Both children should be in the same single column."
        )
