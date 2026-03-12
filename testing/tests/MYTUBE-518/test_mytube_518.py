"""
MYTUBE-518: Dashboard redesign styles — page heading and toolbar grid verified

Objective
---------
Verify the visual design of the dashboard heading and the toolbar container
according to the redesign specifications.

Steps
-----
1. Navigate to the Dashboard page.
2. Inspect the "My Videos" page heading.
3. Inspect the toolbar card container (.card.toolbar).

Expected Result
---------------
The heading has font-size: 24px and font-weight: 700.
The toolbar card has background: var(--bg-card), border-radius: 16px, and
uses a CSS grid row layout with columns 1fr 220px auto.

Test Approach
-------------
**Layer A — CSS module inspection** (no browser required):
    Reads web/src/app/dashboard/_content.module.css and verifies each CSS
    property is declared exactly as specified in the redesign ticket.

**Layer B — Source code structural analysis** (no browser required):
    Parses web/src/app/dashboard/_content.tsx to confirm:
    - The <h1> heading uses the sectionHeading style class.
    - The toolbar div uses the toolbar style class.
    - The toolbar grid div uses the toolbarGrid style class.

Architecture
------------
- CSSGlobalsPage from testing/components/pages/css_globals_page/ for --bg-card
  token verification.
- No browser / Playwright dependency — pure static analysis.
- Follows the two-layer approach used by MYTUBE-452.

Run from repo root:
    pytest testing/tests/MYTUBE-518/test_mytube_518.py -v
"""
from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from testing.components.pages.css_globals_page.css_globals_page import CSSGlobalsPage

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_DASHBOARD_CSS = os.path.join(
    _REPO_ROOT, "web", "src", "app", "dashboard", "_content.module.css"
)
_DASHBOARD_TSX = os.path.join(
    _REPO_ROOT, "web", "src", "app", "dashboard", "_content.tsx"
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_file(path: str) -> str:
    """Read file content, fail clearly if it does not exist."""
    if not os.path.isfile(path):
        pytest.fail(f"Source file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _extract_rule_block(css_text: str, class_name: str) -> str:
    """
    Return the declarations block of the first CSS rule for *class_name*.

    Searches for ``.classname {`` and returns the text between ``{`` and
    the matching ``}`` so that individual property assertions can be made
    against the raw source string.
    """
    pattern = re.compile(
        rf"\.{re.escape(class_name)}\s*\{{([^}}]*)}}",
        re.DOTALL,
    )
    match = pattern.search(css_text)
    if not match:
        pytest.fail(
            f"CSS class '.{class_name}' not found in {_DASHBOARD_CSS}. "
            "The rule may have been renamed or removed."
        )
    return match.group(1)


# ---------------------------------------------------------------------------
# Module-level fixtures
# ---------------------------------------------------------------------------

_css_text = _read_file(_DASHBOARD_CSS)
_tsx_text = _read_file(_DASHBOARD_TSX)
_css_globals = CSSGlobalsPage()


# ---------------------------------------------------------------------------
# Layer A: Dashboard CSS module property verification
# ---------------------------------------------------------------------------


class TestLayerACSSProperties:
    """MYTUBE-518 — Layer A: CSS properties in _content.module.css match spec."""

    # ── Heading (.sectionHeading) ─────────────────────────────────────────

    def test_section_heading_font_size(self) -> None:
        """
        Step 2 — Inspect the "My Videos" page heading.
        .sectionHeading must declare font-size: 24px.
        """
        block = _extract_rule_block(_css_text, "sectionHeading")
        assert re.search(r"font-size\s*:\s*24px", block), (
            "Expected .sectionHeading to have 'font-size: 24px' but it was not found. "
            f"Current .sectionHeading block:\n{block.strip()}"
        )

    def test_section_heading_font_weight(self) -> None:
        """
        Step 2 — Inspect the "My Videos" page heading.
        .sectionHeading must declare font-weight: 700.
        """
        block = _extract_rule_block(_css_text, "sectionHeading")
        assert re.search(r"font-weight\s*:\s*700", block), (
            "Expected .sectionHeading to have 'font-weight: 700' but it was not found. "
            f"Current .sectionHeading block:\n{block.strip()}"
        )

    # ── Toolbar card (.toolbar) ───────────────────────────────────────────

    def test_toolbar_background_uses_bg_card_token(self) -> None:
        """
        Step 3 — Inspect the toolbar card container.
        .toolbar must declare background: var(--bg-card).
        """
        block = _extract_rule_block(_css_text, "toolbar")
        assert re.search(r"background\s*:\s*var\(\s*--bg-card\s*\)", block), (
            "Expected .toolbar to have 'background: var(--bg-card)' but it was not found. "
            f"Current .toolbar block:\n{block.strip()}"
        )

    def test_toolbar_border_radius(self) -> None:
        """
        Step 3 — Inspect the toolbar card container.
        .toolbar must declare border-radius: 16px.
        """
        block = _extract_rule_block(_css_text, "toolbar")
        assert re.search(r"border-radius\s*:\s*16px", block), (
            "Expected .toolbar to have 'border-radius: 16px' but it was not found. "
            f"Current .toolbar block:\n{block.strip()}"
        )

    # ── Toolbar grid (.toolbarGrid) ───────────────────────────────────────

    def test_toolbar_grid_columns(self) -> None:
        """
        Step 3 — Inspect the toolbar card container grid layout.
        .toolbarGrid must declare grid-template-columns: 1fr 220px auto.
        """
        block = _extract_rule_block(_css_text, "toolbarGrid")
        assert re.search(r"grid-template-columns\s*:\s*1fr\s+220px\s+auto", block), (
            "Expected .toolbarGrid to have 'grid-template-columns: 1fr 220px auto' "
            "but it was not found. "
            f"Current .toolbarGrid block:\n{block.strip()}"
        )

    def test_toolbar_grid_display(self) -> None:
        """
        Step 3 — Toolbar grid must be a CSS grid container.
        .toolbarGrid must declare display: grid.
        """
        block = _extract_rule_block(_css_text, "toolbarGrid")
        assert re.search(r"display\s*:\s*grid", block), (
            "Expected .toolbarGrid to have 'display: grid' but it was not found. "
            f"Current .toolbarGrid block:\n{block.strip()}"
        )


# ---------------------------------------------------------------------------
# Layer B: Source code structural analysis (_content.tsx)
# ---------------------------------------------------------------------------


class TestLayerBSourceStructure:
    """MYTUBE-518 — Layer B: The dashboard component uses the correct style classes."""

    def test_heading_uses_section_heading_class(self) -> None:
        """
        Step 2 — The "My Videos" <h1> heading must use the sectionHeading style class.
        Expected: styles.sectionHeading is applied to an <h1> element containing
        "My Videos".
        """
        # Verify that sectionHeading is applied to h1 in the component
        assert re.search(r"<h1[^>]*styles\.sectionHeading", _tsx_text), (
            "Expected the dashboard to render <h1 className={styles.sectionHeading}> "
            "but this pattern was not found in _content.tsx. "
            "The sectionHeading CSS class must be applied to the <h1> heading."
        )

    def test_heading_text_is_my_videos(self) -> None:
        """
        Step 2 — The heading text must be "My Videos".
        """
        assert "My Videos" in _tsx_text, (
            "Expected the text 'My Videos' inside the dashboard heading but it was "
            "not found in _content.tsx. "
            "The heading content may have changed."
        )

    def test_toolbar_uses_toolbar_class(self) -> None:
        """
        Step 3 — The toolbar container div must use the toolbar style class.
        Expected: styles.toolbar is applied to the toolbar wrapper element.
        """
        assert re.search(r"styles\.toolbar\b", _tsx_text), (
            "Expected the toolbar container to use styles.toolbar in _content.tsx "
            "but this reference was not found. "
            "The toolbar card may not be applying the correct CSS class."
        )

    def test_toolbar_grid_uses_toolbar_grid_class(self) -> None:
        """
        Step 3 — The inner grid div must use the toolbarGrid style class.
        Expected: styles.toolbarGrid is applied to the CSS grid row container.
        """
        assert re.search(r"styles\.toolbarGrid\b", _tsx_text), (
            "Expected the toolbar grid container to use styles.toolbarGrid in "
            "_content.tsx but this reference was not found. "
            "The grid-template-columns layout may not be applied."
        )


# ---------------------------------------------------------------------------
# Layer C: CSS design token validation (globals.css)
# ---------------------------------------------------------------------------


class TestLayerCDesignTokens:
    """MYTUBE-518 — Layer C: The --bg-card design token is defined in globals.css."""

    def test_bg_card_token_defined_in_globals(self) -> None:
        """
        Step 3 — The toolbar uses var(--bg-card) for its background.
        --bg-card must be defined in the :root block of globals.css.
        """
        value = _css_globals.get_light_token("--bg-card")
        assert value, (
            "The --bg-card CSS custom property is not defined in the :root block "
            "of globals.css. The toolbar background token is missing."
        )
        # Verify it is a valid colour value (hex or rgb)
        assert re.match(r"#[0-9a-fA-F]{3,8}|rgb", value), (
            f"--bg-card is defined as '{value}' which does not look like a valid "
            "colour value. Expected a hex or rgb() value."
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
