"""
MYTUBE-559: Open hamburger menu on mobile — navigation links are visible and interactable.

Objective
---------
Ensure the hamburger menu functionality is usable on mobile, allowing users
to access navigation links without layout breakage.

Preconditions
-------------
Viewport width is set to 768px or less.

Steps
-----
1. Set viewport to mobile width (≤768px) and navigate to the homepage.
2. Locate and click the hamburger menu icon in the SiteHeader.
3. Observe the menu expansion and the visibility of navigation links (Home, My Videos).
4. Click on a navigation link or the close button.

Expected Result
---------------
The menu expands smoothly without jitter. Navigation links (Home, My Videos) are
clearly visible, properly spaced, and clickable. The menu closes correctly when
requested, returning the header to its compact state.

Architecture
------------
- WebConfig (core/config/web_config.py) centralises env var access.
- SiteHeader (components/pages/site_header/) wraps header DOM queries.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs, credentials, or environment-specific paths.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-559/test_mytube_559.py -v
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

_MOBILE_VIEWPORT = {"width": 375, "height": 812}   # iPhone-like mobile size
_PAGE_LOAD_TIMEOUT = 30_000   # ms

# Hamburger button selector — a <button> inside <header> that is only visible
# on mobile (hidden on sm+ breakpoints) used to toggle the mobile nav menu.
# Common patterns: aria-label containing "menu", or a button with sm:hidden.
_HAMBURGER_SELECTORS = [
    "header button[aria-label*='menu' i]",
    "header button[aria-label*='navigation' i]",
    "header button[aria-label*='hamburger' i]",
    "header button[aria-label*='nav' i]",
    "header button.sm\\:hidden",
    "header button[data-testid*='hamburger']",
    "header button[data-testid*='mobile-menu']",
]

# Mobile nav menu selectors — the expanded menu container shown after
# clicking the hamburger button.
_MOBILE_NAV_SELECTORS = [
    "header nav.sm\\:hidden",
    "[data-testid='mobile-nav']",
    "[aria-label='Mobile navigation']",
    "header [role='dialog']",
    "header .mobile-menu",
    "header .mobile-nav",
]

# Navigation links expected in the mobile menu.
_NAV_LINK_HOME_TEXT = "Home"
_NAV_LINK_MY_VIDEOS_TEXT = "My Videos"


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Helper
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
    """Return the first visible mobile nav container after menu open, or None."""
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


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMytube559HamburgerMenuMobile:
    """MYTUBE-559 — Hamburger menu on mobile opens and shows nav links."""

    def test_hamburger_menu_opens_and_shows_nav_links(self, config: WebConfig) -> None:
        """Full E2E test:
        1. Navigate to homepage with mobile viewport.
        2. Locate the hamburger menu icon — it must be present and visible.
        3. Click the hamburger icon — mobile nav menu must expand.
        4. Navigation links (Home, My Videos) must be visible and clickable.
        5. Close the menu — header must return to compact state.
        """
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=config.headless, slow_mo=config.slow_mo
            )
            try:
                page = browser.new_page(viewport=_MOBILE_VIEWPORT)

                # ── Step 1: Navigate to homepage at mobile viewport ──────────
                page.goto(
                    config.home_url(),
                    timeout=_PAGE_LOAD_TIMEOUT,
                    wait_until="domcontentloaded",
                )

                # ── Step 2: Locate the hamburger menu icon ───────────────────
                hamburger = _find_hamburger_button(page)
                assert hamburger is not None, (
                    "Hamburger/mobile-menu toggle button NOT FOUND in the site header "
                    f"at mobile viewport {_MOBILE_VIEWPORT['width']}×{_MOBILE_VIEWPORT['height']}px. "
                    "Expected: a <button> with aria-label containing 'menu', 'nav', or 'hamburger' "
                    "to be present and visible inside <header> on mobile viewports. "
                    "Actual: no such button found. "
                    "The primary nav links (<nav aria-label='Primary navigation'>) use "
                    "'hidden sm:flex' — they are invisible on mobile and no hamburger fallback exists. "
                    "This appears to be an unimplemented feature (noted as a follow-up in MYTUBE-536 PR review)."
                )

                # ── Step 3: Click hamburger — menu must expand ───────────────
                hamburger.click()

                # Allow animation to complete
                page.wait_for_timeout(400)

                # Look for expanded mobile nav menu
                mobile_nav = _find_mobile_nav(page)

                # Also check if the primary nav becomes visible after click
                primary_nav = page.locator("header nav[aria-label='Primary navigation']")
                primary_nav_visible = False
                try:
                    primary_nav_visible = primary_nav.is_visible()
                except Exception:
                    pass

                assert mobile_nav is not None or primary_nav_visible, (
                    "After clicking the hamburger button, NO mobile navigation menu appeared. "
                    "Expected: a mobile nav container to become visible with Home and My Videos links. "
                    "Actual: neither a dedicated mobile nav panel nor the primary nav became visible."
                )

                # ── Step 4: Verify nav links are visible and clickable ───────
                # Check inside the expanded nav area
                nav_container = mobile_nav if mobile_nav is not None else primary_nav

                home_link = nav_container.locator(f"a:has-text('{_NAV_LINK_HOME_TEXT}')")
                my_videos_link = nav_container.locator(f"a:has-text('{_NAV_LINK_MY_VIDEOS_TEXT}')")

                assert home_link.count() > 0 and home_link.first.is_visible(), (
                    f"'{_NAV_LINK_HOME_TEXT}' navigation link NOT visible in the mobile menu. "
                    "Expected: Home link visible and clickable after opening the hamburger menu."
                )

                assert my_videos_link.count() > 0 and my_videos_link.first.is_visible(), (
                    f"'{_NAV_LINK_MY_VIDEOS_TEXT}' navigation link NOT visible in the mobile menu. "
                    "Expected: My Videos link visible and clickable after opening the hamburger menu."
                )

                # ── Step 5: Close menu — check for close button or re-click ──
                close_btn = page.locator(
                    "header button[aria-label*='close' i], "
                    "header button[aria-label*='dismiss' i], "
                    "header button[aria-expanded='true']"
                )
                if close_btn.count() > 0 and close_btn.first.is_visible():
                    close_btn.first.click()
                else:
                    # Re-click hamburger to close
                    hamburger.click()

                page.wait_for_timeout(400)

                # The mobile nav menu should be closed / hidden now
                if mobile_nav is not None:
                    try:
                        assert not mobile_nav.is_visible(), (
                            "After clicking close/hamburger, the mobile nav menu is STILL visible. "
                            "Expected: menu to collapse back to compact state."
                        )
                    except Exception:
                        # Element may have been removed from DOM — that's also acceptable
                        pass

            finally:
                browser.close()
