"""
MYTUBE-499: SiteHeader nav links — styling and hover transitions applied

Objective
---------
Ensure navigation links in the header follow the specified typography and
interaction patterns.

Steps
-----
1. Locate the .nav-links section in the SiteHeader.
2. Observe the default state of "Home" and "My Videos" links.
3. Hover the mouse over the links.

Expected Result
---------------
Links have a font-size of 16px and use color: var(--text-secondary). On hover,
an underline transition effect is visible.

Architecture
------------
Layer A — Source code inspection (no browser required):
    Reads web/src/components/SiteHeader.tsx and confirms that nav links carry
    the `text-base` Tailwind class (= 16px), `style={{ color: "var(--text-secondary)" }}`,
    and `hover:underline` for the hover underline transition.

Layer B — Playwright computed-style validation (browser required):
    Navigates to the homepage, reads computed CSS for both nav-link elements,
    and asserts font-size == 16px and color matches the --text-secondary token.
    Also triggers a hover and checks that text-decoration-line becomes "underline".

Run from repo root:
    pytest testing/tests/MYTUBE-499/test_mytube_499.py -v
"""
from __future__ import annotations

import os
import re
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.css_globals_page.css_globals_page import CSSGlobalsPage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_SITE_HEADER_TSX = os.path.join(_REPO_ROOT, "web", "src", "components", "SiteHeader.tsx")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_EXPECTED_FONT_SIZE_PX = 16.0

# Selector for the primary nav links in the header
_NAV_LINKS_SELECTOR = "header nav[aria-label='Primary navigation'] a"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_source(path: str) -> str:
    """Read a source file, raising a clear error if it is missing."""
    if not os.path.isfile(path):
        pytest.fail(f"Source file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def css() -> CSSGlobalsPage:
    return CSSGlobalsPage()


@pytest.fixture(scope="module")
def site_header_source() -> str:
    return _read_source(_SITE_HEADER_TSX)


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo,
        )
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        page.goto(config.home_url(), timeout=_PAGE_LOAD_TIMEOUT, wait_until="networkidle")
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Layer A: Source code inspection
# ---------------------------------------------------------------------------


class TestNavLinksSourceInspection:
    """Layer A — confirm styling classes are present in SiteHeader.tsx source."""

    def test_nav_links_use_text_base_class(self, site_header_source: str) -> None:
        """
        Step 2 (source): The nav links must carry the 'text-base' Tailwind class,
        which maps to font-size: 1rem = 16px.
        """
        # Match a Link element in the primary nav that has text-base in className
        pattern = re.compile(
            r'aria-label="Primary navigation".*?text-base',
            re.DOTALL,
        )
        assert pattern.search(site_header_source), (
            "Could not find 'text-base' class on nav links within "
            "aria-label='Primary navigation' in SiteHeader.tsx. "
            "The 16px font-size styling may be missing."
        )

    def test_nav_links_use_text_secondary_color(self, site_header_source: str) -> None:
        """
        Step 2 (source): The nav links must use color: var(--text-secondary).
        """
        pattern = re.compile(
            r'aria-label="Primary navigation".*?color:\s*"var\(--text-secondary\)"',
            re.DOTALL,
        )
        assert pattern.search(site_header_source), (
            "Could not find style={{ color: \"var(--text-secondary)\" }} on nav links "
            "within aria-label='Primary navigation' in SiteHeader.tsx."
        )

    def test_nav_links_have_hover_underline(self, site_header_source: str) -> None:
        """
        Step 3 (source): The nav links must carry 'hover:underline' Tailwind class
        to apply the underline transition effect on hover.
        """
        pattern = re.compile(
            r'aria-label="Primary navigation".*?hover:underline',
            re.DOTALL,
        )
        assert pattern.search(site_header_source), (
            "Could not find 'hover:underline' class on nav links within "
            "aria-label='Primary navigation' in SiteHeader.tsx. "
            "The hover underline transition may be missing."
        )

    def test_nav_links_have_transition_class(self, site_header_source: str) -> None:
        """
        Step 3 (source): The nav links must carry a 'transition-' class for the
        smooth underline transition effect.
        """
        pattern = re.compile(
            r'aria-label="Primary navigation".*?transition-',
            re.DOTALL,
        )
        assert pattern.search(site_header_source), (
            "Could not find a 'transition-' class on nav links within "
            "aria-label='Primary navigation' in SiteHeader.tsx. "
            "The CSS transition for hover effect may be missing."
        )

    def test_text_secondary_token_defined_in_css(self, css: CSSGlobalsPage) -> None:
        """
        Step 2 (CSS): The --text-secondary design token must be defined in globals.css.
        """
        value = css.get_light_token("--text-secondary")
        assert value, (
            "--text-secondary token is not defined in the :root block of globals.css."
        )


# ---------------------------------------------------------------------------
# Layer B: Playwright computed-style validation
# ---------------------------------------------------------------------------


class TestNavLinksComputedStyles:
    """Layer B — browser-level validation of computed CSS properties."""

    def test_nav_links_are_present(self, browser_page: Page) -> None:
        """
        Step 1: The primary nav section with 'Home' and 'My Videos' links must
        be visible in the header.
        """
        locator = browser_page.locator(_NAV_LINKS_SELECTOR)
        count = locator.count()
        assert count >= 2, (
            f"Expected at least 2 nav links in header primary navigation, found {count}. "
            f"Selector: '{_NAV_LINKS_SELECTOR}', Page URL: {browser_page.url}"
        )

    def test_home_link_font_size_is_16px(self, browser_page: Page) -> None:
        """
        Step 2: The 'Home' link computed font-size must be exactly 16px.
        """
        home_link = browser_page.locator(_NAV_LINKS_SELECTOR).first
        home_link.wait_for(state="visible", timeout=5_000)
        raw_size: str = home_link.evaluate("el => window.getComputedStyle(el).fontSize")
        assert raw_size, (
            f"Could not read computed font-size for the first nav link. "
            f"Selector: '{_NAV_LINKS_SELECTOR}'"
        )
        numeric_size = float(raw_size.replace("px", "").strip())
        assert numeric_size == _EXPECTED_FONT_SIZE_PX, (
            f"'Home' nav link font-size mismatch. "
            f"Expected: {_EXPECTED_FONT_SIZE_PX}px, Got: {raw_size}"
        )

    def test_my_videos_link_font_size_is_16px(self, browser_page: Page) -> None:
        """
        Step 2: The 'My Videos' link computed font-size must be exactly 16px.
        """
        links = browser_page.locator(_NAV_LINKS_SELECTOR)
        assert links.count() >= 2, (
            f"Expected at least 2 nav links, found {links.count()}."
        )
        my_videos_link = links.nth(1)
        my_videos_link.wait_for(state="visible", timeout=5_000)
        raw_size: str = my_videos_link.evaluate("el => window.getComputedStyle(el).fontSize")
        numeric_size = float(raw_size.replace("px", "").strip())
        assert numeric_size == _EXPECTED_FONT_SIZE_PX, (
            f"'My Videos' nav link font-size mismatch. "
            f"Expected: {_EXPECTED_FONT_SIZE_PX}px, Got: {raw_size}"
        )

    def test_home_link_color_uses_text_secondary(self, browser_page: Page, css: CSSGlobalsPage) -> None:
        """
        Step 2: The 'Home' link computed color must resolve to the value of
        --text-secondary from the design token.
        """
        home_link = browser_page.locator(_NAV_LINKS_SELECTOR).first
        home_link.wait_for(state="visible", timeout=5_000)
        computed_color: str = home_link.evaluate("el => window.getComputedStyle(el).color")
        assert computed_color, (
            f"Could not read computed color for the 'Home' nav link. "
            f"Selector: '{_NAV_LINKS_SELECTOR}'"
        )
        # Verify that var(--text-secondary) is applied as inline style
        inline_color: str = home_link.evaluate("el => el.style.color")
        assert "var(--text-secondary)" in inline_color or "text-secondary" in inline_color, (
            f"'Home' nav link does not use var(--text-secondary) as inline style. "
            f"Got inline style color: '{inline_color}', computed color: '{computed_color}'"
        )

    def test_home_link_hover_shows_underline(self, browser_page: Page) -> None:
        """
        Step 3: Hovering over the 'Home' link must apply text-decoration: underline.
        """
        home_link = browser_page.locator(_NAV_LINKS_SELECTOR).first
        home_link.wait_for(state="visible", timeout=5_000)
        # Hover over the link
        home_link.hover()
        # Check that text-decoration-line becomes "underline" after hover
        text_decoration: str = home_link.evaluate(
            "el => window.getComputedStyle(el).textDecorationLine"
        )
        assert text_decoration == "underline", (
            f"'Home' nav link should show underline on hover. "
            f"Expected text-decoration-line: 'underline', Got: '{text_decoration}'"
        )

    def test_my_videos_link_hover_shows_underline(self, browser_page: Page) -> None:
        """
        Step 3: Hovering over the 'My Videos' link must apply text-decoration: underline.
        """
        links = browser_page.locator(_NAV_LINKS_SELECTOR)
        my_videos_link = links.nth(1)
        my_videos_link.wait_for(state="visible", timeout=5_000)
        my_videos_link.hover()
        text_decoration: str = my_videos_link.evaluate(
            "el => window.getComputedStyle(el).textDecorationLine"
        )
        assert text_decoration == "underline", (
            f"'My Videos' nav link should show underline on hover. "
            f"Expected text-decoration-line: 'underline', Got: '{text_decoration}'"
        )
