"""
MYTUBE-509: Progress bar redesign styling — green gradient and rounded track

Objective
---------
Verify the visual appearance of the progress bar matches the redesign
specifications (gradient fill and height).

Steps
-----
1. Observe the progress bar shell (.progressShell / .progress-shell).
2. Inspect the fill element style while upload is active.

Expected Result
---------------
* The track background is rgba(127, 127, 127, 0.18).
* The fill uses a gradient from var(--accent-cta) to var(--accent-cta-end).
* The bar height is exactly 10px with a border-radius of 999px.

Test Approach
-------------
Static analysis — reads the CSS module (upload.module.css) and globals.css
directly to assert the correct values are in place.  This verifies the
implementation without requiring a running server.

Run from repo root:
    pytest testing/tests/MYTUBE-509/test_mytube_509.py -v
"""
from __future__ import annotations

import re
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_WEB_SRC = _REPO_ROOT / "web" / "src"
_UPLOAD_CSS = _WEB_SRC / "app" / "upload" / "upload.module.css"
_GLOBALS_CSS = _WEB_SRC / "app" / "globals.css"

# ---------------------------------------------------------------------------
# Expected values (from redesign specification)
# ---------------------------------------------------------------------------

_EXPECTED_SHELL_BG = "rgba(127, 127, 127, 0.18)"
_EXPECTED_SHELL_BG_ALT = "rgba(127,127,127,0.18)"   # compact form also acceptable
_EXPECTED_HEIGHT = "10px"
_EXPECTED_BORDER_RADIUS = "999px"
_EXPECTED_GRADIENT = "linear-gradient(90deg, var(--accent-cta)"
_EXPECTED_GRADIENT_END = "var(--accent-cta-end)"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _extract_rule(css: str, selector_fragment: str) -> str:
    """Return the body of the first CSS rule whose selector contains *selector_fragment*."""
    pattern = rf"\.{re.escape(selector_fragment)}\s*\{{([^}}]*)\}}"
    match = re.search(pattern, css, re.DOTALL | re.IGNORECASE)
    if not match:
        raise AssertionError(
            f"CSS rule for '.{selector_fragment}' not found in {_UPLOAD_CSS.name}."
        )
    return match.group(1)


def _normalise(value: str) -> str:
    """Strip whitespace and lowercase for loose comparison."""
    return re.sub(r"\s+", " ", value).strip().lower()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProgressBarCSSModule:
    """MYTUBE-509 (Static): Verify upload.module.css contains the redesign styles."""

    # -- Step 1: progress shell / track ----------------------------------------

    def test_upload_css_exists(self) -> None:
        """upload.module.css must exist at the expected path."""
        assert _UPLOAD_CSS.exists(), (
            f"upload.module.css not found at {_UPLOAD_CSS}. "
            "The progress bar styles are expected to live in this file."
        )

    def test_progress_shell_background(self) -> None:
        """
        Step 1 — .progressShell background must be rgba(127,127,127,0.18).
        """
        css = _read(_UPLOAD_CSS)
        rule = _extract_rule(css, "progressShell")
        norm = _normalise(rule)
        # Accept either spacing variant
        assert (
            "rgba(127, 127, 127, 0.18)" in norm or "rgba(127,127,127,0.18)" in norm
        ), (
            f".progressShell background is not set to rgba(127,127,127,0.18).\n"
            f"Rule body found:\n{rule.strip()}"
        )

    def test_progress_shell_height(self) -> None:
        """
        Step 1 — .progressShell height must be exactly 10px.
        """
        css = _read(_UPLOAD_CSS)
        rule = _extract_rule(css, "progressShell")
        norm = _normalise(rule)
        assert "height: 10px" in norm, (
            f".progressShell height is not '10px'.\n"
            f"Rule body found:\n{rule.strip()}"
        )

    def test_progress_shell_border_radius(self) -> None:
        """
        Step 1 — .progressShell border-radius must be 999px.
        """
        css = _read(_UPLOAD_CSS)
        rule = _extract_rule(css, "progressShell")
        norm = _normalise(rule)
        assert "border-radius: 999px" in norm, (
            f".progressShell border-radius is not '999px'.\n"
            f"Rule body found:\n{rule.strip()}"
        )

    # -- Step 2: progress fill / gradient --------------------------------------

    def test_progress_fill_uses_gradient(self) -> None:
        """
        Step 2 — .progressFill background must use a linear-gradient.
        """
        css = _read(_UPLOAD_CSS)
        rule = _extract_rule(css, "progressFill")
        norm = _normalise(rule)
        assert "linear-gradient" in norm, (
            f".progressFill background does not use linear-gradient.\n"
            f"Rule body found:\n{rule.strip()}"
        )

    def test_progress_fill_gradient_uses_accent_cta(self) -> None:
        """
        Step 2 — .progressFill gradient must start with var(--accent-cta).
        """
        css = _read(_UPLOAD_CSS)
        rule = _extract_rule(css, "progressFill")
        norm = _normalise(rule)
        assert "var(--accent-cta)" in norm, (
            f".progressFill gradient does not reference var(--accent-cta).\n"
            f"Rule body found:\n{rule.strip()}"
        )

    def test_progress_fill_gradient_uses_accent_cta_end(self) -> None:
        """
        Step 2 — .progressFill gradient must end with var(--accent-cta-end).
        """
        css = _read(_UPLOAD_CSS)
        rule = _extract_rule(css, "progressFill")
        norm = _normalise(rule)
        assert "var(--accent-cta-end)" in norm, (
            f".progressFill gradient does not reference var(--accent-cta-end).\n"
            f"Rule body found:\n{rule.strip()}"
        )

    def test_progress_fill_height_full(self) -> None:
        """
        Step 2 — .progressFill height must be 100% (fills the shell).
        """
        css = _read(_UPLOAD_CSS)
        rule = _extract_rule(css, "progressFill")
        norm = _normalise(rule)
        assert "height: 100%" in norm, (
            f".progressFill height is not '100%'.\n"
            f"Rule body found:\n{rule.strip()}"
        )

    # -- globals.css CSS variable definitions ----------------------------------

    def test_globals_css_defines_accent_cta(self) -> None:
        """
        globals.css :root must define --accent-cta used by the fill gradient.
        """
        css = _read(_GLOBALS_CSS)
        assert "--accent-cta" in css, (
            "globals.css does not define --accent-cta. "
            "This CSS variable is required by the progress fill gradient."
        )

    def test_globals_css_defines_accent_cta_end(self) -> None:
        """
        globals.css :root must define --accent-cta-end used by the fill gradient.
        """
        css = _read(_GLOBALS_CSS)
        assert "--accent-cta-end" in css, (
            "globals.css does not define --accent-cta-end. "
            "This CSS variable is required by the progress fill gradient."
        )
