"""
MYTUBE-586: Mobile menu state management — menu closes automatically on
viewport expansion.

Objective
---------
Verify that the mobile navigation menu does not persist or block the UI when
the viewport is resized from mobile to desktop width.

Steps
-----
1. Set the viewport width to 375px.
2. Click the hamburger menu icon to open the navigation links.
3. Increase the viewport width to 1024px while the menu is still open.

Expected Result
---------------
The mobile-only menu and any associated backdrops/overlays are automatically
dismissed. The standard horizontal navigation links (Home, My Videos) appear
correctly in the header.

Architecture
------------
- WebConfig (core/config/web_config.py) centralises env var access.
- SiteHeader (components/pages/site_header/) wraps header DOM queries.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs, credentials, or environment-specific paths.

Implementation notes
--------------------
SiteHeader.tsx registers a ``resize`` event listener that calls
``setMobileNavOpen(false)`` when ``window.innerWidth >= 640``.  The mobile nav
panel uses the HTML ``hidden`` attribute (not a CSS class) to control
visibility.  After resizing the viewport we allow a brief settle period
(300 ms) for the React state update to propagate to the DOM before asserting.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-586/test_mytube_586.py -v
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

_MOBILE_VIEWPORT = {"width": 375, "height": 812}
_DESKTOP_VIEWPORT = {"width": 1024, "height": 812}

_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Hamburger button — mobile-only toggle inside <header>
_HAMBURGER_SELECTORS = [
    "header button[aria-label*='menu' i]",
    "header button[aria-label*='navigation' i]",
    "header button[aria-label*='hamburger' i]",
    "header button.sm\\:hidden",
    "header button[data-testid*='hamburger']",
    "header button[data-testid*='mobile-menu']",
]

# Mobile nav panel — always in DOM; ``hidden`` attr controls visibility
_MOBILE_NAV_ID = "mobile-nav"
_MOBILE_NAV_SELECTOR = "#mobile-nav"
_MOBILE_NAV_ARIA_SELECTOR = "[aria-label='Mobile navigation']"

# Primary desktop nav — hidden sm:flex
_DESKTOP_NAV_SELECTOR = "nav[aria-label='Primary navigation']"


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_hamburger_button(page: Page):
    """Return the first visible hamburger toggle button, or None."""
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


def _mobile_nav_is_visible(page: Page) -> bool:
    """Return True if the mobile nav panel is currently visible to the user.

    SiteHeader.tsx uses the HTML ``hidden`` attribute on the <nav id="mobile-nav">
    element (not a CSS class).  ``is_visible()`` in Playwright respects the
    ``hidden`` attribute, so this correctly returns False when hidden=True.
    """
    for selector in (_MOBILE_NAV_SELECTOR, _MOBILE_NAV_ARIA_SELECTOR):
        locator = page.locator(selector)
        try:
            if locator.count() > 0 and locator.first.is_visible():
                return True
        except Exception:
            continue
    return False


def _mobile_nav_is_in_dom(page: Page) -> bool:
    """Return True if the mobile nav element exists in the DOM at all."""
    for selector in (_MOBILE_NAV_SELECTOR, _MOBILE_NAV_ARIA_SELECTOR):
        try:
            if page.locator(selector).count() > 0:
                return True
        except Exception:
            continue
    return False


def _desktop_nav_is_visible(page: Page) -> bool:
    """Return True if the primary desktop navigation links are visible."""
    try:
        locator = page.locator(_DESKTOP_NAV_SELECTOR)
        return locator.count() > 0 and locator.first.is_visible()
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestMytube586MobileMenuClosesOnResize:
    """MYTUBE-586 — Mobile menu auto-closes when viewport expands to desktop."""

    def test_mobile_menu_closes_on_viewport_expansion(
        self, config: WebConfig
    ) -> None:
        """
        Full E2E test:
        1. Load homepage at 375px mobile viewport.
        2. Locate and click the hamburger button — mobile nav must open.
        3. Resize viewport to 1024px — mobile nav must close automatically.
        4. Desktop primary nav (Home, My Videos) must be visible.
        """
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=config.headless, slow_mo=config.slow_mo
            )
            try:
                context = browser.new_context(viewport=_MOBILE_VIEWPORT)
                page = context.new_page()

                # ── Step 1: Load homepage at mobile viewport ─────────────────
                page.goto(
                    config.home_url(),
                    timeout=_PAGE_LOAD_TIMEOUT,
                    wait_until="domcontentloaded",
                )
                page.wait_for_timeout(500)  # let React hydrate

                # ── Step 2: Find and click hamburger ─────────────────────────
                hamburger = _find_hamburger_button(page)
                assert hamburger is not None, (
                    "Hamburger/mobile-menu toggle button NOT FOUND in the site header "
                    f"at mobile viewport {_MOBILE_VIEWPORT['width']}×{_MOBILE_VIEWPORT['height']}px. "
                    "Expected: a <button> with aria-label containing 'menu', 'nav', or 'hamburger' "
                    "to be present and visible inside <header> on mobile viewports."
                )

                hamburger.click()
                page.wait_for_timeout(400)  # wait for animation/state update

                # Verify menu actually opened before proceeding
                menu_opened = _mobile_nav_is_visible(page)
                assert menu_opened, (
                    "After clicking the hamburger button the mobile navigation panel "
                    "did NOT become visible. "
                    "Expected: <nav id='mobile-nav'> to be shown (hidden attribute removed). "
                    "Actual: the panel remained hidden / not visible."
                )

                # ── Step 3: Resize to desktop viewport ───────────────────────
                page.set_viewport_size(_DESKTOP_VIEWPORT)

                # Allow the resize event handler to fire and React to update DOM.
                # SiteHeader.tsx listens to 'resize' and sets mobileNavOpen=false
                # when window.innerWidth >= 640.  A 600 ms wait is conservative
                # but reliable for CI environments.
                page.wait_for_timeout(600)

                # ── Assert: mobile nav must be closed ────────────────────────
                mobile_nav_still_visible = _mobile_nav_is_visible(page)

                assert not mobile_nav_still_visible, (
                    "After resizing the viewport from "
                    f"{_MOBILE_VIEWPORT['width']}px to {_DESKTOP_VIEWPORT['width']}px, "
                    "the mobile navigation panel is STILL visible. "
                    "Expected: the resize handler in SiteHeader.tsx to call "
                    "setMobileNavOpen(false) when window.innerWidth >= 640, "
                    "dismissing the mobile nav automatically. "
                    "Actual: <nav id='mobile-nav'> / [aria-label='Mobile navigation'] "
                    "remains visible after the viewport was expanded to desktop width."
                )

                # ── Assert: desktop nav must be visible ──────────────────────
                assert _desktop_nav_is_visible(page), (
                    "After resizing to desktop width "
                    f"({_DESKTOP_VIEWPORT['width']}px), the primary navigation "
                    "(nav[aria-label='Primary navigation']) is NOT visible. "
                    "Expected: the 'hidden sm:flex' Tailwind classes to show "
                    "the desktop nav links (Home, My Videos) at ≥640px."
                )

                # ── Assert: desktop nav contains Home and My Videos ───────────
                desktop_nav = page.locator(_DESKTOP_NAV_SELECTOR).first
                home_link = desktop_nav.locator("a:has-text('Home')")
                my_videos_link = desktop_nav.locator("a:has-text('My Videos')")

                assert home_link.count() > 0 and home_link.first.is_visible(), (
                    "'Home' link is NOT visible in the desktop primary navigation "
                    f"at {_DESKTOP_VIEWPORT['width']}px viewport width."
                )
                assert my_videos_link.count() > 0 and my_videos_link.first.is_visible(), (
                    "'My Videos' link is NOT visible in the desktop primary navigation "
                    f"at {_DESKTOP_VIEWPORT['width']}px viewport width."
                )

            finally:
                browser.close()
