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
- SiteHeader page object encapsulates hamburger button lookup.
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

import urllib.request

import pytest
from playwright.sync_api import expect, sync_playwright

from testing.components.pages.site_header.site_header import SiteHeader
from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOBILE_VIEWPORT = {"width": 375, "height": 812}  # iPhone-like mobile size ≤ 640px
_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_url_reachable(url: str, timeout: int = 10) -> bool:
    try:
        res = urllib.request.urlopen(url, timeout=timeout)
        return res.status < 500
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMytube585HamburgerARIA:
    """MYTUBE-585 — Hamburger menu button includes required ARIA attributes."""

    def test_hamburger_aria_attributes_and_expanded_toggle(self, config: WebConfig) -> None:
        """Verify hamburger button ARIA accessibility attributes on mobile viewport.

        Steps:
        1. Navigate to homepage with mobile viewport (≤640px).
        2. Locate the hamburger button via SiteHeader page object.
        3. Verify aria-label contains 'menu', 'nav', or 'hamburger'.
        4. Verify button has a data-testid for 'hamburger' or 'mobile-menu'.
        5. Confirm aria-expanded is initially 'false'.
        6. Click button and confirm aria-expanded changes to 'true'.
        """
        if not _is_url_reachable(config.base_url):
            pytest.skip(f"Deployed app unreachable ({config.base_url})")

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

                site_header = SiteHeader(page)

                # ── Step 2: Locate the hamburger button via SiteHeader PO ────
                hamburger = site_header.hamburger_button_locator()
                assert hamburger is not None, (
                    "Hamburger/mobile-menu toggle button NOT FOUND via aria-label in the site header "
                    f"at mobile viewport {_MOBILE_VIEWPORT['width']}×{_MOBILE_VIEWPORT['height']}px. "
                    "Expected: a <button> inside <header> with aria-label containing 'menu', 'nav', "
                    "or 'hamburger' to be present and visible."
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
                button_testid = hamburger.get_attribute("data-testid") or ""
                has_testid = (
                    "hamburger" in button_testid.lower()
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
                expect(hamburger).to_have_attribute("aria-expanded", "true")

            finally:
                browser.close()
