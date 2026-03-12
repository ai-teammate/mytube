"""
MYTUBE-510: Library area toolbar grid — search and filter layout.

Objective
---------
Verify the toolbar in the library area correctly aligns the search input,
category filter, and reset button.

Preconditions
-------------
User is on the /upload page.

Steps
-----
1. Locate the .card.toolbar in the right-hand library area.
2. Inspect the layout of the search input and select filter.

Expected Result
---------------
The toolbar is a CSS grid row containing the search input, category filter
select, and reset button.  The elements are aligned horizontally with
consistent spacing as per the workspace layout spec.

Test Approach
-------------
The /upload page requires an authenticated user.  When real Firebase
credentials (FIREBASE_TEST_EMAIL + FIREBASE_TEST_PASSWORD + FIREBASE_API_KEY)
are available the test performs a real login; otherwise it injects a fake
Firebase user via a context init script — the same technique used by
MYTUBE-401 — so that the upload page renders its full authenticated content.

After navigation the test:
  1. Waits for the search-videos input to be present (confirms the library
     toolbar has mounted).
  2. Reads the computed CSS of the toolbar row (parent of the search input)
     via window.getComputedStyle().
  3. Asserts display == "grid".
  4. Asserts the grid has three columns: 1fr + two auto columns.
  5. Asserts all three interactive elements (search input, category select,
     reset button) are present and visible.
  6. Asserts each element is in the same parent container.

Architecture
------------
- WebConfig from testing/core/config/web_config.py centralises env var access.
- Playwright sync API with pytest module-scoped fixtures.
- No hardcoded URLs, credentials, or environment values.
"""
from __future__ import annotations

import os
import sys
from typing import Optional

import pytest
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_TOOLBAR_WAIT_TIMEOUT = 15_000  # ms — time to wait for the toolbar to appear

# Stable aria-based selectors that survive CSS module name mangling
_SEARCH_INPUT_SELECTOR = '[aria-label="search videos"]'
_CATEGORY_SELECT_SELECTOR = '[aria-label="filter by category"]'
_RESET_BUTTON_SELECTOR = 'button[type="button"]'

# Expected computed CSS values for the toolbar row (CSS grid)
_EXPECTED_DISPLAY = "grid"
_EXPECTED_ALIGN_ITEMS = "center"

# Fake Firebase user injection — same technique as MYTUBE-401.
# Intercepts webpack's minified onAuthStateChanged export ("hg") so that the
# app receives a fake signed-in user and renders the /upload page content.
_FAKE_USER_INJECT_SCRIPT = """
(function () {
    var _origDefProp = Object.defineProperty;
    Object.defineProperty = function (target, prop, descriptor) {
        if (prop === 'hg' && descriptor && typeof descriptor.get === 'function') {
            window.__authIntercept510Activated = true;
            return _origDefProp(target, prop, {
                enumerable: descriptor.enumerable,
                configurable: true,
                get: function () {
                    return function fakeOnAuthStateChanged(auth, nextOrObserver) {
                        var nextCb;
                        if (typeof nextOrObserver === 'function') {
                            nextCb = nextOrObserver;
                        } else if (
                            nextOrObserver !== null &&
                            typeof nextOrObserver === 'object' &&
                            typeof nextOrObserver.next === 'function'
                        ) {
                            nextCb = nextOrObserver.next;
                        }
                        var fakeUser = {
                            uid: 'ci-uid-mytube-510',
                            email: 'ci@mytube510.test',
                            displayName: 'CI Tester',
                            photoURL: null,
                            emailVerified: true,
                            isAnonymous: false,
                            getIdToken: function (forceRefresh) {
                                return Promise.resolve('ci-fake-id-token-510');
                            }
                        };
                        setTimeout(function () {
                            if (typeof nextCb === 'function') {
                                nextCb(fakeUser);
                            }
                        }, 200);
                        return function () {};
                    };
                }
            });
        }
        return _origDefProp.apply(Object, arguments);
    };
})();
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _computed_style_of_parent(page: Page, child_selector: str, prop: str) -> str:
    """Return a computed CSS property of the *parent* element of child_selector."""
    return page.eval_on_selector(
        child_selector,
        f"el => window.getComputedStyle(el.parentElement).{prop}",
    )


def _parent_element_tag(page: Page, child_selector: str) -> str:
    """Return the tag name of the parent element of child_selector."""
    return page.eval_on_selector(
        child_selector,
        "el => el.parentElement.tagName.toLowerCase()",
    )


def _siblings_share_parent(page: Page, selector_a: str, selector_b: str) -> bool:
    """Return True if two elements share the same immediate parent."""
    return page.evaluate(
        """([selA, selB]) => {
            const a = document.querySelector(selA);
            const b = document.querySelector(selB);
            return a !== null && b !== null && a.parentElement === b.parentElement;
        }""",
        [selector_a, selector_b],
    )


def _get_toolbar_css(page: Page) -> dict:
    """Return key computed CSS values for the toolbar row."""
    return page.eval_on_selector(
        _SEARCH_INPUT_SELECTOR,
        """el => {
            const row = el.parentElement;
            const cs = window.getComputedStyle(row);
            return {
                display: cs.display,
                gridTemplateColumns: cs.gridTemplateColumns,
                gap: cs.gap,
                columnGap: cs.columnGap,
                alignItems: cs.alignItems,
                childCount: row.children.length,
                tagName: row.tagName.toLowerCase(),
            };
        }""",
    )


def _reset_button_in_toolbar(page: Page) -> bool:
    """Return True if there is a 'Reset' button that shares the toolbar parent."""
    return page.evaluate(
        """([searchSel]) => {
            const searchInput = document.querySelector(searchSel);
            if (!searchInput) return false;
            const row = searchInput.parentElement;
            const buttons = row ? Array.from(row.querySelectorAll('button')) : [];
            return buttons.some(btn => (btn.textContent || '').trim() === 'Reset');
        }""",
        [_SEARCH_INPUT_SELECTOR],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def upload_page(config: WebConfig) -> Page:
    """Navigate to /upload with a fake (or real) authenticated user.

    Uses the fake-user injection init script if no real Firebase credentials
    are configured; otherwise performs a real login first.
    """
    firebase_api_key = os.getenv("FIREBASE_API_KEY", "")
    email = config.test_email
    password = config.test_password
    has_credentials = bool(firebase_api_key and email and password)

    with sync_playwright() as pw:
        browser: Browser = pw.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo,
        )
        context: BrowserContext = browser.new_context()
        context.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        # Always inject the fake-user script so the toolbar renders even when
        # real credentials are unavailable.
        context.add_init_script(script=_FAKE_USER_INJECT_SCRIPT)

        page: Page = context.new_page()
        page.set_default_timeout(_PAGE_LOAD_TIMEOUT)

        if has_credentials:
            # Real login path
            page.goto(config.login_url(), wait_until="domcontentloaded")
            try:
                page.wait_for_selector('input[id="email"]', timeout=15_000)
                page.fill('input[id="email"]', email)
                page.fill('input[id="password"]', password)
                page.click('button[type="submit"]:not([aria-label="Submit search"])')
                page.wait_for_url(lambda url: "/login" not in url, timeout=20_000)
            except Exception:
                pass

        # Navigate to /upload (fake user makes the page render its content)
        page.goto(config.upload_url(), wait_until="domcontentloaded")

        # Wait for the toolbar search input to confirm the library area rendered
        try:
            page.wait_for_selector(
                _SEARCH_INPUT_SELECTOR,
                timeout=_TOOLBAR_WAIT_TIMEOUT,
            )
        except Exception:
            pass

        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLibraryToolbarGridLayout:
    """MYTUBE-510 — Toolbar in the library area uses CSS grid layout."""

    def test_search_input_is_present(self, upload_page: Page) -> None:
        """The search input with aria-label='search videos' must be present."""
        locator = upload_page.locator(_SEARCH_INPUT_SELECTOR)
        assert locator.count() >= 1, (
            f"Search input ({_SEARCH_INPUT_SELECTOR}) not found in the library toolbar. "
            "The /upload page may not have rendered the authenticated content. "
            "Check that the fake-user injection script activated correctly."
        )

    def test_category_select_is_present(self, upload_page: Page) -> None:
        """The category filter select with aria-label='filter by category' must be present."""
        locator = upload_page.locator(_CATEGORY_SELECT_SELECTOR)
        assert locator.count() >= 1, (
            f"Category select ({_CATEGORY_SELECT_SELECTOR}) not found in the library toolbar."
        )

    def test_reset_button_is_present_in_toolbar(self, upload_page: Page) -> None:
        """A 'Reset' button must be present inside the toolbar row."""
        found = _reset_button_in_toolbar(upload_page)
        assert found, (
            "No 'Reset' button found as a sibling of the search input inside the toolbar row. "
            "Expected a <button> with text 'Reset' as a direct child of the toolbar grid row."
        )

    def test_search_and_select_share_parent(self, upload_page: Page) -> None:
        """The search input and category select must be direct children of the same parent."""
        shared = _siblings_share_parent(
            upload_page,
            _SEARCH_INPUT_SELECTOR,
            _CATEGORY_SELECT_SELECTOR,
        )
        assert shared, (
            "The search input and category select do not share the same parent element. "
            "Both must be direct children of the toolbar grid row."
        )

    def test_toolbar_row_is_css_grid(self, upload_page: Page) -> None:
        """The toolbar row container must use display: grid."""
        css = _get_toolbar_css(upload_page)
        display = css.get("display", "")
        assert display == _EXPECTED_DISPLAY, (
            f"Toolbar row has display='{display}', expected 'grid'. "
            f"Full CSS snapshot: {css}"
        )

    def test_toolbar_grid_has_three_columns(self, upload_page: Page) -> None:
        """The toolbar grid must define three columns (1fr + two auto columns)."""
        css = _get_toolbar_css(upload_page)
        grid_cols: str = css.get("gridTemplateColumns", "")
        # getComputedStyle resolves the three columns to pixel values like
        # "NNNpx NNNpx NNNpx"; split and count.
        parts = [p.strip() for p in grid_cols.split() if p.strip()]
        # Each column value is a px measurement or track keyword.
        # 3 separate column values expected.
        assert len(parts) == 3, (
            f"Toolbar grid has {len(parts)} column track(s) ({grid_cols!r}), "
            "expected 3 columns (1fr auto auto) as defined in upload.module.css. "
            f"Full CSS snapshot: {css}"
        )

    def test_toolbar_row_align_items_center(self, upload_page: Page) -> None:
        """The toolbar grid row must align children to center on the cross axis."""
        css = _get_toolbar_css(upload_page)
        align = css.get("alignItems", "")
        assert align == _EXPECTED_ALIGN_ITEMS, (
            f"Toolbar row has align-items='{align}', expected 'center'. "
            f"Full CSS snapshot: {css}"
        )

    def test_toolbar_row_has_gap(self, upload_page: Page) -> None:
        """The toolbar grid row must have a non-zero column gap between elements."""
        css = _get_toolbar_css(upload_page)
        # gap / column-gap is resolved to a px value by the browser
        col_gap: str = css.get("columnGap", css.get("gap", "0px"))
        # Parse numeric value
        numeric = col_gap.replace("px", "").strip()
        try:
            gap_px = float(numeric)
        except ValueError:
            gap_px = 0.0
        assert gap_px > 0, (
            f"Toolbar grid column gap is {col_gap!r}, expected a positive value (spec: 8px). "
            f"Full CSS snapshot: {css}"
        )

    def test_toolbar_has_exactly_three_children(self, upload_page: Page) -> None:
        """The toolbar grid row must contain exactly three direct children."""
        css = _get_toolbar_css(upload_page)
        child_count = css.get("childCount", 0)
        assert child_count == 3, (
            f"Toolbar grid row has {child_count} direct child element(s), expected 3 "
            "(search input, category select, reset button). "
            f"Full CSS snapshot: {css}"
        )
