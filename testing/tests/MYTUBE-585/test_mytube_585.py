"""
MYTUBE-585: Mobile menu toggle accessibility — button includes required ARIA attributes.

Objective
---------
Ensure the hamburger menu button is programmatically detectable by automated testing
tools and assistive technology, specifically addressing the previous assertion failure.

Preconditions
-------------
Viewport width is set to 640px or less.

Steps
-----
1. Set viewport to mobile width (≤640px) and navigate to the homepage.
2. Locate the hamburger menu button in the SiteHeader.
3. Verify the button has an aria-label containing 'menu', 'nav', or 'hamburger'.
4. Verify the button has a data-testid attribute for 'hamburger' or 'mobile-menu'.
5. Observe the initial value of the aria-expanded attribute (must be 'false').
6. Click the button to open the menu and re-verify aria-expanded is now 'true'.

Expected Result
---------------
The button contains the specified labels and test IDs. The aria-expanded attribute
correctly toggles between false and true based on the menu state.

Architecture
------------
- WebConfig (core/config/web_config.py) centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs or environment-specific paths.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-585/test_mytube_585.py -v
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

_MOBILE_VIEWPORT = {"width": 375, "height": 812}  # iPhone-like mobile size ≤ 640px
_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Primary selector for the hamburger button: aria-label containing 'menu'
# as implemented in SiteHeader.tsx: aria-label="Open navigation menu"
_HAMBURGER_BY_ARIA_LABEL_SELECTORS = [
    "header button[aria-label*='menu' i]",
    "header button[aria-label*='hamburger' i]",
    "header button[aria-label*='nav' i]",
]

# Fallback selectors by data-testid (for forward compatibility)
_HAMBURGER_BY_TESTID_SELECTORS = [
    "header button[data-testid*='hamburger']",
    "header button[data-testid*='mobile-menu']",
]


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_hamburger_by_aria_label(page: Page):
    """Return the first visible hamburger button matched by aria-label, or None."""
    for selector in _HAMBURGER_BY_ARIA_LABEL_SELECTORS:
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


def _find_hamburger_by_testid(page: Page):
    """Return the first visible hamburger button matched by data-testid, or None."""
    for selector in _HAMBURGER_BY_TESTID_SELECTORS:
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


class TestMytube585HamburgerARIA:
    """MYTUBE-585 — Hamburger menu button includes required ARIA attributes."""

    def test_hamburger_aria_attributes_and_expanded_toggle(self, config: WebConfig) -> None:
        """Verify hamburger button ARIA accessibility attributes on mobile viewport.

        Steps:
        1. Navigate to homepage with mobile viewport (≤640px).
        2. Locate the hamburger button via aria-label.
        3. Verify aria-label contains 'menu', 'nav', or 'hamburger'.
        4. Verify button has a data-testid for 'hamburger' or 'mobile-menu'.
        5. Confirm aria-expanded is initially 'false'.
        6. Click button and confirm aria-expanded changes to 'true'.
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

                # ── Step 2: Locate the hamburger button via aria-label ───────
                hamburger = _find_hamburger_by_aria_label(page)
                assert hamburger is not None, (
                    "Hamburger/mobile-menu toggle button NOT FOUND via aria-label in the site header "
                    f"at mobile viewport {_MOBILE_VIEWPORT['width']}×{_MOBILE_VIEWPORT['height']}px. "
                    "Expected: a <button> inside <header> with aria-label containing 'menu', 'nav', "
                    "or 'hamburger' to be present and visible. "
                    f"Selectors tried: {_HAMBURGER_BY_ARIA_LABEL_SELECTORS}"
                )

                # ── Step 3: Verify aria-label contains expected keyword ──────
                aria_label = hamburger.get_attribute("aria-label") or ""
                aria_label_lower = aria_label.lower()
                assert any(kw in aria_label_lower for kw in ("menu", "nav", "hamburger")), (
                    f"Hamburger button aria-label '{aria_label}' does not contain any of "
                    "'menu', 'nav', or 'hamburger'. "
                    "Expected: aria-label to contain at least one of these keywords for "
                    "assistive technology compatibility."
                )

                # ── Step 4: Verify data-testid attribute ─────────────────────
                # Check via data-testid selectors
                hamburger_by_testid = _find_hamburger_by_testid(page)
                # Also check if the button itself has a data-testid attribute
                button_testid = hamburger.get_attribute("data-testid") or ""
                has_testid = (
                    hamburger_by_testid is not None
                    or "hamburger" in button_testid.lower()
                    or "mobile-menu" in button_testid.lower()
                )
                assert has_testid, (
                    f"Hamburger button does NOT have a data-testid attribute for 'hamburger' or 'mobile-menu'. "
                    f"Current data-testid value: '{button_testid}' (empty means attribute is missing). "
                    "Expected: button to have data-testid containing 'hamburger' or 'mobile-menu' "
                    "for automated testing tool discoverability."
                )

                # ── Step 5: Verify initial aria-expanded is 'false' ─────────
                aria_expanded_initial = hamburger.get_attribute("aria-expanded") or ""
                assert aria_expanded_initial == "false", (
                    f"Hamburger button aria-expanded initial value is '{aria_expanded_initial}', "
                    "expected 'false' (menu should be closed on page load). "
                    "The aria-expanded attribute must reflect the actual menu state."
                )

                # ── Step 6: Click button and verify aria-expanded → 'true' ──
                hamburger.click()
                page.wait_for_timeout(400)  # Allow animation to settle

                aria_expanded_after = hamburger.get_attribute("aria-expanded") or ""
                assert aria_expanded_after == "true", (
                    f"After clicking the hamburger button, aria-expanded is '{aria_expanded_after}', "
                    "expected 'true'. "
                    "The aria-expanded attribute must toggle to 'true' when the mobile menu is opened."
                )

            finally:
                browser.close()
