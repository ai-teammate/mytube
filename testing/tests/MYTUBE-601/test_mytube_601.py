"""
MYTUBE-601: Dashboard status badges — colors adapt correctly to dark theme tokens

Objective
---------
Verify that status badges in ``DashboardVideoCard`` use design tokens and remain
readable when dark theme is active, replacing hardcoded hex values.

Preconditions
-------------
User has videos in Ready, Processing, Pending, and Failed states.
Dark theme is enabled (``body[data-theme="dark"]``).

Steps
-----
1. Navigate to the Dashboard page.
2. Identify the status badge for each video state.
3. Inspect the element styles in the browser console.

Expected Result
---------------
Status badges do not use hardcoded hex values (e.g., ``#dcfce7``, ``#fef9c3``).
They use CSS variables (design tokens) that provide high contrast and correct
coloring for dark mode (e.g., ``var(--status-ready-bg)`` etc.).

Test Strategy
-------------
Dual-mode approach:

**Static analysis** (always runs): Parses ``DashboardVideoCard.module.css`` to
verify each status badge class (``.statusReady``, ``.statusProcessing``,
``.statusPending``, ``.statusFailed``) uses ``var(--status-*-bg)`` and
``var(--status-*-fg)`` tokens instead of hardcoded hex values.

**Playwright fixture mode** (always runs): Renders a self-contained HTML page
embedding the exact CSS from ``DashboardVideoCard.module.css`` and ``globals.css``
with ``data-theme="dark"`` set on the ``<body>`` element.  Asserts computed
``background-color`` and ``color`` for each badge class match the expected
dark-mode token values defined in ``globals.css``.

Architecture
------------
- Playwright sync API with pytest module-scoped fixtures.
- HTML fixture mode uses ``page.set_content()`` with inline CSS — no external deps.

Linked bugs
-----------
MYTUBE-593 (Done): Dashboard status badge classes in DashboardVideoCard.module.css
used hardcoded light-theme hex values for background and foreground colours.
Fix replaced all hardcoded values with CSS design tokens:
  .statusReady       → background: var(--status-ready-bg);      color: var(--status-ready-fg)
  .statusProcessing  → background: var(--status-processing-bg); color: var(--status-processing-fg)
  .statusPending     → background: var(--status-pending-bg);    color: var(--status-pending-fg)
  .statusFailed      → background: var(--status-failed-bg);     color: var(--status-failed-fg)
"""
from __future__ import annotations

import pathlib
import re
import sys
import os

import pytest
from playwright.sync_api import Page

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_DASHBOARD_CARD_CSS = (
    _REPO_ROOT / "web" / "src" / "components" / "DashboardVideoCard.module.css"
)
_GLOBALS_CSS = _REPO_ROOT / "web" / "src" / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Expected resolved values in dark theme (from globals.css dark block)
# --status-ready-bg:       #14532d  → rgb(20, 83, 45)
# --status-ready-fg:       #86efac  → rgb(134, 239, 172)
# --status-processing-bg:  #713f12  → rgb(113, 63, 18)
# --status-processing-fg:  #fde68a  → rgb(253, 230, 138)
# --status-pending-bg:     #374151  → rgb(55, 65, 81)
# --status-pending-fg:     #d1d5db  → rgb(209, 213, 219)
# --status-failed-bg:      #7f1d1d  → rgb(127, 29, 29)
# --status-failed-fg:      #fca5a5  → rgb(252, 165, 165)
# ---------------------------------------------------------------------------

_DARK_EXPECTED: dict[str, tuple[str, str]] = {
    "statusReady": ("rgb(20, 83, 45)", "rgb(134, 239, 172)"),
    "statusProcessing": ("rgb(113, 63, 18)", "rgb(253, 230, 138)"),
    "statusPending": ("rgb(55, 65, 81)", "rgb(209, 213, 219)"),
    "statusFailed": ("rgb(127, 29, 29)", "rgb(252, 165, 165)"),
}

# Hardcoded light-theme hex values that must NOT appear in the badge rules
_FORBIDDEN_HEX: list[str] = [
    "#dcfce7", "#166534",
    "#fef9c3", "#854d0e",
    "#f3f4f6", "#374151",
    "#fee2e2", "#991b1b",
]

_STATUS_CLASSES = list(_DARK_EXPECTED.keys())

# ---------------------------------------------------------------------------
# CSS helpers
# ---------------------------------------------------------------------------


def _load_css(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_rule_body(css: str, class_name: str) -> str:
    """Return the declaration block for ``.{class_name}`` in *css*, or empty string."""
    pattern = rf"\.{re.escape(class_name)}\s*\{{([^}}]*)\}}"
    m = re.search(pattern, css, re.DOTALL)
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# HTML fixture builder
# ---------------------------------------------------------------------------


def _build_dark_theme_fixture() -> str:
    """Return a self-contained HTML page with dark theme and all status badges."""
    globals_css = _load_css(_GLOBALS_CSS)
    module_css = _load_css(_DASHBOARD_CARD_CSS)

    badges_html = "\n".join(
        f'  <span class="{cls}" id="{cls}">Label</span>'
        for cls in _STATUS_CLASSES
    )

    return (
        "<!DOCTYPE html>\n"
        "<html lang=\"en\">\n"
        "<head>\n"
        "  <meta charset=\"UTF-8\">\n"
        "  <title>Status Badge Dark Theme Fixture MYTUBE-601</title>\n"
        "  <style>" + globals_css + "</style>\n"
        "  <style>" + module_css + "</style>\n"
        "</head>\n"
        "<body data-theme=\"dark\">\n"
        + badges_html + "\n"
        "</body>\n"
        "</html>"
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def dark_fixture_page(browser):
    """Playwright page loaded with the dark-theme HTML fixture."""
    page = browser.new_page()
    page.set_content(
        _build_dark_theme_fixture(),
        wait_until="domcontentloaded",
    )
    yield page
    page.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_computed(page: Page, selector: str, prop: str) -> str:
    return page.evaluate(
        """([sel, prop]) => {
            const el = document.querySelector(sel);
            if (!el) return '';
            return getComputedStyle(el).getPropertyValue(prop).trim();
        }""",
        [selector, prop],
    )


# ---------------------------------------------------------------------------
# Tests — Static CSS analysis
# ---------------------------------------------------------------------------


class TestStatusBadgeStaticCSS:
    """Static analysis: verify badge classes use CSS tokens, not hardcoded hex."""

    @pytest.fixture(autouse=True)
    def _load(self) -> None:
        self.css = _load_css(_DASHBOARD_CARD_CSS)

    @pytest.mark.parametrize("class_name", _STATUS_CLASSES)
    def test_badge_rule_exists(self, class_name: str) -> None:
        """Badge rule for ``class_name`` must exist in DashboardVideoCard.module.css."""
        body = _extract_rule_body(self.css, class_name)
        assert body, (
            f"CSS rule '.{class_name}' not found in DashboardVideoCard.module.css. "
            "The status badge styling may be missing entirely."
        )

    @pytest.mark.parametrize("class_name", _STATUS_CLASSES)
    def test_badge_background_uses_token(self, class_name: str) -> None:
        """``background`` for ``class_name`` must reference a CSS variable, not hardcoded hex."""
        body = _extract_rule_body(self.css, class_name)
        token_key = class_name[0].lower() + class_name[1:]  # camelCase → camelCase
        # derive expected token name, e.g. statusReady → --status-ready-bg
        # Insert hyphens before uppercase letters: statusReady → status-Ready → status-ready
        snake = re.sub(r"(?<=[a-z])([A-Z])", r"-\1", class_name).lower()
        expected_token = f"var(--{snake}-bg)"
        assert expected_token in body, (
            f"'.{class_name}' background does not use '{expected_token}'. "
            f"Rule body: {body!r}. "
            "Replace the hardcoded colour with the CSS design token."
        )

    @pytest.mark.parametrize("class_name", _STATUS_CLASSES)
    def test_badge_color_uses_token(self, class_name: str) -> None:
        """``color`` for ``class_name`` must reference a CSS variable, not hardcoded hex."""
        body = _extract_rule_body(self.css, class_name)
        snake = re.sub(r"(?<=[a-z])([A-Z])", r"-\1", class_name).lower()
        expected_token = f"var(--{snake}-fg)"
        assert expected_token in body, (
            f"'.{class_name}' color does not use '{expected_token}'. "
            f"Rule body: {body!r}. "
            "Replace the hardcoded colour with the CSS design token."
        )

    @pytest.mark.parametrize("hex_value", _FORBIDDEN_HEX)
    def test_no_hardcoded_hex_in_badge_rules(self, hex_value: str) -> None:
        """No hardcoded hex colour value must appear in the status badge rules."""
        # Check each badge rule independently for clarity
        for class_name in _STATUS_CLASSES:
            body = _extract_rule_body(self.css, class_name)
            assert hex_value.lower() not in body.lower(), (
                f"Hardcoded hex value '{hex_value}' found in '.{class_name}' rule. "
                f"Rule body: {body!r}. "
                "This hardcoded colour breaks dark mode. Replace with the CSS token."
            )


# ---------------------------------------------------------------------------
# Tests — Playwright fixture (dark theme computed styles)
# ---------------------------------------------------------------------------


class TestStatusBadgeDarkThemeComputed:
    """Playwright: verify computed badge styles resolve to correct dark-theme colours."""

    @pytest.mark.parametrize("class_name,expected", list(_DARK_EXPECTED.items()))
    def test_badge_background_color_dark(
        self,
        dark_fixture_page: Page,
        class_name: str,
        expected: tuple[str, str],
    ) -> None:
        """
        In dark mode, ``background-color`` of the badge must resolve to the
        expected dark-theme token value.
        """
        expected_bg, _ = expected
        actual = _get_computed(dark_fixture_page, f"#{class_name}", "background-color")
        assert actual == expected_bg, (
            f"'.{class_name}' background-color in dark mode: "
            f"expected {expected_bg!r}, got {actual!r}. "
            "The badge background is not resolving to the correct dark-theme token value."
        )

    @pytest.mark.parametrize("class_name,expected", list(_DARK_EXPECTED.items()))
    def test_badge_text_color_dark(
        self,
        dark_fixture_page: Page,
        class_name: str,
        expected: tuple[str, str],
    ) -> None:
        """
        In dark mode, ``color`` of the badge must resolve to the
        expected dark-theme token value.
        """
        _, expected_fg = expected
        actual = _get_computed(dark_fixture_page, f"#{class_name}", "color")
        assert actual == expected_fg, (
            f"'.{class_name}' color in dark mode: "
            f"expected {expected_fg!r}, got {actual!r}. "
            "The badge text colour is not resolving to the correct dark-theme token value."
        )
