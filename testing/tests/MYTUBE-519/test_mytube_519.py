"""
MYTUBE-519: Search and category filter styling — borderless inputs and focus behavior verified.

Objective
---------
Verify the styling and focus effects of the search and category controls in
the dashboard toolbar.

Steps
-----
1. Inspect the search input and category select element in the toolbar.
2. Click into the search input to trigger focus.
3. Inspect the select element's dropdown indicator.

Expected Result
---------------
Both elements have ``background: var(--bg-content)``, ``border-radius: 12px``,
are borderless (``border: none``), and display a focus box-shadow.
The select element features a custom chevron SVG (via ``background-image``).

Architecture & Testing Strategy
--------------------------------
**Dual-mode** approach:

1. **Live mode** (primary): When ``APP_URL`` / ``WEB_BASE_URL`` is set AND
   ``FIREBASE_TEST_EMAIL`` + ``FIREBASE_TEST_PASSWORD`` are set, the test
   authenticates and navigates to the real ``/dashboard/`` page.

2. **Fixture mode** (fallback): Uses a self-contained HTML page that reproduces
   the toolbar markup and CSS from ``_content.module.css`` / ``globals.css``
   exactly — including CSS variable definitions — so that computed style
   assertions are identical to the production app.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
FIREBASE_TEST_EMAIL      Email of test Firebase user (optional, live mode only).
FIREBASE_TEST_PASSWORD   Password of test Firebase user (optional, live mode only).
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).
"""
from __future__ import annotations

import os
import pathlib
import sys

import pytest
from playwright.sync_api import sync_playwright, Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Constants — expected computed values
# ---------------------------------------------------------------------------

# --bg-content light-theme value (from globals.css :root)
_EXPECTED_BG_CONTENT = "#ffffff"
# --accent-logo light-theme value
_EXPECTED_ACCENT_LOGO = "#6d40cb"

_EXPECTED_BORDER_RADIUS = "12px"
_EXPECTED_BORDER_STYLE = "none"

# Focus ring: 0 0 0 2px var(--accent-logo)  →  0 0 0 2px rgb(109, 64, 203)
_EXPECTED_BOX_SHADOW_PARTIAL = "rgb(109, 64, 203)"

_PAGE_LOAD_TIMEOUT = 30_000  # ms


# ---------------------------------------------------------------------------
# Fixture HTML helper
# ---------------------------------------------------------------------------


def _get_fixture_html() -> str:
    """Return a self-contained HTML page reproducing the dashboard toolbar.

    Loads the actual production CSS files (``globals.css`` and
    ``_content.module.css``) from the repository at runtime so that the
    fixture reflects real CSS changes and can detect regressions.
    """
    repo_root = pathlib.Path(__file__).parents[3]
    css_globals = (repo_root / "web/src/app/globals.css").read_text()
    css_content = (repo_root / "web/src/app/dashboard/_content.module.css").read_text()
    # Strip @import directives that cannot be resolved in a plain HTML context
    css_globals_clean = "\n".join(
        line for line in css_globals.splitlines() if not line.strip().startswith("@import")
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>MYTUBE-519 toolbar fixture</title>
  <style>{css_globals_clean}</style>
  <style>{css_content}</style>
</head>
<body>
  <div class="toolbar">
    <div class="toolbarGrid">
      <input
        type="search"
        id="search-input"
        aria-label="Search videos"
        placeholder="Search videos…"
        class="toolbarInput"
      />
      <select
        id="category-select"
        aria-label="Filter by category"
        class="toolbarSelect"
      >
        <option value="">All categories</option>
        <option value="1">Education</option>
        <option value="2">Entertainment</option>
      </select>
      <button class="btnReset">Reset filters</button>
    </div>
  </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Mode helpers
# ---------------------------------------------------------------------------


def _should_use_live_mode(config: WebConfig) -> bool:
    """Return True when both a deployed URL and Firebase credentials are set."""
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", "")).strip()
    has_url = bool(env_url and env_url.lower() not in ("false", "0", ""))
    has_creds = bool(config.test_email and config.test_password)
    return has_url and has_creds


def _rgb_to_hex(rgb: str) -> str:
    """Convert 'rgb(r, g, b)' to '#rrggbb' lowercase."""
    rgb = rgb.strip()
    if rgb.startswith("rgb("):
        parts = rgb[4:-1].split(",")
        r, g, b = [int(p.strip()) for p in parts]
        return f"#{r:02x}{g:02x}{b:02x}"
    return rgb.lower()


def _get_computed(page: Page, selector: str, prop: str) -> str:
    """Return the computed style *prop* for the first element matching *selector*."""
    return page.evaluate(
        """([sel, prop]) => {
            const el = document.querySelector(sel);
            if (!el) return '';
            return getComputedStyle(el).getPropertyValue(prop).trim();
        }""",
        [selector, prop],
    )


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def browser_page(config: WebConfig):
    """Launch Chromium, load the toolbar (fixture or live), yield the page."""
    headless = os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
    slow_mo = int(os.getenv("PLAYWRIGHT_SLOW_MO", "0"))

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=headless, slow_mo=slow_mo)
        context = browser.new_context()
        page = context.new_page()

        if _should_use_live_mode(config):
            # --- Live mode: authenticate then navigate to /dashboard/ ---
            from testing.components.pages.register_page.register_page import RegisterPage  # noqa: F401
            # Sign in via /login page (Firebase email/password)
            page.goto(f"{config.base_url}/login/", timeout=_PAGE_LOAD_TIMEOUT,
                      wait_until="domcontentloaded")
            # Fill email and password
            page.get_by_label("Email").fill(config.test_email)
            page.get_by_label("Password").fill(config.test_password)
            page.get_by_role("button", name="Sign in").click()
            page.wait_for_url(lambda url: "/dashboard" in url or url == config.base_url + "/",
                              timeout=_PAGE_LOAD_TIMEOUT)
            page.goto(config.dashboard_url(), timeout=_PAGE_LOAD_TIMEOUT,
                      wait_until="networkidle")
            # Wait for toolbar to appear (only shown when videos exist)
            page.wait_for_selector(".toolbarInput, input[aria-label='Search videos']",
                                   timeout=15_000)
        else:
            # --- Fixture mode: self-contained HTML page ---
            page.set_content(_get_fixture_html(), wait_until="domcontentloaded")

        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestToolbarStyling:
    """MYTUBE-519: Verify borderless input / select styling in dashboard toolbar."""

    # ── Step 1: background and border-radius ────────────────────────────────

    def test_search_input_background(self, browser_page: Page) -> None:
        """Search input background must resolve to --bg-content (#ffffff light)."""
        selector = "input[aria-label='Search videos']"
        raw = _get_computed(browser_page, selector, "background-color")
        assert raw, f"Could not read background-color from search input (selector: {selector!r})"
        hex_val = _rgb_to_hex(raw)
        assert hex_val == _EXPECTED_BG_CONTENT, (
            f"Search input background: expected {_EXPECTED_BG_CONTENT!r}, got {raw!r} ({hex_val!r}). "
            "The .toolbarInput class must set 'background: var(--bg-content)'."
        )

    def test_category_select_background(self, browser_page: Page) -> None:
        """Category select background must resolve to --bg-content (#ffffff light)."""
        selector = "select[aria-label='Filter by category']"
        raw = _get_computed(browser_page, selector, "background-color")
        assert raw, f"Could not read background-color from select (selector: {selector!r})"
        hex_val = _rgb_to_hex(raw)
        assert hex_val == _EXPECTED_BG_CONTENT, (
            f"Category select background: expected {_EXPECTED_BG_CONTENT!r}, got {raw!r} ({hex_val!r}). "
            "The .toolbarSelect class must set 'background: var(--bg-content)'."
        )

    def test_search_input_border_radius(self, browser_page: Page) -> None:
        """Search input must have border-radius: 12px."""
        selector = "input[aria-label='Search videos']"
        raw = _get_computed(browser_page, selector, "border-radius")
        assert raw == _EXPECTED_BORDER_RADIUS, (
            f"Search input border-radius: expected {_EXPECTED_BORDER_RADIUS!r}, got {raw!r}. "
            "The .toolbarInput class must set 'border-radius: 12px'."
        )

    def test_category_select_border_radius(self, browser_page: Page) -> None:
        """Category select must have border-radius: 12px."""
        selector = "select[aria-label='Filter by category']"
        raw = _get_computed(browser_page, selector, "border-radius")
        assert raw == _EXPECTED_BORDER_RADIUS, (
            f"Category select border-radius: expected {_EXPECTED_BORDER_RADIUS!r}, got {raw!r}. "
            "The .toolbarSelect class must set 'border-radius: 12px'."
        )

    def test_search_input_is_borderless(self, browser_page: Page) -> None:
        """Search input must have border: none (border-style = none)."""
        selector = "input[aria-label='Search videos']"
        border_style = _get_computed(browser_page, selector, "border-top-style")
        assert border_style in ("none", ""), (
            f"Search input border-top-style: expected 'none', got {border_style!r}. "
            "The .toolbarInput class must set 'border: none'."
        )

    def test_category_select_is_borderless(self, browser_page: Page) -> None:
        """Category select must have border: none (border-style = none)."""
        selector = "select[aria-label='Filter by category']"
        border_style = _get_computed(browser_page, selector, "border-top-style")
        assert border_style in ("none", ""), (
            f"Category select border-top-style: expected 'none', got {border_style!r}. "
            "The .toolbarSelect class must set 'border: none'."
        )

    # ── Step 2: focus box-shadow on search input ─────────────────────────────

    def test_search_input_focus_box_shadow(self, browser_page: Page) -> None:
        """Clicking the search input must apply a focus box-shadow containing --accent-logo color."""
        selector = "input[aria-label='Search videos']"
        browser_page.locator(selector).click()
        browser_page.wait_for_function(
            """([sel, partial]) => {
                const el = document.querySelector(sel);
                if (!el) return false;
                return getComputedStyle(el).getPropertyValue('box-shadow').includes(partial);
            }""",
            arg=[selector, _EXPECTED_BOX_SHADOW_PARTIAL],
            timeout=5_000,
        )
        box_shadow = _get_computed(browser_page, selector, "box-shadow")
        assert _EXPECTED_BOX_SHADOW_PARTIAL in box_shadow, (
            f"Search input focus box-shadow: expected to contain {_EXPECTED_BOX_SHADOW_PARTIAL!r}, "
            f"got {box_shadow!r}. "
            "The .toolbarInput:focus rule must set 'box-shadow: 0 0 0 2px var(--accent-logo)'."
        )
        # Blur to restore default state for subsequent tests
        browser_page.locator(selector).blur()

    # ── Step 3: custom chevron SVG on select ─────────────────────────────────

    def test_category_select_has_custom_chevron(self, browser_page: Page) -> None:
        """Category select must use a custom chevron SVG via background-image (appearance: none)."""
        selector = "select[aria-label='Filter by category']"

        # Check appearance: none (native dropdown arrow removed)
        appearance = _get_computed(browser_page, selector, "appearance")
        assert appearance == "none", (
            f"Category select appearance: expected 'none' (custom arrow removed), got {appearance!r}. "
            "The .toolbarSelect class must set 'appearance: none'."
        )

        # Check background-image contains an SVG data URI with the chevron
        bg_image = _get_computed(browser_page, selector, "background-image")
        assert "svg" in bg_image.lower() or "url(" in bg_image.lower(), (
            f"Category select background-image does not contain an SVG chevron. "
            f"Got: {bg_image!r}. "
            "The .toolbarSelect class must set a custom SVG background-image for the dropdown indicator."
        )
