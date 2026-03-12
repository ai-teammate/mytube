"""
MYTUBE-462: Auth page heading — text and typography match redesign

Objective
---------
Verify the specific heading text and typography on the redesigned auth pages.

Steps
-----
1. Navigate to the /login page.
2. Observe the main heading inside the auth card.

Expected Result
---------------
The heading text is "Welcome to MyTube" with a font-size of 22px and
font-weight of 700.
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

_PAGE_LOAD_TIMEOUT = 30_000  # ms

_EXPECTED_TEXT = "Welcome to MyTube"
_EXPECTED_FONT_SIZE_PX = 22
_EXPECTED_FONT_WEIGHT = 700

# The heading is an <h1> inside the login card
_HEADING_SELECTOR = "h1"


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def login_page_fixture(config: WebConfig):
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        page = browser.new_page()
        login_page = LoginPage(page)
        login_page.navigate(config.login_url())
        login_page.wait_for_form(timeout=_PAGE_LOAD_TIMEOUT)
        yield page
        browser.close()


class TestAuthPageHeading:
    """MYTUBE-462: Auth page heading text and typography match redesign."""

    def test_heading_text(self, login_page_fixture: Page) -> None:
        """The main heading on the login page must read 'Welcome to MyTube'."""
        page = login_page_fixture
        text: str = page.evaluate(
            f"""() => {{
                const el = document.querySelector('{_HEADING_SELECTOR}');
                return el ? (el.innerText || el.textContent || '').trim() : '';
            }}"""
        )
        assert text == _EXPECTED_TEXT, (
            f"Heading text mismatch. Expected: '{_EXPECTED_TEXT}', Got: '{text}'"
        )

    def test_heading_font_size(self, login_page_fixture: Page) -> None:
        """The heading's computed font-size must be exactly 22px."""
        page = login_page_fixture
        raw_font_size: str = page.evaluate(
            f"""() => {{
                const el = document.querySelector('{_HEADING_SELECTOR}');
                return el ? window.getComputedStyle(el).fontSize : '';
            }}"""
        )
        assert raw_font_size, (
            f"Could not read computed font-size for selector '{_HEADING_SELECTOR}'. "
            "The heading element may not be present in the DOM."
        )
        # Computed font-size is returned as e.g. "22px"
        numeric_size = float(raw_font_size.replace("px", "").strip())
        assert numeric_size == _EXPECTED_FONT_SIZE_PX, (
            f"Heading font-size mismatch. "
            f"Expected: {_EXPECTED_FONT_SIZE_PX}px, Got: {raw_font_size}"
        )

    def test_heading_font_weight(self, login_page_fixture: Page) -> None:
        """The heading's computed font-weight must be 700 (bold)."""
        page = login_page_fixture
        raw_font_weight: str = page.evaluate(
            f"""() => {{
                const el = document.querySelector('{_HEADING_SELECTOR}');
                return el ? window.getComputedStyle(el).fontWeight : '';
            }}"""
        )
        assert raw_font_weight, (
            f"Could not read computed font-weight for selector '{_HEADING_SELECTOR}'. "
            "The heading element may not be present in the DOM."
        )
        numeric_weight = int(raw_font_weight.strip())
        assert numeric_weight == _EXPECTED_FONT_WEIGHT, (
            f"Heading font-weight mismatch. "
            f"Expected: {_EXPECTED_FONT_WEIGHT}, Got: {raw_font_weight}"
        )
