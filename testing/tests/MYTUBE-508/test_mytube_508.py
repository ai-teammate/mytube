"""
MYTUBE-508: Form input focus states — focus ring and border color apply accent styles

Objective
---------
Ensure that form inputs, selects, and textareas on the upload page display the
correct focus ring and border color when focused.

Steps
-----
1. Navigate to /upload page.
2. Click or tab into any text input or textarea.
3. Observe the border and box-shadow of the focused element.

Expected Result
---------------
Focused element displays:
  - box-shadow: 0 0 0 3px rgba(109, 64, 203, 0.1)
  - border-color: var(--accent-logo)  (#6d40cb in light mode)
  - background: var(--bg-page)
  - border-radius: 12px

Architecture
------------
- Dual-mode: static analysis (always) + live Playwright (when APP_URL is set).
- WebConfig from testing/core/config/web_config.py centralises env vars.
- UploadPage from testing/components/pages/upload_page/upload_page.py provides
  page-level navigation.
- CSS is inspected via getComputedStyle in the browser and via static file analysis.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.core.config.web_config import WebConfig
from testing.components.pages.upload_page.upload_page import UploadPage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_UPLOAD_CSS = _REPO_ROOT / "web" / "src" / "app" / "upload" / "upload.module.css"
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Expected values
# ---------------------------------------------------------------------------

_EXPECTED_BOX_SHADOW = "0 0 0 3px rgba(109, 64, 203, 0.1)"
_EXPECTED_BORDER_COLOR_TOKEN = "var(--accent-logo)"
_EXPECTED_BORDER_RADIUS_PX = "12px"
_EXPECTED_BG_TOKEN = "var(--bg-page)"
# Resolved hex for --accent-logo in light mode (from globals.css)
_ACCENT_LOGO_HEX = "#6d40cb"
# Resolved rgba forms of the accent logo color (browser normalises hex to rgb)
_ACCENT_LOGO_RGB = "rgb(109, 64, 203)"

_PAGE_LOAD_TIMEOUT = 30_000

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _should_use_live_mode() -> bool:
    env_url = os.getenv("APP_URL", os.getenv("WEB_BASE_URL", ""))
    return bool(env_url and env_url.lower() not in ("false", "0", ""))


def _read_css(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_rule_block(css: str, selector: str) -> str | None:
    """Extract the declaration block for the given CSS selector."""
    # Escape special chars for regex
    escaped = re.escape(selector)
    pattern = re.compile(
        escaped + r"\s*\{([^}]*)\}",
        re.DOTALL,
    )
    m = pattern.search(css)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# Static analysis helpers
# ---------------------------------------------------------------------------


def _assert_focus_box_shadow(css: str, selector: str) -> None:
    block = _extract_rule_block(css, selector)
    assert block is not None, (
        f"CSS rule '{selector}' not found in upload.module.css. "
        "The focus rule must be defined for form inputs."
    )
    assert "0 0 0 3px rgba(109, 64, 203, 0.1)" in block or \
           "0 0 0 3px rgba(109,64,203,0.1)" in block, (
        f"'{selector}' must declare box-shadow: 0 0 0 3px rgba(109, 64, 203, 0.1). "
        f"Actual block: {block.strip()}"
    )


def _assert_focus_border_color(css: str, selector: str) -> None:
    block = _extract_rule_block(css, selector)
    assert block is not None, (
        f"CSS rule '{selector}' not found in upload.module.css."
    )
    assert "border-color: var(--accent-logo)" in block or \
           "border-color:var(--accent-logo)" in block, (
        f"'{selector}' must declare border-color: var(--accent-logo). "
        f"Actual block: {block.strip()}"
    )


def _assert_base_background(css: str, selector: str) -> None:
    block = _extract_rule_block(css, selector)
    assert block is not None, (
        f"CSS rule '{selector}' not found in upload.module.css."
    )
    assert "var(--bg-page)" in block, (
        f"'{selector}' must declare background: var(--bg-page). "
        f"Actual block: {block.strip()}"
    )


def _assert_base_border_radius(css: str, selector: str) -> None:
    block = _extract_rule_block(css, selector)
    assert block is not None, (
        f"CSS rule '{selector}' not found in upload.module.css."
    )
    assert "border-radius: 12px" in block or "border-radius:12px" in block, (
        f"'{selector}' must declare border-radius: 12px. "
        f"Actual block: {block.strip()}"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def live_browser(config: WebConfig):
    """Yield a Playwright Page pre-navigated to /upload."""
    if not _should_use_live_mode():
        pytest.skip("Live mode skipped: APP_URL/WEB_BASE_URL not set")

    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=config.headless,
            slow_mo=config.slow_mo,
        )
        page = browser.new_page(viewport={"width": 1280, "height": 720})
        upload = UploadPage(page)
        upload.navigate(config.base_url)
        # Wait for the title input to appear (page may redirect if unauthenticated)
        try:
            page.locator('input[id="title"]').wait_for(state="visible", timeout=_PAGE_LOAD_TIMEOUT)
        except Exception:
            pass
        yield page
        browser.close()


# ---------------------------------------------------------------------------
# Static tests (always run — no browser required)
# ---------------------------------------------------------------------------


class TestFormControlFocusStatic:
    """MYTUBE-508 (Static): Verify focus styles are correctly defined in CSS source."""

    def test_formcontrol_focus_box_shadow(self) -> None:
        """
        Step 2 (static) — .formControl:focus must declare the accent focus ring.
        """
        css = _read_css(_UPLOAD_CSS)
        _assert_focus_box_shadow(css, ".formControl:focus")

    def test_formcontrol_focus_border_color(self) -> None:
        """
        Step 2 (static) — .formControl:focus must declare border-color: var(--accent-logo).
        """
        css = _read_css(_UPLOAD_CSS)
        _assert_focus_border_color(css, ".formControl:focus")

    def test_selectcontrol_focus_box_shadow(self) -> None:
        """
        Step 2 (static) — .selectControl:focus must declare the accent focus ring.
        """
        css = _read_css(_UPLOAD_CSS)
        _assert_focus_box_shadow(css, ".selectControl:focus")

    def test_selectcontrol_focus_border_color(self) -> None:
        """
        Step 2 (static) — .selectControl:focus must declare border-color: var(--accent-logo).
        """
        css = _read_css(_UPLOAD_CSS)
        _assert_focus_border_color(css, ".selectControl:focus")

    def test_formcontrol_base_background(self) -> None:
        """
        Step 3 (static) — .formControl base must have background: var(--bg-page).
        """
        css = _read_css(_UPLOAD_CSS)
        _assert_base_background(css, ".formControl")

    def test_formcontrol_base_border_radius(self) -> None:
        """
        Step 3 (static) — .formControl base must have border-radius: 12px.
        """
        css = _read_css(_UPLOAD_CSS)
        _assert_base_border_radius(css, ".formControl")

    def test_selectcontrol_base_background(self) -> None:
        """
        Step 3 (static) — .selectControl base must have background: var(--bg-page).
        """
        css = _read_css(_UPLOAD_CSS)
        _assert_base_background(css, ".selectControl")

    def test_selectcontrol_base_border_radius(self) -> None:
        """
        Step 3 (static) — .selectControl base must have border-radius: 12px.
        """
        css = _read_css(_UPLOAD_CSS)
        _assert_base_border_radius(css, ".selectControl")

    def test_globals_css_defines_accent_logo(self) -> None:
        """
        Step 3 (static) — globals.css must define --accent-logo CSS variable.
        """
        css = _read_css(_GLOBALS_CSS)
        root_match = re.search(r":root\s*\{([^}]*)\}", css, re.DOTALL)
        assert root_match, "globals.css :root block not found"
        root_block = root_match.group(1)
        assert "--accent-logo" in root_block, (
            "globals.css :root block must define --accent-logo token. "
            "The focus border-color depends on this CSS variable."
        )

    def test_globals_css_defines_bg_page(self) -> None:
        """
        Step 3 (static) — globals.css must define --bg-page CSS variable.
        """
        css = _read_css(_GLOBALS_CSS)
        root_match = re.search(r":root\s*\{([^}]*)\}", css, re.DOTALL)
        assert root_match, "globals.css :root block not found"
        root_block = root_match.group(1)
        assert "--bg-page" in root_block, (
            "globals.css :root block must define --bg-page token. "
            "The input background depends on this CSS variable."
        )


# ---------------------------------------------------------------------------
# Live Playwright tests (only run when APP_URL / WEB_BASE_URL is set)
# ---------------------------------------------------------------------------


class TestFormControlFocusLive:
    """MYTUBE-508 (Live): Verify computed focus styles on the deployed /upload page."""

    def _get_focused_styles(self, page, selector: str) -> dict:
        """Focus the element and return its computed box-shadow, border-color,
        background-color, and border-radius."""
        return page.evaluate(
            """(sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                el.focus();
                const cs = window.getComputedStyle(el);
                return {
                    boxShadow:    cs.boxShadow,
                    borderColor:  cs.borderColor,
                    background:   cs.backgroundColor,
                    borderRadius: cs.borderRadius,
                };
            }""",
            selector,
        )

    def test_title_input_focus_box_shadow(self, live_browser) -> None:
        """
        Step 2 (live) — title input (#title) focused box-shadow must be the accent ring.
        """
        styles = self._get_focused_styles(live_browser, 'input[id="title"]')
        assert styles is not None, "Could not find title input on /upload page."
        # Browser normalises: "0 0 0 3px rgba(109, 64, 203, 0.1)"
        assert "rgba(109, 64, 203, 0.1)" in styles["boxShadow"] or \
               "rgba(109,64,203,0.1)" in styles["boxShadow"], (
            f"Title input focused box-shadow is '{styles['boxShadow']}'. "
            f"Expected it to contain '0 0 0 3px rgba(109, 64, 203, 0.1)'."
        )

    def test_title_input_focus_border_color(self, live_browser) -> None:
        """
        Step 2 (live) — title input focused border-color must resolve to --accent-logo.
        """
        styles = self._get_focused_styles(live_browser, 'input[id="title"]')
        assert styles is not None, "Could not find title input on /upload page."
        assert _ACCENT_LOGO_RGB in styles["borderColor"] or \
               _ACCENT_LOGO_HEX.lower() in styles["borderColor"].lower(), (
            f"Title input focused borderColor is '{styles['borderColor']}'. "
            f"Expected '{_ACCENT_LOGO_RGB}' (resolved from var(--accent-logo))."
        )

    def test_title_input_base_border_radius(self, live_browser) -> None:
        """
        Step 3 (live) — title input border-radius must be 12px.
        """
        styles = self._get_focused_styles(live_browser, 'input[id="title"]')
        assert styles is not None, "Could not find title input on /upload page."
        assert styles["borderRadius"] == _EXPECTED_BORDER_RADIUS_PX, (
            f"Title input borderRadius is '{styles['borderRadius']}', "
            f"expected '{_EXPECTED_BORDER_RADIUS_PX}'."
        )

    def test_description_textarea_focus_box_shadow(self, live_browser) -> None:
        """
        Step 2 (live) — description textarea focused box-shadow must be the accent ring.
        """
        styles = self._get_focused_styles(live_browser, 'textarea[id="description"]')
        assert styles is not None, "Could not find description textarea on /upload page."
        assert "rgba(109, 64, 203, 0.1)" in styles["boxShadow"] or \
               "rgba(109,64,203,0.1)" in styles["boxShadow"], (
            f"Description textarea focused box-shadow is '{styles['boxShadow']}'. "
            f"Expected it to contain 'rgba(109, 64, 203, 0.1)'."
        )

    def test_description_textarea_focus_border_color(self, live_browser) -> None:
        """
        Step 2 (live) — description textarea focused border-color must resolve to --accent-logo.
        """
        styles = self._get_focused_styles(live_browser, 'textarea[id="description"]')
        assert styles is not None, "Could not find description textarea on /upload page."
        assert _ACCENT_LOGO_RGB in styles["borderColor"] or \
               _ACCENT_LOGO_HEX.lower() in styles["borderColor"].lower(), (
            f"Description textarea focused borderColor is '{styles['borderColor']}'. "
            f"Expected '{_ACCENT_LOGO_RGB}' (resolved from var(--accent-logo))."
        )

    def test_category_select_focus_box_shadow(self, live_browser) -> None:
        """
        Step 2 (live) — category select (#categoryId) focused box-shadow must be the accent ring.
        """
        styles = self._get_focused_styles(live_browser, 'select[id="categoryId"]')
        assert styles is not None, "Could not find category select on /upload page."
        assert "rgba(109, 64, 203, 0.1)" in styles["boxShadow"] or \
               "rgba(109,64,203,0.1)" in styles["boxShadow"], (
            f"Category select focused box-shadow is '{styles['boxShadow']}'. "
            f"Expected it to contain 'rgba(109, 64, 203, 0.1)'."
        )

    def test_tags_input_focus_box_shadow(self, live_browser) -> None:
        """
        Step 2 (live) — tags input (#tags) focused box-shadow must be the accent ring.
        """
        styles = self._get_focused_styles(live_browser, 'input[id="tags"]')
        assert styles is not None, "Could not find tags input on /upload page."
        assert "rgba(109, 64, 203, 0.1)" in styles["boxShadow"] or \
               "rgba(109,64,203,0.1)" in styles["boxShadow"], (
            f"Tags input focused box-shadow is '{styles['boxShadow']}'. "
            f"Expected it to contain 'rgba(109, 64, 203, 0.1)'."
        )
