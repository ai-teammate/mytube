"""
MYTUBE-363: View buttons across site — labels are visible and legible.

Objective
---------
Ensure that all UI buttons have visible labels with sufficient contrast across
various pages of the MyTube application.

Steps
-----
1. Navigate to the homepage and inspect header buttons (search submit button).
2. Navigate to the /login page and inspect the "Sign In" button.
3. Navigate to the /upload page and inspect the primary action button
   ("Upload video").  Authentication is required for this step.

Expected Result
---------------
All button labels are clearly visible.  The text colour contrasts sufficiently
with the button background (WCAG AA minimum contrast ratio of 4.5:1 for normal
text, 3:1 for large/bold text ≥ 14 px bold).  No labels are invisible due to
token mismatches.

Environment variables
---------------------
- APP_URL / WEB_BASE_URL  : Base URL of the deployed web application.
                            Default: https://ai-teammate.github.io/mytube
- FIREBASE_TEST_EMAIL     : Email for the test Firebase user (required for step 3).
- FIREBASE_TEST_PASSWORD  : Password for the test Firebase user (required for step 3).
- PLAYWRIGHT_HEADLESS     : Run browser headless (default: true).
- PLAYWRIGHT_SLOW_MO      : Slow-motion delay in ms for debugging (default: 0).

Architecture
------------
- Uses SiteHeader page object for header button inspection.
- Uses LoginPage page object for the /login Sign In button.
- Uses UploadPage page object for the /upload primary action button.
- WebConfig centralises all env-var access.
- Contrast ratios are evaluated via JavaScript ``getComputedStyle``.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Tuple

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.login_page.login_page import LoginPage
from testing.components.pages.upload_page.upload_page import UploadPage
from testing.components.pages.site_header.site_header import SiteHeader
from testing.components.pages.home_page.home_page import HomePage

# ---------------------------------------------------------------------------
# WCAG contrast thresholds
# ---------------------------------------------------------------------------

# WCAG AA – normal text (< 14 px bold / < 18 px regular).  We use this
# conservative threshold for all button text since the tested buttons use
# text-sm (14 px) which may or may not qualify as "large" text.
_MIN_CONTRAST_RATIO = 4.5

# ---------------------------------------------------------------------------
# JS helper evaluated on an element handle to compute contrast.
# Uses an off-screen Canvas to convert any CSS color (including oklch, hsl,
# hex, rgb) into RGB values — the canvas normalises everything for us.
# ---------------------------------------------------------------------------

_CONTRAST_ELEMENT_JS = """
(el) => {
    function toRGB(cssColor) {
        const canvas = document.createElement('canvas');
        canvas.width = 1;
        canvas.height = 1;
        const ctx = canvas.getContext('2d');
        ctx.fillStyle = cssColor;
        ctx.fillRect(0, 0, 1, 1);
        const d = ctx.getImageData(0, 0, 1, 1).data;
        return [d[0], d[1], d[2]];
    }

    function linearise(c) {
        const s = c / 255;
        return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    }

    function luminance(r, g, b) {
        return 0.2126 * linearise(r) + 0.7152 * linearise(g) + 0.0722 * linearise(b);
    }

    const style = window.getComputedStyle(el);
    const fgRGB = toRGB(style.color);
    const bgRGB = toRGB(style.backgroundColor);

    const fgL = luminance(...fgRGB);
    const bgL = luminance(...bgRGB);
    const lighter = Math.max(fgL, bgL);
    const darker  = Math.min(fgL, bgL);
    const ratio   = (lighter + 0.05) / (darker + 0.05);

    return {
        fg: style.color,
        bg: style.backgroundColor,
        fgRGB: fgRGB,
        bgRGB: bgRGB,
        ratio: ratio
    };
}
"""


def _evaluate_contrast_for_locator(page: Page, locator_obj) -> Optional[dict]:
    """Return contrast info dict for a Playwright Locator, or None on failure.

    Uses an element handle so the JS runs *on the element* — this avoids
    ``document.querySelector`` returning null when selectors include
    pseudo-classes that Chromium's CSS parser handles differently at runtime.
    """
    try:
        handle = locator_obj.element_handle(timeout=5_000)
        if handle is None:
            return None
        return handle.evaluate(_CONTRAST_ELEMENT_JS)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def web_config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser(web_config: WebConfig) -> Browser:
    with sync_playwright() as pw:
        br: Browser = pw.chromium.launch(
            headless=web_config.headless,
            slow_mo=web_config.slow_mo,
        )
        yield br
        br.close()


@pytest.fixture(scope="module")
def page(browser: Browser) -> Page:
    """A plain (unauthenticated) browser page for steps 1 and 2."""
    context: BrowserContext = browser.new_context()
    pg: Page = context.new_page()
    pg.set_default_timeout(20_000)
    yield pg
    context.close()


@pytest.fixture(scope="module")
def authenticated_page(browser: Browser, web_config: WebConfig) -> Optional[Page]:
    """An authenticated browser page for step 3 (upload page).

    Yields *None* when Firebase credentials are absent — the upload test is
    then skipped instead of failing.
    """
    if not web_config.test_email or not web_config.test_password:
        yield None
        return

    context: BrowserContext = browser.new_context()
    pg: Page = context.new_page()
    pg.set_default_timeout(20_000)

    login_page = LoginPage(pg)
    login_page.navigate(web_config.login_url())
    login_page.login_as(web_config.test_email, web_config.test_password)

    pg.wait_for_url(
        lambda u: "/login" not in u,
        timeout=20_000,
    )

    yield pg
    context.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestButtonLabelsVisibleAndLegible:
    """MYTUBE-363: Button labels must be visible and have sufficient contrast."""

    # -----------------------------------------------------------------------
    # Step 1 – Homepage header search button
    # -----------------------------------------------------------------------

    def test_homepage_header_search_button_visible(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """Step 1a: The Search submit button in the site header is visible on the homepage."""
        home_page = HomePage(page)
        home_page.navigate(web_config.base_url)

        # The search submit button has aria-label="Submit search"
        search_btn = page.locator('button[aria-label="Submit search"]')
        assert search_btn.count() > 0, (
            "No 'Submit search' button found in the homepage header. "
            "Expected a <button aria-label='Submit search'> inside the SiteHeader component."
        )
        assert search_btn.first.is_visible(), (
            "The 'Submit search' button in the site header is not visible on the homepage. "
            "The button may be hidden or have display:none / visibility:hidden applied."
        )

    def test_homepage_header_search_button_has_label(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """Step 1b: The Search button has a non-empty accessible label (visible text or aria-label)."""
        # Page is already on homepage from previous test (module-scoped fixture).
        search_btn = page.locator('button[aria-label="Submit search"]').first
        aria_label = search_btn.get_attribute("aria-label") or ""
        inner_text = search_btn.inner_text().strip()

        assert aria_label or inner_text, (
            "The homepage Search button has neither visible text nor an aria-label. "
            f"aria-label={aria_label!r}, inner_text={inner_text!r}."
        )

    def test_homepage_header_search_button_contrast(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """Step 1c: The Search button text colour contrasts sufficiently with its background."""
        search_locator = page.locator('button[aria-label="Submit search"]').first
        info = _evaluate_contrast_for_locator(page, search_locator)

        assert info is not None, (
            "Could not evaluate contrast for the Search button: "
            "element handle or getComputedStyle returned null for "
            "'button[aria-label=\"Submit search\"]' on the homepage."
        )

        ratio = info["ratio"]
        assert ratio >= _MIN_CONTRAST_RATIO, (
            f"Search button contrast ratio {ratio:.2f}:1 is below the WCAG AA "
            f"minimum of {_MIN_CONTRAST_RATIO}:1. "
            f"Foreground: {info['fg']}, Background: {info['bg']}. "
            f"Button selector: 'button[aria-label=\"Submit search\"]' on {page.url!r}."
        )

    # -----------------------------------------------------------------------
    # Step 2 – Login page "Sign In" button
    # -----------------------------------------------------------------------

    def test_login_page_sign_in_button_visible(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """Step 2a: The 'Sign In' submit button is visible on the /login page."""
        # Use networkidle to ensure React has fully hydrated the login form.
        page.goto(web_config.login_url(), wait_until="networkidle", timeout=30_000)

        # Wait for at least one submit button to appear.
        page.locator('button[type="submit"]').first.wait_for(
            state="visible", timeout=10_000
        )

        # The Sign In button is type="submit" and NOT the header search button.
        sign_in_btn = page.locator(
            'button[type="submit"]:not([aria-label="Submit search"])'
        ).first

        assert sign_in_btn.is_visible(), (
            "The Sign In button on /login is not visible. "
            "The button may be hidden by CSS or not rendered by the login form component. "
            f"URL: {page.url!r}."
        )

    def test_login_page_sign_in_button_has_label(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """Step 2b: The Sign In button has a non-empty visible label."""
        sign_in_btn = page.locator(
            'button[type="submit"]:not([aria-label="Submit search"])'
        ).first
        inner_text = sign_in_btn.inner_text().strip()

        assert inner_text, (
            "The Sign In button on /login has no visible text label. "
            f"inner_text={inner_text!r}. "
            "The button label may be empty or rendered in an invisible colour."
        )

    def test_login_page_sign_in_button_contrast(
        self,
        page: Page,
        web_config: WebConfig,
    ) -> None:
        """Step 2c: The Sign In button text colour contrasts sufficiently with its background."""
        sign_in_locator = page.locator(
            'button[type="submit"]:not([aria-label="Submit search"])'
        ).first
        info = _evaluate_contrast_for_locator(page, sign_in_locator)

        assert info is not None, (
            "Could not evaluate contrast for the Sign In button: "
            "element handle or getComputedStyle returned null for "
            "'button[type=\"submit\"]:not([aria-label=\"Submit search\"])' "
            f"on {page.url!r}."
        )

        ratio = info["ratio"]
        assert ratio >= _MIN_CONTRAST_RATIO, (
            f"Sign In button contrast ratio {ratio:.2f}:1 is below the WCAG AA "
            f"minimum of {_MIN_CONTRAST_RATIO}:1. "
            f"Foreground: {info['fg']}, Background: {info['bg']}. "
            f"URL: {page.url!r}."
        )

    # -----------------------------------------------------------------------
    # Step 3 – Upload page primary action button
    # -----------------------------------------------------------------------

    def test_upload_page_button_visible(
        self,
        authenticated_page: Optional[Page],
        web_config: WebConfig,
    ) -> None:
        """Step 3a: The 'Upload video' submit button is visible on /upload (authenticated)."""
        if authenticated_page is None:
            pytest.skip(
                "FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD not set — "
                "skipping upload page button check (step 3)."
            )

        upload_page = UploadPage(authenticated_page)
        upload_page.navigate(web_config.base_url)

        assert not upload_page.is_on_login_page(), (
            "The /upload page redirected an authenticated user to /login. "
            "Authentication may not have completed correctly."
        )
        assert upload_page.is_form_visible(), (
            "The upload form is not visible on /upload for an authenticated user. "
            f"Current URL: {authenticated_page.url!r}."
        )

        upload_btn = authenticated_page.locator('button[type="submit"]').first
        upload_btn.wait_for(state="visible", timeout=10_000)
        assert upload_btn.is_visible(), (
            "The 'Upload video' submit button on /upload is not visible. "
            "The button may be hidden by CSS or the form may not have rendered."
        )

    def test_upload_page_button_has_label(
        self,
        authenticated_page: Optional[Page],
        web_config: WebConfig,
    ) -> None:
        """Step 3b: The Upload video button has a non-empty visible label."""
        if authenticated_page is None:
            pytest.skip(
                "FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD not set — "
                "skipping upload page button label check (step 3)."
            )

        upload_btn = authenticated_page.locator('button[type="submit"]').first
        inner_text = upload_btn.inner_text().strip()

        assert inner_text, (
            "The primary action button on /upload has no visible text label. "
            f"inner_text={inner_text!r}. "
            "The button text may be empty or invisible due to a colour token mismatch."
        )

    def test_upload_page_button_contrast(
        self,
        authenticated_page: Optional[Page],
        web_config: WebConfig,
    ) -> None:
        """Step 3c: The Upload video button text colour contrasts sufficiently with its background."""
        if authenticated_page is None:
            pytest.skip(
                "FIREBASE_TEST_EMAIL / FIREBASE_TEST_PASSWORD not set — "
                "skipping upload page button contrast check (step 3)."
            )

        upload_locator = authenticated_page.locator('button[type="submit"]').first
        info = _evaluate_contrast_for_locator(authenticated_page, upload_locator)

        assert info is not None, (
            "Could not evaluate contrast for the Upload video button: "
            "element handle or getComputedStyle returned null for "
            f"'button[type=\"submit\"]' on {authenticated_page.url!r}."
        )

        ratio = info["ratio"]
        assert ratio >= _MIN_CONTRAST_RATIO, (
            f"Upload video button contrast ratio {ratio:.2f}:1 is below the "
            f"WCAG AA minimum of {_MIN_CONTRAST_RATIO}:1. "
            f"Foreground: {info['fg']}, Background: {info['bg']}. "
            f"URL: {authenticated_page.url!r}."
        )
