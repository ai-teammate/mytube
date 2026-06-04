"""
MYTUBE-662: Legacy copy removal — 'personal video portal' is no longer present.

Objective
---------
Verify that the old positioning text "personal video portal" has been
completely removed from the homepage UI.

Steps
-----
1. Navigate to the homepage (/).
2. Search the rendered page text for the string "personal video portal".

Expected Result
---------------
No instances of the string "personal video portal" are found anywhere in
the rendered page content.

Architecture
------------
- WebConfig: base URL from environment variables.
- HomePage: page object for homepage navigation.
- Playwright: browser automation to verify rendered HTML content.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-662/test_mytube_662.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.home_page.home_page import HomePage

LEGACY_TEXT = "personal video portal"


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


def test_personal_video_portal_text_removed(config: WebConfig) -> None:
    """Verify 'personal video portal' is absent from the rendered homepage."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo,
        )
        page = browser.new_page()
        try:
            home = HomePage(page)
            home.navigate(config.base_url)

            # Capture the full rendered text content of the page body
            body_text = page.inner_text("body").lower()

            assert LEGACY_TEXT not in body_text, (
                f"Found legacy text '{LEGACY_TEXT}' on the homepage. "
                f"It should have been removed. "
                f"URL: {page.url}"
            )
        finally:
            browser.close()
