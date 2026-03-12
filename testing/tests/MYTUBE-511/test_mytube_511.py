"""
MYTUBE-511: Custom select chevron — SVG data URI is used for dropdown icon.

Objective
---------
Verify the select input on the upload page uses the custom branded chevron
(SVG data URI via CSS ``background-image``) instead of the browser default.

Steps
-----
1. Navigate to the /upload page (log in first if required).
2. Locate the category selection dropdown (``select[id="categoryId"]``).
3. Inspect the CSS ``background-image`` property for the select element.

Expected Result
---------------
- The ``appearance`` CSS property is ``none`` (browser default chevron suppressed).
- The ``background-image`` property starts with ``url("data:image/svg+xml`` (custom SVG).

Architecture
------------
- WebConfig from testing/core/config/web_config.py for env-based config.
- LoginPage / UploadPage page objects from testing/components/pages/.
- Playwright sync API with ``evaluate`` for CSS property inspection.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.upload_page.upload_page import UploadPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_AUTH_RESOLVE_TIMEOUT = 20_000  # ms

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

        if config.test_email and config.test_password:
            login_page = LoginPage(page)
            login_page.navigate(config.login_url())
            login_page.login_as(config.test_email, config.test_password)
            page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=_AUTH_RESOLVE_TIMEOUT,
            )

        upload = UploadPage(page)
        upload.navigate(config.base_url)

        yield page
        browser.close()


@pytest.fixture(scope="module")
def upload_page(browser_page: Page) -> UploadPage:
    return UploadPage(browser_page)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCustomSelectChevron:
    """MYTUBE-511: Category select uses custom SVG chevron via background-image."""

    def test_category_select_is_present(self, upload_page: UploadPage) -> None:
        """Step 2: The category select dropdown must be visible on the upload page."""
        page = upload_page._page
        select = page.locator(UploadPage._CATEGORY_SELECT)
        assert select.count() > 0, (
            "Category select element (select[id='categoryId']) not found on the upload page. "
            f"Current URL: {page.url}"
        )
        select.first.wait_for(state="visible", timeout=5_000)

    def test_category_select_has_svg_data_uri_background_image(
        self, upload_page: UploadPage
    ) -> None:
        """Step 3: CSS background-image must be a custom SVG data URI."""
        page = upload_page._page
        select = page.locator(UploadPage._CATEGORY_SELECT).first
        select.wait_for(state="visible", timeout=5_000)

        styles: dict = select.evaluate(
            """(el) => {
                const s = window.getComputedStyle(el);
                return {
                    backgroundImage: s.backgroundImage,
                    appearance: s.appearance,
                    webkitAppearance: s.webkitAppearance,
                };
            }"""
        )

        bg_image: str = styles.get("backgroundImage", "")
        appearance: str = styles.get("appearance", "")
        webkit_appearance: str = styles.get("webkitAppearance", "")

        assert "data:image/svg+xml" in bg_image, (
            "Expected the category select's CSS background-image to contain an "
            "SVG data URI (custom branded chevron), but it does not.\n"
            f"  Actual background-image : '{bg_image}'\n"
            f"  Expected                : contains 'data:image/svg+xml'\n"
            f"  Current URL             : {page.url}"
        )

    def test_category_select_hides_browser_default_chevron(
        self, upload_page: UploadPage
    ) -> None:
        """Step 3: CSS appearance must be 'none' to suppress the browser default chevron."""
        page = upload_page._page
        select = page.locator(UploadPage._CATEGORY_SELECT).first
        select.wait_for(state="visible", timeout=5_000)

        styles: dict = select.evaluate(
            """(el) => {
                const s = window.getComputedStyle(el);
                return {
                    appearance: s.appearance,
                    webkitAppearance: s.webkitAppearance,
                };
            }"""
        )

        appearance: str = styles.get("appearance", "")
        webkit_appearance: str = styles.get("webkitAppearance", "")

        assert appearance == "none" or webkit_appearance == "none", (
            "Expected the category select's CSS appearance to be 'none' "
            "(to hide the browser default dropdown chevron), but it is not.\n"
            f"  Actual appearance         : '{appearance}'\n"
            f"  Actual -webkit-appearance : '{webkit_appearance}'\n"
            f"  Expected                  : 'none' (in either property)\n"
            f"  Current URL               : {page.url}"
        )
