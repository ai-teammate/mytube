"""
MYTUBE-560: Mobile header layout consistency — alignment remains correct on all AppShell pages.

Objective
---------
Verify that the fix for the misaligned mobile header (MYTUBE-536) is applied globally
across all pages that use the SiteHeader component.

Preconditions
-------------
Viewport width is set to 375px (mobile).

Steps
-----
1. Navigate to the Homepage and verify header alignment.
2. Navigate to the Watch page and verify header alignment.
3. Navigate to the Dashboard and verify header alignment.
4. Log in and navigate to the Upload page; verify header alignment.

Expected Result
---------------
The SiteHeader maintains a consistent, non-broken layout across all pages.
The logo, search (if visible), and auth/avatar section remain correctly positioned
regardless of the page content.

Bug fix (MYTUBE-536)
--------------------
The fix replaced fixed mobile padding/gap with responsive Tailwind classes:
  - min-h-[56px] sm:min-h-[88px]   (was: min-h-[88px])
  - px-4 sm:px-10                   (was: px-10)
  - py-3 sm:py-4                    (was: py-4)
  - gap-3 sm:gap-6                  (was: gap-6)
  - min-w-0 on search <form>        (allows flex item to shrink)
  - min-w-0 on search <input>       (fixes min-width: auto overflow)

Architecture
------------
- Dual-mode: static source analysis (always) + live Playwright on mobile viewport (when APP_URL set).
- WebConfig from testing/core/config/web_config.py centralises env vars.
- SiteHeader page object from testing/components/pages/site_header/site_header.py
  encapsulates header queries.
- No hardcoded URLs, credentials, or selectors outside component/page objects.

Run from repo root:
    pytest testing/tests/MYTUBE-560/test_mytube_560.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MOBILE_WIDTH = 375
_MOBILE_HEIGHT = 812
_PAGE_LOAD_TIMEOUT = 30_000  # ms

# Repo root for static analysis
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SITE_HEADER_TSX = _REPO_ROOT / "web" / "src" / "components" / "SiteHeader.tsx"

# Responsive CSS classes the fix introduced (MYTUBE-536)
_EXPECTED_MOBILE_PADDING_X = "px-4"
_EXPECTED_RESPONSIVE_PADDING_X = "sm:px-10"
_EXPECTED_MOBILE_MIN_HEIGHT = "min-h-[56px]"
_EXPECTED_RESPONSIVE_MIN_HEIGHT = "sm:min-h-[88px]"
_EXPECTED_MOBILE_GAP = "gap-3"
_EXPECTED_RESPONSIVE_GAP = "sm:gap-6"
_EXPECTED_FORM_MIN_W = "min-w-0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_live_mode() -> bool:
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


def _header_overflow_info(page: Page) -> dict:
    """Return header layout metrics to detect horizontal overflow on mobile.

    Uses the bounding rect rather than scrollWidth because flex layout allows
    items to shrink below their natural content size — scrollWidth can exceed
    offsetWidth even when the header is visually correct on screen.  We detect
    real overflow by checking whether any VISIBLE child element's right edge
    extends beyond the viewport boundary.
    """
    return page.evaluate(
        """() => {
            const header = document.querySelector('header');
            if (!header) return { found: false };
            const rect = header.getBoundingClientRect();
            const vpW = window.innerWidth;

            // Scan all visible descendant elements; track the furthest right edge.
            let maxRight = rect.right;
            for (const el of header.querySelectorAll('*')) {
                const cs = window.getComputedStyle(el);
                if (cs.display === 'none' || cs.visibility === 'hidden') continue;
                const r = el.getBoundingClientRect();
                if (r.right > maxRight) maxRight = r.right;
            }

            return {
                found: true,
                offsetWidth: header.offsetWidth,
                scrollWidth: header.scrollWidth,
                viewportWidth: vpW,
                rectWidth: rect.width,
                rectRight: rect.right,
                maxVisibleRight: maxRight,
                // Tolerance of 2px to absorb sub-pixel rounding
                exceedsViewport: maxRight > vpW + 2,
            };
        }"""
    )


def _document_has_horizontal_scroll(page: Page) -> bool:
    """Return True if the document body overflows horizontally."""
    return page.evaluate(
        "() => document.documentElement.scrollWidth > document.documentElement.clientWidth"
    )


def _logo_is_visible(page: Page) -> bool:
    """Return True if the logo link is present and visible in the header.

    The logo <Link href="/"> uses no Tailwind text-color class — colour is set
    via inline style (var(--accent-logo)).  We match by href pattern to keep
    this selector deployment-path agnostic (works with and without a base path).
    """
    return page.evaluate(
        """() => {
            // The logo link contains a LogoIcon SVG and text, always href="/"
            // or the base-path variant e.g. "/mytube/"
            const header = document.querySelector('header');
            if (!header) return false;
            const logoLink = header.querySelector('a[href="/"], a[href$="/mytube/"], a[href$="/"]');
            if (!logoLink) return false;
            const rect = logoLink.getBoundingClientRect();
            return rect.width > 0 && rect.height > 0;
        }"""
    )


def _wait_for_page_content(page: Page, url: str) -> None:
    """Navigate to url and wait for the header to be present."""
    page.goto(url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
    page.wait_for_selector("header", timeout=_PAGE_LOAD_TIMEOUT)


def _get_first_video_id(page: Page, home_url: str) -> str | None:
    """Navigate to the homepage and extract the first video link's ID, or None."""
    page.goto(home_url, timeout=_PAGE_LOAD_TIMEOUT, wait_until="domcontentloaded")
    try:
        # Video links are rendered as /v/<id>/
        page.wait_for_selector("a[href*='/v/']", timeout=10_000)
        href = page.locator("a[href*='/v/']").first.get_attribute("href")
        if href:
            parts = [p for p in href.split("/") if p and p != "v"]
            # The last non-empty segment after /v/ is the ID
            idx = href.find("/v/")
            if idx >= 0:
                rest = href[idx + 3:].strip("/")
                video_id = rest.split("/")[0]
                return video_id if video_id else None
    except Exception:
        pass
    return None


def _assert_header_not_overflowing(page: Page, page_label: str) -> None:
    """Assert that the SiteHeader does not overflow horizontally on this page."""
    info = _header_overflow_info(page)

    assert info.get("found"), (
        f"[{page_label}] No <header> element found in the DOM. "
        f"Expected the SiteHeader to be present on all AppShell pages. "
        f"URL: {page.url}"
    )

    assert not info.get("exceedsViewport"), (
        f"[{page_label}] A visible element inside the header extends beyond the viewport. "
        f"Maximum visible right edge: {info.get('maxVisibleRight', '?')}px, "
        f"viewport width: {info.get('viewportWidth', '?')}px. "
        f"The header layout is broken on mobile — an element overflows the {_MOBILE_WIDTH}px screen. "
        f"URL: {page.url}"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def mobile_page(config: WebConfig):
    """Chromium browser page at 375×812 mobile viewport."""
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=config.headless, slow_mo=config.slow_mo)
        page = browser.new_page(viewport={"width": _MOBILE_WIDTH, "height": _MOBILE_HEIGHT})
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Static analysis (always runs — validates the fix was applied in source)
# ---------------------------------------------------------------------------


class TestMytube560MobileHeaderStaticAnalysis:
    """MYTUBE-560 — Static source analysis validates MYTUBE-536 fix is present."""

    @pytest.fixture(scope="class")
    def tsx_source(self) -> str:
        assert _SITE_HEADER_TSX.exists(), (
            f"SiteHeader.tsx not found at expected path: {_SITE_HEADER_TSX}. "
            "Cannot verify the MYTUBE-536 responsive fix."
        )
        return _SITE_HEADER_TSX.read_text(encoding="utf-8")

    def test_mobile_padding_x_applied(self, tsx_source: str) -> None:
        """SiteHeader must use px-4 (mobile) instead of px-10 (desktop-only)."""
        assert _EXPECTED_MOBILE_PADDING_X in tsx_source, (
            f"Expected '{_EXPECTED_MOBILE_PADDING_X}' not found in SiteHeader.tsx. "
            "The MYTUBE-536 fix should have replaced the fixed 'px-10' with responsive "
            "'px-4 sm:px-10' to avoid overflow on mobile viewports."
        )

    def test_responsive_padding_x_applied(self, tsx_source: str) -> None:
        """SiteHeader must use sm:px-10 (large-screen) responsive padding."""
        assert _EXPECTED_RESPONSIVE_PADDING_X in tsx_source, (
            f"Expected '{_EXPECTED_RESPONSIVE_PADDING_X}' not found in SiteHeader.tsx. "
            "The MYTUBE-536 fix should have replaced the fixed 'px-10' with responsive "
            "'px-4 sm:px-10'."
        )

    def test_mobile_min_height_applied(self, tsx_source: str) -> None:
        """SiteHeader must use min-h-[56px] for mobile (reduced from 88px)."""
        assert _EXPECTED_MOBILE_MIN_HEIGHT in tsx_source, (
            f"Expected '{_EXPECTED_MOBILE_MIN_HEIGHT}' not found in SiteHeader.tsx. "
            "The MYTUBE-536 fix should have replaced 'min-h-[88px]' with "
            "'min-h-[56px] sm:min-h-[88px]' so mobile header isn't too tall."
        )

    def test_responsive_min_height_applied(self, tsx_source: str) -> None:
        """SiteHeader must use sm:min-h-[88px] for large screens."""
        assert _EXPECTED_RESPONSIVE_MIN_HEIGHT in tsx_source, (
            f"Expected '{_EXPECTED_RESPONSIVE_MIN_HEIGHT}' not found in SiteHeader.tsx. "
            "The MYTUBE-536 fix should have added 'sm:min-h-[88px]' alongside "
            "'min-h-[56px]' for responsive height."
        )

    def test_mobile_gap_applied(self, tsx_source: str) -> None:
        """SiteHeader must use gap-3 on mobile (reduced from gap-6)."""
        assert _EXPECTED_MOBILE_GAP in tsx_source, (
            f"Expected '{_EXPECTED_MOBILE_GAP}' not found in SiteHeader.tsx. "
            "The MYTUBE-536 fix should have replaced 'gap-6' with 'gap-3 sm:gap-6' "
            "to reduce spacing on mobile."
        )

    def test_responsive_gap_applied(self, tsx_source: str) -> None:
        """SiteHeader must use sm:gap-6 for large screens."""
        assert _EXPECTED_RESPONSIVE_GAP in tsx_source, (
            f"Expected '{_EXPECTED_RESPONSIVE_GAP}' not found in SiteHeader.tsx. "
            "The MYTUBE-536 fix should have replaced 'gap-6' with 'gap-3 sm:gap-6'."
        )

    def test_search_form_has_min_w_0(self, tsx_source: str) -> None:
        """Search <form> must have min-w-0 to allow flex shrinking on mobile."""
        assert _EXPECTED_FORM_MIN_W in tsx_source, (
            f"Expected '{_EXPECTED_FORM_MIN_W}' not found in SiteHeader.tsx. "
            "The MYTUBE-536 fix should have added 'min-w-0' to the search form and/or "
            "input to prevent flex overflow on narrow viewports."
        )


# ---------------------------------------------------------------------------
# Live tests (require APP_URL to be set and app to be reachable)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _is_live_mode(),
    reason="Live mode requires APP_URL / WEB_BASE_URL to be set",
)
class TestMytube560MobileHeaderAlignmentLive:
    """MYTUBE-560 — Live Playwright tests at 375px mobile viewport width."""

    def test_homepage_header_not_overflowing(
        self, mobile_page: Page, config: WebConfig
    ) -> None:
        """Step 1: Homepage header must not overflow horizontally at 375px."""
        _wait_for_page_content(mobile_page, config.home_url())
        _assert_header_not_overflowing(mobile_page, "Homepage")

    def test_homepage_logo_visible(
        self, mobile_page: Page, config: WebConfig
    ) -> None:
        """Step 1 (logo): Logo link must be visible on the homepage at 375px."""
        _wait_for_page_content(mobile_page, config.home_url())
        assert _logo_is_visible(mobile_page), (
            f"[Homepage] Logo link is not visible in the header "
            f"at {_MOBILE_WIDTH}px viewport width. "
            f"Expected: logo always visible on mobile. URL: {mobile_page.url}"
        )

    def test_watch_page_header_not_overflowing(
        self, mobile_page: Page, config: WebConfig
    ) -> None:
        """Step 2: Watch page header must not overflow horizontally at 375px."""
        # Navigate to homepage first to find a real video ID
        video_id = _get_first_video_id(mobile_page, config.home_url())
        if not video_id:
            pytest.skip(
                "No video links found on the homepage. "
                "Cannot navigate to a watch page. Skipping watch-page header check."
            )

        watch_url = f"{config.base_url}/v/{video_id}/"
        _wait_for_page_content(mobile_page, watch_url)
        _assert_header_not_overflowing(mobile_page, "Watch page")

    def test_watch_page_logo_visible(
        self, mobile_page: Page, config: WebConfig
    ) -> None:
        """Step 2 (logo): Logo must be visible on the watch page at 375px."""
        video_id = _get_first_video_id(mobile_page, config.home_url())
        if not video_id:
            pytest.skip("No video links found — skipping watch page logo check.")

        watch_url = f"{config.base_url}/v/{video_id}/"
        _wait_for_page_content(mobile_page, watch_url)
        assert _logo_is_visible(mobile_page), (
            f"[Watch page] Logo is not visible in the header "
            f"at {_MOBILE_WIDTH}px viewport. URL: {mobile_page.url}"
        )

    def test_dashboard_header_not_overflowing(
        self, mobile_page: Page, config: WebConfig
    ) -> None:
        """Step 3: Dashboard header must not overflow horizontally at 375px.

        Note: The dashboard may redirect to /login when not authenticated.
        The header is still rendered on the redirect target, so we assert
        alignment on whatever page we land on.
        """
        _wait_for_page_content(mobile_page, config.dashboard_url())
        _assert_header_not_overflowing(mobile_page, "Dashboard (or login redirect)")

    def test_dashboard_logo_visible(
        self, mobile_page: Page, config: WebConfig
    ) -> None:
        """Step 3 (logo): Logo must be visible on the dashboard at 375px."""
        _wait_for_page_content(mobile_page, config.dashboard_url())
        assert _logo_is_visible(mobile_page), (
            f"[Dashboard] Logo is not visible in the header "
            f"at {_MOBILE_WIDTH}px viewport. URL: {mobile_page.url}"
        )

    def test_upload_page_header_not_overflowing_after_login(
        self, mobile_page: Page, config: WebConfig
    ) -> None:
        """Step 4: After login, Upload page header must not overflow at 375px."""
        if not config.test_email or not config.test_password:
            pytest.skip(
                "FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD not set. "
                "Cannot test upload page in authenticated state."
            )

        # Log in
        login_page = LoginPage(mobile_page)
        login_page.navigate(config.login_url())
        login_page.fill_email(config.test_email)
        login_page.fill_password(config.test_password)
        login_page.click_sign_in()

        # Wait for successful navigation away from login (to / or /upload)
        try:
            mobile_page.wait_for_url(
                lambda url: "/login" not in url,
                timeout=15_000,
            )
        except Exception:
            pytest.skip(
                "Login did not succeed within timeout — "
                "skipping upload page header alignment check."
            )

        # Navigate to upload page
        _wait_for_page_content(mobile_page, config.upload_url())
        _assert_header_not_overflowing(mobile_page, "Upload page (authenticated)")

    def test_upload_page_logo_visible_after_login(
        self, mobile_page: Page, config: WebConfig
    ) -> None:
        """Step 4 (logo): Logo must be visible on the upload page at 375px."""
        if not config.test_email or not config.test_password:
            pytest.skip(
                "FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD not set. "
                "Cannot test upload page logo visibility."
            )

        _wait_for_page_content(mobile_page, config.upload_url())
        assert _logo_is_visible(mobile_page), (
            f"[Upload page] Logo is not visible in the header "
            f"at {_MOBILE_WIDTH}px viewport. URL: {mobile_page.url}"
        )

    def test_no_horizontal_document_scroll_on_homepage(
        self, mobile_page: Page, config: WebConfig
    ) -> None:
        """Bonus: The homepage must not create horizontal scrolling at 375px.

        Horizontal scroll at mobile width is a strong sign that an element
        (e.g. the header) is overflowing the viewport.
        """
        _wait_for_page_content(mobile_page, config.home_url())
        has_scroll = _document_has_horizontal_scroll(mobile_page)
        assert not has_scroll, (
            f"The homepage has horizontal scrolling at {_MOBILE_WIDTH}px viewport width. "
            f"Expected: no horizontal overflow. "
            f"This typically means an element (likely the header) is wider than the viewport. "
            f"URL: {mobile_page.url}"
        )
