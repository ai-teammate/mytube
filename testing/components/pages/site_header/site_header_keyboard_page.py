"""
Page object for keyboard navigation testing of the SiteHeader component.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from playwright.sync_api import Page, expect

_PAGE_LOAD_TIMEOUT = 30_000       # ms
_MAX_TABS = 30                    # safety limit to avoid infinite loops

# Elements that deliberately remove the native outline in favour of an
# alternative indicator (e.g. border-blue-500 on focus).  We skip the
# outline-width assertion for these but still assert :focus-visible.
_OUTLINE_NONE_ARIA_LABELS = {"Search query"}


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
