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
(600 ms) for the React state update to propagate to the DOM before asserting.

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

from testing.components.pages.site_header.site_header import SiteHeader
from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOBILE_VIEWPORT = {"width": 375, "height": 812}
_DESKTOP_VIEWPORT = {"width": 1024, "height": 812}

_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    """Launch Chromium at mobile viewport, navigate to homepage, yield the page."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        context = browser.new_context(viewport=_MOBILE_VIEWPORT)
        page = context.new_page()
        page.goto(
            config.home_url(),
            timeout=_PAGE_LOAD_TIMEOUT,
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(500)  # let React hydrate
        yield page
        browser.close()


@pytest.fixture(scope="module")
def site_header(browser_page: Page) -> SiteHeader:
    """Return a SiteHeader component bound to the browser page."""
    return SiteHeader(browser_page)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestMytube586MobileMenuClosesOnResize:
    """MYTUBE-586 — Mobile menu auto-closes when viewport expands to desktop."""

    def test_mobile_menu_closes_on_viewport_expansion(
        self, browser_page: Page, site_header: SiteHeader
    ) -> None:
        """
        Full E2E test:
        1. Confirm page is loaded at 375px mobile viewport.
        2. Locate and click the hamburger button — mobile nav must open.
        3. Resize viewport to 1024px — mobile nav must close automatically.
        4. Desktop primary nav (Home, My Videos) must be visible.
        """

        # ── Step 2: Find and click hamburger ─────────────────────────────────
        assert site_header.is_hamburger_visible(), (
            "Hamburger/mobile-menu toggle button NOT FOUND in the site header "
            f"at mobile viewport {_MOBILE_VIEWPORT['width']}×{_MOBILE_VIEWPORT['height']}px. "
            "Expected: a <button> with aria-label containing 'menu', 'nav', or 'hamburger' "
            "to be present and visible inside <header> on mobile viewports."
        )

        site_header.click_hamburger()
        browser_page.wait_for_timeout(400)  # wait for animation/state update

        # Verify menu actually opened before proceeding
        assert site_header.is_mobile_nav_visible(), (
            "After clicking the hamburger button the mobile navigation panel "
            "did NOT become visible. "
            "Expected: <nav id='mobile-nav'> to be shown (hidden attribute removed). "
            "Actual: the panel remained hidden / not visible."
        )

        # ── Step 3: Resize to desktop viewport ───────────────────────────────
        browser_page.set_viewport_size(_DESKTOP_VIEWPORT)

        # Allow the resize event handler to fire and React to update DOM.
        # SiteHeader.tsx listens to 'resize' and sets mobileNavOpen=false
        # when window.innerWidth >= 640.  A 600 ms wait is conservative
        # but reliable for CI environments.
        browser_page.wait_for_timeout(600)

        # ── Assert: mobile nav must be closed ────────────────────────────────
        assert not site_header.is_mobile_nav_visible(), (
            f"After resizing the viewport from {_MOBILE_VIEWPORT['width']}px to "
            f"{_DESKTOP_VIEWPORT['width']}px, the mobile navigation panel is STILL visible. "
            "Expected: the resize handler in SiteHeader.tsx to call "
            "setMobileNavOpen(false) when window.innerWidth >= 640, "
            "dismissing the mobile nav automatically. "
            "Actual: <nav id='mobile-nav'> / [aria-label='Mobile navigation'] "
            "remains visible after the viewport was expanded to desktop width."
        )

        # ── Assert: desktop nav must be visible ──────────────────────────────
        assert site_header.is_desktop_nav_visible(), (
            f"After resizing to desktop width ({_DESKTOP_VIEWPORT['width']}px), "
            "the primary navigation (nav[aria-label='Primary navigation']) is NOT visible. "
            "Expected: the 'hidden sm:flex' Tailwind classes to show "
            "the desktop nav links (Home, My Videos) at ≥640px."
        )

        # ── Assert: desktop nav contains Home and My Videos ──────────────────
        assert site_header.desktop_nav_home_link_visible(), (
            "'Home' link is NOT visible in the desktop primary navigation "
            f"at {_DESKTOP_VIEWPORT['width']}px viewport width."
        )
        assert site_header.desktop_nav_my_videos_link_visible(), (
            "'My Videos' link is NOT visible in the desktop primary navigation "
            f"at {_DESKTOP_VIEWPORT['width']}px viewport width."
        )
