"""
MYTUBE-345: Navigate header using keyboard — focus moves correctly through links.

Objective
---------
Verify that the App Shell navigation is accessible via keyboard controls.

Steps
-----
1. Load the homepage.
2. Use the Tab key to cycle through the interactive elements in the header.

Expected Result
---------------
The focus moves logically from the logo, to the search input, then through
the navigation links (Home, Upload, etc.), with a visible focus indicator
for each element.

Test approach
-------------
Uses Playwright with a desktop viewport (1280 × 720) so that the desktop
navigation (Primary navigation nav) is visible.

For a guest (unauthenticated) user, the expected focus order within
SiteHeader is:
  1. Logo link  — first <a> in <header>, text "mytube"
  2. Search input — input[type="search"][aria-label="Search query"]
  3. Search submit button — button[aria-label="Submit search"]
  4. Home nav link — nav[aria-label="Primary navigation"] > first <a>

The test:
  - Presses Tab from the document body and tracks every element that
    receives focus inside <header>, up to a safety limit.
  - Asserts the four expected elements appear in the correct order.
  - For each, asserts that :focus-visible is true (browser confirms
    keyboard-triggered focus and that a focus indicator should be shown).
  - For elements that do not use outline:none, asserts the computed
    outline is not zero-width (default browser focus ring is intact).

Environment variables
---------------------
APP_URL / WEB_BASE_URL  Base URL of the deployed web app.
                        Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS     Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO      Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from typing import List, Optional

import pytest
from playwright.sync_api import sync_playwright, Page, expect

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000       # ms
_DESKTOP_VIEWPORT = {"width": 1280, "height": 720}
_MAX_TABS = 30                    # safety limit to avoid infinite loops

# Elements that deliberately remove the native outline in favour of an
# alternative indicator (e.g. border-blue-500 on focus).  We skip the
# outline-width assertion for these but still assert :focus-visible.
_OUTLINE_NONE_ARIA_LABELS = {"Search query"}


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------


@dataclass
class FocusedElementInfo:
    """Snapshot of a focused element's identity and focus-visible state."""

    tag_name: str
    aria_label: Optional[str]
    href: Optional[str]
    input_type: Optional[str]
    text_content: str
    focus_visible: bool
    outline_width: str         # getComputedStyle.outlineWidth
    outline_style: str         # getComputedStyle.outlineStyle
    in_primary_nav: bool       # True when inside nav[aria-label="Primary navigation"]
    in_header: bool


# ---------------------------------------------------------------------------
# Header keyboard-navigation page object
# ---------------------------------------------------------------------------


class SiteHeaderKeyboardPage:
    """Encapsulates keyboard navigation interactions with SiteHeader.

    Responsibilities:
      - Navigate to a URL and wait for the header to be hydrated.
      - Press Tab and capture the focused element's accessibility properties.
      - Collect all header-focused elements in tab order.
    """

    _HEADER_SELECTOR = "header"
    _PRIMARY_NAV_SELECTOR = "nav[aria-label='Primary navigation']"

    def __init__(self, page: Page) -> None:
        self._page = page

    def navigate(self, base_url: str) -> None:
        """Navigate to the homepage and wait for the header to appear."""
        url = f"{base_url.rstrip('/')}/"
        self._page.goto(url)
        self._page.wait_for_selector(self._HEADER_SELECTOR, timeout=_PAGE_LOAD_TIMEOUT)
        # Wait for React hydration (interactive elements must be clickable).
        self._page.wait_for_load_state("networkidle", timeout=_PAGE_LOAD_TIMEOUT)

    def reset_focus(self) -> None:
        """Blur any focused element and move focus to the document body so the
        next Tab press starts at the top of the natural tab order."""
        self._page.evaluate(
            "() => { "
            "  if (document.activeElement) document.activeElement.blur(); "
            "  document.body.setAttribute('tabindex', '-1'); "
            "  document.body.focus(); "
            "}"
        )

    def _capture_active_element(self) -> FocusedElementInfo:
        """Return a snapshot of the currently focused (active) element."""
        data = self._page.evaluate(
            """() => {
                const el = document.activeElement;
                if (!el || el === document.body || el === document.documentElement) {
                    return null;
                }
                const cs = window.getComputedStyle(el);
                const primaryNav = document.querySelector(
                    "nav[aria-label='Primary navigation']"
                );
                return {
                    tagName:      el.tagName.toLowerCase(),
                    ariaLabel:    el.getAttribute('aria-label'),
                    href:         el.getAttribute('href'),
                    inputType:    el.getAttribute('type'),
                    textContent:  (el.textContent || '').trim().substring(0, 100),
                    focusVisible: el.matches(':focus-visible'),
                    outlineWidth: cs.outlineWidth,
                    outlineStyle: cs.outlineStyle,
                    inHeader:     !!el.closest('header'),
                    inPrimaryNav: !!(primaryNav && primaryNav.contains(el)),
                };
            }"""
        )
        if not data:
            return FocusedElementInfo(
                tag_name="body", aria_label=None, href=None, input_type=None,
                text_content="", focus_visible=False,
                outline_width="0px", outline_style="none",
                in_primary_nav=False, in_header=False,
            )
        return FocusedElementInfo(
            tag_name=data["tagName"],
            aria_label=data.get("ariaLabel"),
            href=data.get("href"),
            input_type=data.get("inputType"),
            text_content=data.get("textContent", ""),
            focus_visible=data["focusVisible"],
            outline_width=data["outlineWidth"],
            outline_style=data["outlineStyle"],
            in_primary_nav=data["inPrimaryNav"],
            in_header=data["inHeader"],
        )

    def tab_once(self) -> FocusedElementInfo:
        """Press Tab one time and return the focused element's info."""
        self._page.keyboard.press("Tab")
        return self._capture_active_element()

    def collect_header_focus_sequence(self) -> List[FocusedElementInfo]:
        """Press Tab up to _MAX_TABS times and collect all elements focused
        inside <header>, stopping once focus leaves the header."""
        sequence: List[FocusedElementInfo] = []
        for _ in range(_MAX_TABS):
            info = self.tab_once()
            if not info.in_header:
                break
            sequence.append(info)
        return sequence

    def assert_header_visible(self) -> None:
        expect(self._page.locator(self._HEADER_SELECTOR)).to_be_visible()

    def assert_desktop_nav_visible(self) -> None:
        """Assert that the primary navigation nav is visible (desktop viewport)."""
        expect(self._page.locator(self._PRIMARY_NAV_SELECTOR)).to_be_visible()

    def take_screenshot(self, path: str) -> None:
        self._page.screenshot(path=path)


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig):
    with sync_playwright() as pw:
        br = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def header_page(browser, web_config: WebConfig) -> SiteHeaderKeyboardPage:
    """Return a SiteHeaderKeyboardPage navigated to the homepage."""
    context = browser.new_context(viewport=_DESKTOP_VIEWPORT)
    page = context.new_page()
    page.set_default_timeout(_PAGE_LOAD_TIMEOUT)
    kbd_page = SiteHeaderKeyboardPage(page)
    kbd_page.navigate(web_config.base_url)
    yield kbd_page
    context.close()


@pytest.fixture(scope="module")
def focus_sequence(header_page: SiteHeaderKeyboardPage) -> List[FocusedElementInfo]:
    """Collect the full header focus sequence once and share across all tests."""
    header_page.reset_focus()
    return header_page.collect_header_focus_sequence()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt(info: FocusedElementInfo) -> str:
    """Human-readable representation for assertion messages."""
    return (
        f"<{info.tag_name} "
        f"aria-label={info.aria_label!r} "
        f"href={info.href!r} "
        f"type={info.input_type!r} "
        f"text={info.text_content[:40]!r} "
        f"focus-visible={info.focus_visible} "
        f"outline={info.outline_style}/{info.outline_width}>"
    )


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestHeaderKeyboardNavigation:
    """MYTUBE-345: Keyboard navigation through the site header."""

    # ------------------------------------------------------------------
    # Step 1: page loads and header is visible
    # ------------------------------------------------------------------

    def test_header_is_visible(self, header_page: SiteHeaderKeyboardPage) -> None:
        """Step 1 — The homepage loads and the <header> element is visible."""
        header_page.assert_header_visible()

    def test_desktop_nav_is_rendered(self, header_page: SiteHeaderKeyboardPage) -> None:
        """The primary navigation nav is visible at desktop viewport width."""
        header_page.assert_desktop_nav_visible()

    # ------------------------------------------------------------------
    # Step 2: Tab key cycles through header elements
    # ------------------------------------------------------------------

    def test_at_least_four_header_elements_focusable(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """Tabbing through the header must reach at least 4 focusable elements
        (logo, search input, search button, Home link)."""
        assert len(focus_sequence) >= 4, (
            f"Expected at least 4 focusable elements inside <header>, "
            f"but only {len(focus_sequence)} received focus via Tab.\n"
            f"Elements found: {[_fmt(e) for e in focus_sequence]}"
        )

    def test_first_focused_element_is_logo_link(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """The first Tab stop in the header must be the logo link (mytube)."""
        assert focus_sequence, "No elements received focus inside <header>."
        first = focus_sequence[0]
        is_logo = (
            first.tag_name == "a"
            and "mytube" in first.text_content.lower()
        )
        assert is_logo, (
            "Expected the first header Tab stop to be the logo link "
            "(<a> with text containing 'mytube'), "
            f"but got: {_fmt(first)}"
        )

    def test_second_focused_element_is_search_input(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """The second Tab stop must be the search input."""
        assert len(focus_sequence) >= 2, (
            "Focus sequence has fewer than 2 elements; cannot check search input."
        )
        second = focus_sequence[1]
        is_search = (
            second.tag_name == "input"
            and second.input_type == "search"
        )
        assert is_search, (
            "Expected the second header Tab stop to be input[type='search'], "
            f"but got: {_fmt(second)}"
        )

    def test_third_focused_element_is_search_submit_button(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """The third Tab stop must be the search submit button."""
        assert len(focus_sequence) >= 3, (
            "Focus sequence has fewer than 3 elements; cannot check submit button."
        )
        third = focus_sequence[2]
        is_submit = (
            third.tag_name == "button"
            and third.input_type == "submit"
        )
        assert is_submit, (
            "Expected the third header Tab stop to be the search submit button "
            "(<button type='submit'>), "
            f"but got: {_fmt(third)}"
        )

    def test_fourth_focused_element_is_home_nav_link(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """The fourth Tab stop must be the Home link inside the primary nav."""
        assert len(focus_sequence) >= 4, (
            "Focus sequence has fewer than 4 elements; cannot check Home nav link."
        )
        fourth = focus_sequence[3]
        is_home_nav = (
            fourth.tag_name == "a"
            and fourth.in_primary_nav
        )
        assert is_home_nav, (
            "Expected the fourth header Tab stop to be the Home link "
            "(<a> inside nav[aria-label='Primary navigation']), "
            f"but got: {_fmt(fourth)}"
        )

    # ------------------------------------------------------------------
    # Expected result: visible focus indicator for each element
    # ------------------------------------------------------------------

    def test_logo_has_focus_visible(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """:focus-visible must be active when the logo receives keyboard focus."""
        assert focus_sequence, "No elements received focus inside <header>."
        logo = focus_sequence[0]
        assert logo.focus_visible, (
            "Logo link did not satisfy :focus-visible when focused via Tab. "
            "A visible keyboard focus indicator is required for accessibility.\n"
            f"Element: {_fmt(logo)}"
        )

    def test_search_input_has_focus_visible(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """:focus-visible must be active when the search input receives focus."""
        assert len(focus_sequence) >= 2
        inp = focus_sequence[1]
        assert inp.focus_visible, (
            "Search input did not satisfy :focus-visible when focused via Tab. "
            "A visible keyboard focus indicator is required (e.g. focus:border-blue-500).\n"
            f"Element: {_fmt(inp)}"
        )

    def test_search_button_has_focus_visible(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """:focus-visible must be active when the search submit button receives focus."""
        assert len(focus_sequence) >= 3
        btn = focus_sequence[2]
        assert btn.focus_visible, (
            "Search submit button did not satisfy :focus-visible when focused via Tab.\n"
            f"Element: {_fmt(btn)}"
        )

    def test_home_nav_link_has_focus_visible(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """:focus-visible must be active when the Home nav link receives focus."""
        assert len(focus_sequence) >= 4
        home = focus_sequence[3]
        assert home.focus_visible, (
            "Home nav link did not satisfy :focus-visible when focused via Tab.\n"
            f"Element: {_fmt(home)}"
        )

    def test_logo_has_visible_outline(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """The logo link must show a non-zero, non-transparent outline when focused.

        The logo uses the browser default focus ring (no focus:outline-none),
        so the computed outline width must be > 0.
        """
        assert focus_sequence
        logo = focus_sequence[0]
        # outline-style 'none' means no outline at all
        assert logo.outline_style != "none", (
            "Logo link has outline-style: none when focused via keyboard. "
            "This means the browser focus ring is suppressed with no alternative "
            "focus indicator provided.\n"
            f"Element: {_fmt(logo)}"
        )
        assert logo.outline_width not in ("0px", "0"), (
            "Logo link has outline-width: 0 when focused via keyboard. "
            "The visible focus ring is missing.\n"
            f"Element: {_fmt(logo)}"
        )

    def test_search_button_has_visible_outline(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """The search submit button must show a non-zero outline when focused."""
        assert len(focus_sequence) >= 3
        btn = focus_sequence[2]
        assert btn.outline_style != "none", (
            "Search submit button has outline-style: none when focused via keyboard.\n"
            f"Element: {_fmt(btn)}"
        )
        assert btn.outline_width not in ("0px", "0"), (
            "Search submit button has outline-width: 0 when focused via keyboard.\n"
            f"Element: {_fmt(btn)}"
        )

    def test_home_nav_link_has_visible_outline(
        self, focus_sequence: List[FocusedElementInfo]
    ) -> None:
        """The Home nav link must show a non-zero outline when focused."""
        assert len(focus_sequence) >= 4
        home = focus_sequence[3]
        assert home.outline_style != "none", (
            "Home nav link has outline-style: none when focused via keyboard.\n"
            f"Element: {_fmt(home)}"
        )
        assert home.outline_width not in ("0px", "0"), (
            "Home nav link has outline-width: 0 when focused via keyboard.\n"
            f"Element: {_fmt(home)}"
        )
