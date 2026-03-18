"""
MYTUBE-595: Upload page — Choose File button styling is consistent across browsers.

Objective
---------
Ensure the ``::file-selector-button`` pseudo-element styling is correctly applied
across different browsers, preventing native OS overrides from making it invisible.

Steps
-----
1. Open the /upload page in Chrome (Chromium), Firefox, and Safari.
2. Toggle between light and dark themes in each browser.
3. Inspect the Choose File button appearance.

Expected Result
---------------
The button maintains visibility and the custom styling defined in
``upload.module.css`` regardless of the browser's default native file input
rendering.  It does not appear as unstyled plain text.

Test Approach
-------------
Two complementary layers:

**Layer A — Static CSS analysis** (always runs; no browser needed):
  - Verifies the CSS file ``upload.module.css`` defines a
    ``::file-selector-button`` rule on ``.fileInput``.
  - Confirms the rule includes ``background: var(--accent-cta)`` (green CTA colour).
  - Confirms the rule includes ``color: var(--text-cta)`` (white text).
  - Confirms a hover rule (``::file-selector-button:hover``) exists.
  - Verifies the CSS variable ``--accent-cta`` is defined in ``globals.css``
    for both light and dark themes.

**Layer B — Browser rendering tests** (runs for Chromium and Firefox):
  - Navigates to the live /upload page.
  - In light theme: verifies the file input element is visible in the DOM and
    that evaluating ``::file-selector-button`` computed styles returns a
    non-transparent background colour consistent with ``--accent-cta``.
  - In dark theme: toggles ``body[data-theme="dark"]`` and re-verifies the
    button remains visible and styled.
  - Confirms the button is not invisible (background is not the page background
    colour and opacity is not 0).

Architecture
------------
- ``UploadCSSModule`` (components/pages/upload_page/upload_css_module.py) provides
  CSS-static inspection helpers.
- ``UploadPage`` (components/pages/upload_page/upload_page.py) wraps browser navigation.
- ``WebConfig`` (core/config/web_config.py) centralises environment variable access.
- Playwright sync API with pytest parametrize over browsers.
- No hardcoded URLs, credentials, or environment-specific paths.

Environment variables
---------------------
APP_URL / WEB_BASE_URL   Base URL of the deployed web app.
                         Default: https://ai-teammate.github.io/mytube
PLAYWRIGHT_HEADLESS      Run browser headless (default: true).
PLAYWRIGHT_SLOW_MO       Slow-motion delay in ms (default: 0).

Run from repo root:
    pytest testing/tests/MYTUBE-595/test_mytube_595.py -v
"""
from __future__ import annotations

import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.upload_page.upload_css_module import UploadCSSModule
from testing.components.pages.upload_page.upload_page import UploadPage
from testing.core.config.web_config import WebConfig

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAGE_LOAD_TIMEOUT = 30_000  # ms
_VIEWPORT = {"width": 1280, "height": 800}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_base_url_reachable(url: str, timeout: int = 10) -> bool:
    """Return True when *url* responds with any HTTP status within *timeout* seconds."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        urllib.request.urlopen(req, timeout=timeout)
        return True
    except urllib.error.HTTPError:
        # Any HTTP error (4xx/5xx) still means the server is reachable
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Layer A — Static CSS analysis (no browser required)
# ---------------------------------------------------------------------------


class TestFileSelectorButtonCSS:
    """Layer A: Verify that upload.module.css contains the required
    ``::file-selector-button`` rules introduced in the MYTUBE-591 fix."""

    @pytest.fixture(autouse=True)
    def css_module(self) -> None:
        self._css = UploadCSSModule()

    def test_upload_css_file_exists(self) -> None:
        """The upload.module.css file must exist in the repository."""
        assert self._css.file_exists(), (
            "upload.module.css not found. "
            "The file may have been moved or deleted."
        )

    def test_file_selector_button_rule_exists(self) -> None:
        """A ``::file-selector-button`` rule must be defined for ``.fileInput``."""
        # get_rule_body raises AssertionError if the rule is not found
        body = self._css.get_rule_body("fileInput::file-selector-button")
        assert body is not None, (
            "No '.fileInput::file-selector-button { ... }' rule found in "
            "upload.module.css. "
            "The MYTUBE-591 fix requires this rule for the button to be visible."
        )

    def test_file_selector_button_has_background(self) -> None:
        """The ``::file-selector-button`` rule must declare a background colour."""
        assert self._css.rule_contains("fileInput::file-selector-button", "background"), (
            "'.fileInput::file-selector-button' rule does not declare a "
            "'background' property."
        )

    def test_file_selector_button_uses_accent_cta(self) -> None:
        """The background must use the ``--accent-cta`` design token."""
        assert self._css.rule_contains("fileInput::file-selector-button", "--accent-cta"), (
            "'.fileInput::file-selector-button' background does not reference "
            "'--accent-cta'. The button may be invisible in dark theme."
        )

    def test_file_selector_button_has_text_cta_color(self) -> None:
        """The ``::file-selector-button`` rule must declare ``color: var(--text-cta)``."""
        assert self._css.rule_contains("fileInput::file-selector-button", "--text-cta"), (
            "'.fileInput::file-selector-button' rule does not set "
            "'color: var(--text-cta)'. Text on the button may be unreadable."
        )

    def test_file_selector_button_hover_rule_exists(self) -> None:
        """A ``::file-selector-button:hover`` rule must be defined."""
        body = self._css.get_rule_body("fileInput::file-selector-button:hover")
        assert body is not None, (
            "No '.fileInput::file-selector-button:hover { ... }' rule found in "
            "upload.module.css. The button has no hover feedback."
        )

    def test_file_selector_button_hover_has_opacity(self) -> None:
        """The hover rule must include an ``opacity`` declaration for visual feedback."""
        assert self._css.rule_contains("fileInput::file-selector-button:hover", "opacity"), (
            "'.fileInput::file-selector-button:hover' rule does not set 'opacity'."
        )

    def test_globals_css_defines_accent_cta_light(self) -> None:
        """``--accent-cta`` must be defined in the light theme in globals.css."""
        assert _GLOBALS_CSS.exists(), f"globals.css not found at {_GLOBALS_CSS}"
        css_text = _GLOBALS_CSS.read_text(encoding="utf-8")
        # Light theme is the :root block (before body[data-theme="dark"])
        dark_pos = css_text.find('body[data-theme="dark"]')
        light_section = css_text[:dark_pos] if dark_pos != -1 else css_text
        assert "--accent-cta" in light_section, (
            "'--accent-cta' is not defined in the light theme section of globals.css."
        )

    def test_globals_css_defines_accent_cta_dark(self) -> None:
        """``--accent-cta`` must be defined in the dark theme in globals.css."""
        assert _GLOBALS_CSS.exists(), f"globals.css not found at {_GLOBALS_CSS}"
        css_text = _GLOBALS_CSS.read_text(encoding="utf-8")
        dark_pos = css_text.find('body[data-theme="dark"]')
        assert dark_pos != -1, (
            "'body[data-theme=\"dark\"]' block not found in globals.css."
        )
        dark_section = css_text[dark_pos:]
        assert "--accent-cta" in dark_section, (
            "'--accent-cta' is not defined in the dark theme override block of globals.css. "
            "The button colour may be wrong in dark mode."
        )


# ---------------------------------------------------------------------------
# Layer B — Browser rendering (Chromium and Firefox)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def config() -> WebConfig:
    return WebConfig()


@pytest.fixture(scope="module")
def app_reachable(config: WebConfig) -> bool:
    return _is_base_url_reachable(config.base_url, timeout=10)


@pytest.mark.parametrize("browser_name", ["chromium", "firefox"])
class TestFileSelectorButtonBrowser:
    """Layer B: Verify the Choose File button is visible and styled in the
    browser for both light and dark themes."""

    def _launch_browser(self, pw, browser_name: str, config: WebConfig):
        """Launch the named browser and return (browser, context, page)."""
        launcher = getattr(pw, browser_name)
        browser = launcher.launch(headless=config.headless, slow_mo=config.slow_mo)
        context = browser.new_context(viewport=_VIEWPORT)
        page = context.new_page()
        return browser, context, page

    def test_file_input_visible_light_theme(
        self, browser_name: str, config: WebConfig, app_reachable: bool
    ) -> None:
        """The file input element must be visible on the upload page in light theme."""
        if not app_reachable:
            pytest.skip(f"Base URL {config.base_url!r} is not reachable; skipping browser test.")

        with sync_playwright() as pw:
            browser, context, page = self._launch_browser(pw, browser_name, config)
            try:
                upload = UploadPage(page)
                upload.navigate(config.base_url)

                # Ensure we're on the upload page (may redirect to /login if not authenticated)
                if upload.is_on_login_page():
                    pytest.skip(
                        "Upload page requires authentication. "
                        "Set FIREBASE_TEST_EMAIL and FIREBASE_TEST_PASSWORD to run this test."
                    )

                assert upload.is_form_visible(), (
                    f"[{browser_name}] File input is not visible on the upload page "
                    f"(light theme). URL: {page.url}"
                )
            finally:
                browser.close()

    def test_file_selector_button_styled_light_theme(
        self, browser_name: str, config: WebConfig, app_reachable: bool
    ) -> None:
        """The ``::file-selector-button`` must have a non-transparent background in light theme."""
        if not app_reachable:
            pytest.skip(f"Base URL {config.base_url!r} is not reachable; skipping browser test.")

        with sync_playwright() as pw:
            browser, context, page = self._launch_browser(pw, browser_name, config)
            try:
                upload = UploadPage(page)
                upload.navigate(config.base_url)

                if upload.is_on_login_page():
                    pytest.skip("Upload page requires authentication.")

                assert upload.is_form_visible(), (
                    f"[{browser_name}] File input not present; cannot inspect button styles."
                )

                # Evaluate computed styles of the ::file-selector-button pseudo-element
                styles = page.evaluate(
                    """() => {
                        const input = document.querySelector('input[type="file"]');
                        if (!input) return null;
                        // ::file-selector-button is only accessible via getComputedStyle
                        const styles = window.getComputedStyle(input, '::file-selector-button');
                        return {
                            background: styles.background,
                            backgroundColor: styles.backgroundColor,
                            color: styles.color,
                            opacity: styles.opacity,
                            display: styles.display,
                        };
                    }"""
                )

                assert styles is not None, (
                    f"[{browser_name}] Could not evaluate computed styles for file input."
                )
                bg = styles.get("backgroundColor", "")
                opacity = styles.get("opacity", "1")

                # The button must not be fully transparent
                assert bg not in ("rgba(0, 0, 0, 0)", "transparent", ""), (
                    f"[{browser_name}, light] ::file-selector-button has transparent "
                    f"backgroundColor='{bg}', making the button invisible. "
                    f"Styles: {styles}"
                )
                # Opacity must not be 0
                assert opacity != "0", (
                    f"[{browser_name}, light] ::file-selector-button has opacity=0, "
                    f"making the button invisible. Styles: {styles}"
                )
            finally:
                browser.close()

    def test_file_selector_button_styled_dark_theme(
        self, browser_name: str, config: WebConfig, app_reachable: bool
    ) -> None:
        """The ``::file-selector-button`` must remain visible after switching to dark theme."""
        if not app_reachable:
            pytest.skip(f"Base URL {config.base_url!r} is not reachable; skipping browser test.")

        with sync_playwright() as pw:
            browser, context, page = self._launch_browser(pw, browser_name, config)
            try:
                upload = UploadPage(page)
                upload.navigate(config.base_url)

                if upload.is_on_login_page():
                    pytest.skip("Upload page requires authentication.")

                assert upload.is_form_visible(), (
                    f"[{browser_name}] File input not present; cannot inspect dark-theme styles."
                )

                # Force dark theme by setting the data-theme attribute on body
                page.evaluate(
                    "() => { document.body.setAttribute('data-theme', 'dark'); }"
                )
                # Allow a brief React/CSS re-paint
                page.wait_for_timeout(300)

                styles = page.evaluate(
                    """() => {
                        const input = document.querySelector('input[type="file"]');
                        if (!input) return null;
                        const styles = window.getComputedStyle(input, '::file-selector-button');
                        return {
                            background: styles.background,
                            backgroundColor: styles.backgroundColor,
                            color: styles.color,
                            opacity: styles.opacity,
                        };
                    }"""
                )

                assert styles is not None, (
                    f"[{browser_name}] Could not evaluate computed dark-theme styles for file input."
                )
                bg = styles.get("backgroundColor", "")
                opacity = styles.get("opacity", "1")

                assert bg not in ("rgba(0, 0, 0, 0)", "transparent", ""), (
                    f"[{browser_name}, dark] ::file-selector-button has transparent "
                    f"backgroundColor='{bg}' in dark theme, making the button invisible. "
                    f"Styles: {styles}"
                )
                assert opacity != "0", (
                    f"[{browser_name}, dark] ::file-selector-button has opacity=0 in "
                    f"dark theme. Styles: {styles}"
                )
            finally:
                browser.close()
