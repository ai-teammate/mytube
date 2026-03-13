"""
MYTUBE-576: Logo icon replacement — rendered SVG matches the provided reference file content.

Objective
---------
Verify that the LogoIcon component uses the exact SVG path and structure from
the provided reference file (logo.svg / favicon.svg).

Preconditions
-------------
The LogoIcon component is implemented at:
  web/src/components/icons/LogoIcon.tsx

The reference SVG is at:
  web/public/favicon.svg

Steps
-----
1. Open the application and inspect the site logo in the header or an auth page.
2. Compare the SVG path data and internal structure with the provided reference
   file (logo.svg).

Expected Result
---------------
The SVG content matches the reference file exactly, resolving the discrepancy
identified in the design review.

Test approach
-------------
Dual-layer static analysis:

**Layer A — Structural attribute check**:
  Reads ``web/src/components/icons/LogoIcon.tsx`` and verifies:
  - viewBox is ``0 0 40 40``
  - root SVG fill is ``none``
  - <rect> has x=2, y=6, width=36, height=28, rx=10
  - Smile arc path: ``M14 26 C16 28 24 28 26 26``
  - Play triangle path: ``M17.5 15.5 L24.5 19.5 L17.5 23.5 V15.5 Z``
  - A linear gradient with CSS variable stops is present

**Layer B — Reference parity check**:
  Reads ``web/public/favicon.svg`` as the canonical shape reference.
  Extracts the same structural elements (viewBox, rect geometry, path data) from
  both files and asserts they are identical.

Run from repo root::

    pytest testing/tests/MYTUBE-576/test_mytube_576.py -v

Architecture
------------
- Pure static analysis — no browser required.
- No hardcoded URLs or environment variables needed.
- Reads source files directly from the repository.
"""
from __future__ import annotations

import re
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# File paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_LOGO_ICON_TSX = _REPO_ROOT / "web" / "src" / "components" / "icons" / "LogoIcon.tsx"
_REFERENCE_SVG = _REPO_ROOT / "web" / "public" / "favicon.svg"

# ---------------------------------------------------------------------------
# Expected values (canonical design specification)
# ---------------------------------------------------------------------------

_EXPECTED_VIEW_BOX = "0 0 40 40"
_EXPECTED_FILL = "none"

# Rect dimensions (the rounded-rect background)
_EXPECTED_RECT_X = "2"
_EXPECTED_RECT_Y = "6"
_EXPECTED_RECT_WIDTH = "36"
_EXPECTED_RECT_HEIGHT = "28"
_EXPECTED_RECT_RX = "10"

# Path data strings (normalised, whitespace-stripped)
_EXPECTED_SMILE_PATH = "M14 26 C16 28 24 28 26 26"
_EXPECTED_PLAY_PATH = "M17.5 15.5 L24.5 19.5 L17.5 23.5 V15.5 Z"

# Gradient stops using CSS custom properties
_EXPECTED_GRAD_START = "var(--logo-grad-start)"
_EXPECTED_GRAD_END = "var(--logo-grad-end)"

# Gradient geometry
_EXPECTED_GRAD_X1 = "0"
_EXPECTED_GRAD_Y1 = "0"
_EXPECTED_GRAD_X2 = "40"
_EXPECTED_GRAD_Y2 = "40"
_EXPECTED_GRAD_UNITS = "userSpaceOnUse"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    assert path.exists(), f"File not found: {path}"
    return path.read_text(encoding="utf-8")


def _attr(source: str, attr_name: str) -> str | None:
    """Extract the first occurrence of attr_name="value" from source."""
    # Matches both JSX (camelCase) and HTML/SVG (kebab-case) attributes
    pattern = re.compile(
        r'(?:^|\s)' + re.escape(attr_name) + r'\s*[=:]\s*["\'{`]([^"\'{`}]+)["\'}]',
        re.MULTILINE,
    )
    m = pattern.search(source)
    return m.group(1).strip() if m else None


def _extract_attr_html(source: str, element: str, attr: str) -> str | None:
    """Extract an XML/SVG attribute value from a specific element."""
    pattern = re.compile(
        r'<' + re.escape(element) + r'[^>]*\s' + re.escape(attr) + r'\s*=\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    m = pattern.search(source)
    return m.group(1).strip() if m else None


def _extract_path_data(source: str) -> list[str]:
    """Return all path ``d`` attribute values found in source."""
    pattern = re.compile(r'\bd\s*[=:]\s*["\'{`]([^"\'{`}]+)["\'}]', re.MULTILINE)
    return [m.group(1).strip() for m in pattern.finditer(source)]


def _extract_stop_colors(source: str) -> list[str]:
    """Return stopColor / stop-color values from gradient stops."""
    # JSX: stopColor="…"  SVG: stop-color="…"
    jsx_pattern = re.compile(r'stopColor\s*=\s*["\'{`]([^"\'{`}]+)["\'}]')
    svg_pattern = re.compile(r'stop-color\s*=\s*["\']([^"\']+)["\']')
    results = [m.group(1).strip() for m in jsx_pattern.finditer(source)]
    results += [m.group(1).strip() for m in svg_pattern.finditer(source)]
    return results


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestLogoIconSVGMatchesReference:
    """Verify LogoIcon.tsx SVG structure matches the reference logo.svg/favicon.svg."""

    # ------------------------------------------------------------------ setup

    @pytest.fixture(scope="class", autouse=True)
    def sources(self, request):
        tsx_source = _read(_LOGO_ICON_TSX)
        ref_source = _read(_REFERENCE_SVG)
        request.cls._tsx = tsx_source
        request.cls._ref = ref_source

    # -------------------------------------------------------- Layer A: LogoIcon.tsx

    def test_logo_icon_file_exists(self):
        assert _LOGO_ICON_TSX.exists(), (
            f"LogoIcon.tsx not found at {_LOGO_ICON_TSX}. "
            "The file must exist for the logo icon to render."
        )

    def test_reference_svg_file_exists(self):
        assert _REFERENCE_SVG.exists(), (
            f"Reference SVG not found at {_REFERENCE_SVG}."
        )

    def test_logo_view_box(self):
        """viewBox must be '0 0 40 40' matching the reference."""
        # Search for viewBox in TSX (JSX attribute)
        match = re.search(r'viewBox\s*=\s*["\']([^"\']+)["\']', self._tsx)
        assert match, "viewBox attribute not found in LogoIcon.tsx"
        actual = match.group(1).strip()
        assert actual == _EXPECTED_VIEW_BOX, (
            f"LogoIcon viewBox mismatch.\n"
            f"  Expected: '{_EXPECTED_VIEW_BOX}'\n"
            f"  Actual:   '{actual}'"
        )

    def test_logo_root_fill_none(self):
        """Root <svg> fill must be 'none'."""
        match = re.search(r'fill\s*=\s*["\']none["\']', self._tsx)
        assert match, (
            "Expected fill=\"none\" on the root <svg> in LogoIcon.tsx but it was not found.\n"
            f"Full source excerpt: {self._tsx[:300]}"
        )

    def test_rect_x_attribute(self):
        match = re.search(r'<rect[^>]*\bx\s*=\s*["\'](\d+)["\']', self._tsx)
        assert match, "<rect> with x attribute not found in LogoIcon.tsx"
        assert match.group(1) == _EXPECTED_RECT_X, (
            f"rect x: expected '{_EXPECTED_RECT_X}', got '{match.group(1)}'"
        )

    def test_rect_y_attribute(self):
        match = re.search(r'<rect[^>]*\by\s*=\s*["\'](\d+)["\']', self._tsx)
        assert match, "<rect> with y attribute not found in LogoIcon.tsx"
        assert match.group(1) == _EXPECTED_RECT_Y, (
            f"rect y: expected '{_EXPECTED_RECT_Y}', got '{match.group(1)}'"
        )

    def test_rect_width(self):
        match = re.search(r'<rect[^>]*\bwidth\s*=\s*["\'](\d+)["\']', self._tsx)
        assert match, "<rect> width not found in LogoIcon.tsx"
        assert match.group(1) == _EXPECTED_RECT_WIDTH, (
            f"rect width: expected '{_EXPECTED_RECT_WIDTH}', got '{match.group(1)}'"
        )

    def test_rect_height(self):
        match = re.search(r'<rect[^>]*\bheight\s*=\s*["\'](\d+)["\']', self._tsx)
        assert match, "<rect> height not found in LogoIcon.tsx"
        assert match.group(1) == _EXPECTED_RECT_HEIGHT, (
            f"rect height: expected '{_EXPECTED_RECT_HEIGHT}', got '{match.group(1)}'"
        )

    def test_rect_rx(self):
        match = re.search(r'<rect[^>]*\brx\s*=\s*["\'](\d+)["\']', self._tsx)
        assert match, "<rect> rx (corner radius) not found in LogoIcon.tsx"
        assert match.group(1) == _EXPECTED_RECT_RX, (
            f"rect rx: expected '{_EXPECTED_RECT_RX}', got '{match.group(1)}'"
        )

    def test_smile_path_data(self):
        """Smile arc path data must match the reference exactly."""
        paths = _extract_path_data(self._tsx)
        assert any(_EXPECTED_SMILE_PATH in p for p in paths), (
            f"Smile arc path '{_EXPECTED_SMILE_PATH}' not found in LogoIcon.tsx.\n"
            f"Found paths: {paths}"
        )

    def test_play_triangle_path_data(self):
        """Play triangle path data must match the reference exactly."""
        paths = _extract_path_data(self._tsx)
        assert any(_EXPECTED_PLAY_PATH in p for p in paths), (
            f"Play triangle path '{_EXPECTED_PLAY_PATH}' not found in LogoIcon.tsx.\n"
            f"Found paths: {paths}"
        )

    def test_gradient_start_stop_uses_css_variable(self):
        """First gradient stop must reference --logo-grad-start CSS variable."""
        stops = _extract_stop_colors(self._tsx)
        assert stops, "No gradient stop colors found in LogoIcon.tsx"
        assert stops[0] == _EXPECTED_GRAD_START, (
            f"First gradient stop: expected '{_EXPECTED_GRAD_START}', got '{stops[0]}'"
        )

    def test_gradient_end_stop_uses_css_variable(self):
        """Second gradient stop must reference --logo-grad-end CSS variable."""
        stops = _extract_stop_colors(self._tsx)
        assert len(stops) >= 2, "Expected at least two gradient stops in LogoIcon.tsx"
        assert stops[1] == _EXPECTED_GRAD_END, (
            f"Second gradient stop: expected '{_EXPECTED_GRAD_END}', got '{stops[1]}'"
        )

    def test_gradient_geometry(self):
        """linearGradient must span from (0,0) to (40,40) in userSpaceOnUse."""
        assert 'x1="0"' in self._tsx or "x1={" in self._tsx, \
            "linearGradient x1=0 not found in LogoIcon.tsx"
        assert 'y1="0"' in self._tsx or "y1={" in self._tsx, \
            "linearGradient y1=0 not found in LogoIcon.tsx"
        assert 'x2="40"' in self._tsx or "x2={" in self._tsx, \
            "linearGradient x2=40 not found in LogoIcon.tsx"
        assert 'y2="40"' in self._tsx or "y2={" in self._tsx, \
            "linearGradient y2=40 not found in LogoIcon.tsx"
        assert 'gradientUnits="userSpaceOnUse"' in self._tsx, \
            "gradientUnits='userSpaceOnUse' not found in LogoIcon.tsx"

    # -------------------------------------------------- Layer B: parity with reference SVG

    def test_reference_view_box_matches(self):
        """favicon.svg viewBox must be the same as LogoIcon.tsx."""
        ref_match = re.search(r'viewBox\s*=\s*["\']([^"\']+)["\']', self._ref)
        assert ref_match, "viewBox not found in reference favicon.svg"
        tsx_match = re.search(r'viewBox\s*=\s*["\']([^"\']+)["\']', self._tsx)
        assert tsx_match, "viewBox not found in LogoIcon.tsx"
        assert ref_match.group(1).strip() == tsx_match.group(1).strip(), (
            f"viewBox mismatch between favicon.svg and LogoIcon.tsx:\n"
            f"  favicon.svg: '{ref_match.group(1).strip()}'\n"
            f"  LogoIcon.tsx: '{tsx_match.group(1).strip()}'"
        )

    def test_reference_rect_geometry_matches(self):
        """Rect geometry (x, y, width, height, rx) must match in both files."""
        for attr in ("x", "y", "width", "height", "rx"):
            ref_match = re.search(
                r'<rect[^>]*\b' + re.escape(attr) + r'\s*=\s*["\'](\w+)["\']',
                self._ref,
            )
            tsx_match = re.search(
                r'<rect[^>]*\b' + re.escape(attr) + r'\s*=\s*["\'](\w+)["\']',
                self._tsx,
            )
            assert ref_match, f"rect {attr} not found in reference favicon.svg"
            assert tsx_match, f"rect {attr} not found in LogoIcon.tsx"
            assert ref_match.group(1) == tsx_match.group(1), (
                f"rect {attr} mismatch:\n"
                f"  favicon.svg: '{ref_match.group(1)}'\n"
                f"  LogoIcon.tsx: '{tsx_match.group(1)}'"
            )

    def test_reference_smile_path_matches(self):
        """Smile arc path in LogoIcon.tsx must equal that in favicon.svg."""
        ref_paths = _extract_path_data(self._ref)
        tsx_paths = _extract_path_data(self._tsx)

        ref_smile = next((p for p in ref_paths if "C" in p or "c" in p), None)
        tsx_smile = next((p for p in tsx_paths if "C" in p or "c" in p), None)

        assert ref_smile is not None, "Smile (curve) path not found in favicon.svg"
        assert tsx_smile is not None, "Smile (curve) path not found in LogoIcon.tsx"
        assert ref_smile == tsx_smile, (
            f"Smile path mismatch:\n"
            f"  favicon.svg: '{ref_smile}'\n"
            f"  LogoIcon.tsx: '{tsx_smile}'"
        )

    def test_reference_play_path_matches(self):
        """Play triangle path in LogoIcon.tsx must equal that in favicon.svg."""
        ref_paths = _extract_path_data(self._ref)
        tsx_paths = _extract_path_data(self._tsx)

        ref_play = next((p for p in ref_paths if "L" in p and "Z" in p), None)
        tsx_play = next((p for p in tsx_paths if "L" in p and "Z" in p), None)

        assert ref_play is not None, "Play triangle path (L…Z) not found in favicon.svg"
        assert tsx_play is not None, "Play triangle path (L…Z) not found in LogoIcon.tsx"
        assert ref_play == tsx_play, (
            f"Play path mismatch:\n"
            f"  favicon.svg: '{ref_play}'\n"
            f"  LogoIcon.tsx: '{tsx_play}'"
        )
