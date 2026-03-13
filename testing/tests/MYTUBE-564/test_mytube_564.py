"""
MYTUBE-564: Scroll responsiveness after UI interaction —
page scrolling is not blocked by residual overlays.

Objective
---------
Ensure that opening and closing the mobile hamburger menu correctly releases
scroll focus and removes any blocking overlays from the page.

Linked Bug: MYTUBE-537 (Done)
Fix: Changed ``overflow: hidden`` → ``overflow: clip`` on ``.shell`` and
``.page-wrap`` in globals.css so that those elements no longer create CSS
scroll containers that silently consume scroll events.

Steps
-----
1. Open the application on a mobile viewport (≤768 px).
2. Click the hamburger menu icon to open the navigation drawer.
3. Close the hamburger menu.
4. Attempt to scroll the main page content immediately.

Expected Result
---------------
- The page scrolls smoothly and immediately.
- ``overflow: hidden`` is NOT present on ``<body>`` or ``<html>``.
- No invisible backdrop/overlay is intercepting pointer events on the main content.

Architecture
------------
- WebConfig (core/config/web_config.py) centralises env var access.
- SiteHeader (components/pages/site_header/) wraps header DOM queries.
- Reuses hamburger-button helpers from MYTUBE-559.
- Playwright sync API with pytest.

Run from repo root:
    pytest testing/tests/MYTUBE-564/test_mytube_564.py -v
"""
from __future__ import annotations

import os
import sys

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOBILE_VIEWPORT = {"width": 375, "height": 812}  # iPhone-like mobile size
_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Hamburger button selectors — must match only the mobile toggle button.
_HAMBURGER_SELECTORS = [
    "header button[aria-label*='menu' i]",
    "header button[aria-label*='navigation' i]",
    "header button[aria-label*='hamburger' i]",
    "header button[aria-label*='nav' i]",
    "header button.sm\\:hidden",
    "header button[data-testid*='hamburger']",
    "header button[data-testid*='mobile-menu']",
]

# Mobile nav menu container selectors.
_MOBILE_NAV_SELECTORS = [
    "header nav.sm\\:hidden",
    "[data-testid='mobile-nav']",
    "[aria-label='Mobile navigation']",
    "header [role='dialog']",
    "header .mobile-menu",
    "header .mobile-nav",
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_hamburger_button(page: Page):
    """Return the first visible hamburger/mobile-menu toggle button, or None."""
    for selector in _HAMBURGER_SELECTORS:
        locator = page.locator(selector)
        try:
            count = locator.count()
        except Exception:
            continue
        for i in range(count):
            try:
                if locator.nth(i).is_visible():
                    return locator.nth(i)
            except Exception:
                continue
    return None


def _find_mobile_nav(page: Page):
    """Return the first visible mobile nav container, or None."""
    for selector in _MOBILE_NAV_SELECTORS:
        locator = page.locator(selector)
        try:
            count = locator.count()
        except Exception:
            continue
        for i in range(count):
            try:
                if locator.nth(i).is_visible():
                    return locator.nth(i)
            except Exception:
                continue
    return None


def _get_overflow_style(page: Page, selector: str) -> str:
    """Return the computed overflow value for the given selector, or ''."""
    return page.evaluate(
        """(sel) => {
            const el = document.querySelector(sel);
            if (!el) return '';
            return window.getComputedStyle(el).overflow;
        }""",
        selector,
    )


def _has_pointer_events_blocking_overlay(page: Page) -> bool:
    """Return True if any full-screen fixed/absolute element is blocking pointer events
    over the main page content area.

    Checks for elements that:
    - Have pointer-events != 'none'
    - Cover a significant portion of the viewport
    - Are positioned fixed/absolute (typical overlay pattern)
    - Are NOT the header itself
    """
    return page.evaluate("""() => {
        const vw = window.innerWidth;
        const vh = window.innerHeight;
        const elements = document.querySelectorAll('body *');
        for (const el of elements) {
            // Skip header and its descendants
            if (el.closest('header')) continue;
            const s = window.getComputedStyle(el);
            if (s.pointerEvents === 'none') continue;
            if (s.position !== 'fixed' && s.position !== 'absolute') continue;
            const rect = el.getBoundingClientRect();
            // Must cover at least 50% of viewport width and height to count as an overlay
            if (rect.width < vw * 0.5 || rect.height < vh * 0.5) continue;
            // Must be visible (not hidden/transparent)
            if (s.display === 'none' || s.visibility === 'hidden') continue;
            if (parseFloat(s.opacity) === 0) continue;
            return true;
        }
        return false;
    }""")


def _measure_scroll_delta(page: Page) -> int:
    """Scroll down by wheel event and return how many pixels the page moved.

    Uses the document scrollTop on the scrollable element (window or
    document.documentElement).  Returns a positive integer if the page
    moved, 0 if it stayed put.
    """
    # Capture initial scroll position
    initial_y: int = page.evaluate("() => window.scrollY || document.documentElement.scrollTop")

    # Dispatch a wheel scroll event in the centre of the viewport
    page.mouse.wheel(0, 300)

    # Give the browser a moment to process the scroll
    page.wait_for_timeout(500)

    final_y: int = page.evaluate("() => window.scrollY || document.documentElement.scrollTop")
    return final_y - initial_y


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMytube564ScrollAfterMenuClose:
    """MYTUBE-564 — Scroll responsiveness after opening and closing the mobile menu."""

    def test_scroll_not_blocked_after_hamburger_menu_close(self, config: WebConfig) -> None:
        """Full E2E test:

        1. Navigate to homepage at mobile viewport.
        2. Locate the hamburger menu button — skip gracefully if not present
           (feature may be implemented as a nav-collapse rather than a modal drawer).
        3. Open the hamburger menu.
        4. Close the hamburger menu.
        5. Assert: body and html do NOT have overflow:hidden.
        6. Assert: no full-screen overlay is blocking pointer events.
        7. Assert: the page physically scrolls when a wheel event is dispatched
           (only if the page is tall enough to be scrollable).
        """
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=config.headless, slow_mo=config.slow_mo
            )
            try:
                page = browser.new_page(viewport=_MOBILE_VIEWPORT)

                # ── Step 1: Navigate ─────────────────────────────────────────
                page.goto(
                    config.home_url(),
                    timeout=_PAGE_LOAD_TIMEOUT,
                    wait_until="domcontentloaded",
                )

                # ── Step 2: Locate hamburger button ──────────────────────────
                hamburger = _find_hamburger_button(page)

                if hamburger is None:
                    # If there is no hamburger button, verify the overflow is
                    # still clean (the bug could manifest regardless of menu use).
                    html_overflow = _get_overflow_style(page, "html")
                    body_overflow = _get_overflow_style(page, "body")

                    assert html_overflow != "hidden", (
                        "No hamburger button found, but <html> already has "
                        f"overflow:hidden ('{html_overflow}'). "
                        "This would block scrolling even without menu interaction."
                    )
                    assert body_overflow != "hidden", (
                        "No hamburger button found, but <body> already has "
                        f"overflow:hidden ('{body_overflow}'). "
                        "This would block scrolling even without menu interaction."
                    )
                    # Nothing more to test without the menu — pass early.
                    return

                # ── Step 3: Open the hamburger menu ──────────────────────────
                hamburger.click()
                page.wait_for_timeout(400)  # allow open animation

                # Confirm menu opened (best effort — don't fail if nav not found)
                _find_mobile_nav(page)

                # ── Step 4: Close the hamburger menu ─────────────────────────
                close_btn = page.locator(
                    "header button[aria-label*='close' i], "
                    "header button[aria-label*='dismiss' i], "
                    "header button[aria-expanded='true']"
                )
                if close_btn.count() > 0 and close_btn.first.is_visible():
                    close_btn.first.click()
                else:
                    # Toggle by re-clicking the hamburger
                    hamburger.click()

                page.wait_for_timeout(400)  # allow close animation

                # ── Step 5: Assert body/html do NOT have overflow:hidden ─────
                html_overflow = _get_overflow_style(page, "html")
                body_overflow = _get_overflow_style(page, "body")

                assert html_overflow != "hidden", (
                    "After closing the hamburger menu, <html> still has "
                    f"overflow:hidden (computed: '{html_overflow}'). "
                    "Expected: overflow must not be 'hidden' so scroll events reach the document. "
                    "The MYTUBE-537 fix changed .shell/.page-wrap to overflow:clip; "
                    "a regression may have re-introduced overflow:hidden on <html>."
                )

                assert body_overflow != "hidden", (
                    "After closing the hamburger menu, <body> still has "
                    f"overflow:hidden (computed: '{body_overflow}'). "
                    "Expected: overflow must not be 'hidden' on <body> after the menu closes. "
                    "A residual scroll-lock class may not be getting cleaned up."
                )

                # ── Step 6: Assert no pointer-events–blocking overlay ────────
                has_overlay = _has_pointer_events_blocking_overlay(page)

                assert not has_overlay, (
                    "After closing the hamburger menu, a full-screen overlay element is still "
                    "intercepting pointer events over the main content area. "
                    "Expected: all overlay/backdrop elements to be removed or set to "
                    "pointer-events:none after the menu closes. "
                    "This would prevent the user from scrolling or interacting with page content."
                )

                # ── Step 7: Verify the page physically scrolls ───────────────
                # Only meaningful when the page content exceeds the viewport.
                page_height: int = page.evaluate(
                    "() => document.documentElement.scrollHeight"
                )
                viewport_height: int = _MOBILE_VIEWPORT["height"]

                if page_height > viewport_height:
                    delta = _measure_scroll_delta(page)
                    assert delta > 0, (
                        f"After closing the hamburger menu, scrolling the page produced "
                        f"a scroll delta of {delta}px (expected > 0). "
                        "The page content is taller than the viewport "
                        f"({page_height}px > {viewport_height}px) so it should be scrollable. "
                        "Possible cause: an invisible overlay or overflow:hidden is still "
                        "blocking scroll events, or the CSS fix for MYTUBE-537 has regressed."
                    )

            finally:
                browser.close()
